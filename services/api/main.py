"""Local, read-only customer analytics API. No external services are called."""
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import timedelta
import os
from uuid import uuid4
from threading import RLock
import time
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from optimizer import Assumptions,Customer,DEFAULT_BUDGET,DEFAULT_MAX_COUPONS,optimize
from executive import load_executive
from views import PagedViews

Run = Literal['A','B','C','A_no_cap','PROD']
Model = Literal['baseline_const','baseline_recent','bgnbd','logreg','gboost']
MODELS = ('baseline_const','baseline_recent','bgnbd','logreg','gboost')
DEFAULT_GRID = {'budgets':[500.,1000.,float(DEFAULT_BUDGET),2500.,3500.], 'tau_c_values':[.05,.15,.25]}


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False,validate_default=True)
    run: Run = 'PROD'
    model: Model = 'bgnbd'
    B: float = Field(default=DEFAULT_BUDGET,ge=0,le=1_000_000_000)
    K: int = Field(default=DEFAULT_MAX_COUPONS,ge=0,le=1_000_000,strict=True)
    m: float = Field(default=.30,ge=0,le=1)
    tau_e: float = Field(default=.02,ge=0,le=1)
    tau_c: float = Field(default=.15,ge=0,le=1)
    f_e: float = Field(default=.05,ge=0,le=1_000_000)
    f_c: float = Field(default=1.,ge=0,le=1_000_000)
    d: float = Field(default=.10,ge=0,le=1)
    include_extra_100: bool = False
    interactive: bool = True


class SensitivityRequest(OptimizeRequest):
    budgets: list[float] = Field(default_factory=lambda:list(DEFAULT_GRID['budgets']),min_length=1,max_length=15)
    tau_c_values: list[float] = Field(default_factory=lambda:list(DEFAULT_GRID['tau_c_values']),min_length=1,max_length=15)

    @model_validator(mode='after')
    def bounded_grid(self):
        if len(self.budgets)*len(self.tau_c_values)>15:
            raise ValueError('Grid must contain at most 15 solves')
        if any(not 0<=v<=1_000_000_000 for v in self.budgets) or any(not 0<=v<=1 for v in self.tau_c_values):
            raise ValueError('Grid values outside valid ranges')
        if len(set(self.budgets))!=len(self.budgets) or len(set(self.tau_c_values))!=len(self.tau_c_values):
            raise ValueError('Grid values must be unique')
        if self.include_extra_100 or not self.interactive:
            raise ValueError('Sensitivity uses interactive mode without extra-budget solves')
        return self


def connect():
    return psycopg.connect(host=os.environ['POSTGRES_HOST'],dbname=os.environ['POSTGRES_DB'],
                          user=os.environ['POSTGRES_USER'],password=os.environ['POSTGRES_PASSWORD'],
                          connect_timeout=3,options='-c statement_timeout=10000',row_factory=dict_row)


def load_snapshot():
    """One immutable, point-consistent snapshot per API startup; never writes DB."""
    try:
        with connect() as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            runs=connection.execute('''SELECT run_id,run_name,train_cutoff,test_cutoff,window_days,
                                      n_train,n_test,base_rate_train,base_rate_test,created_at
                                      FROM modeling.model_runs WHERE run_name = ANY(%s)
                                      ORDER BY test_cutoff,run_name''',(['A','B','C','A_no_cap','PROD'],)).fetchall()
            metrics=connection.execute('''SELECT r.run_name,p.model,p.metric,p.segment,p.value
                                         FROM modeling.model_metrics p JOIN modeling.model_runs r USING(run_id)
                                         WHERE r.run_name = ANY(%s)''',(['A','B','C','A_no_cap','PROD'],)).fetchall()
            predictions=connection.execute('''SELECT r.run_name,p.model,p.customer_id,p."p_purchase_N",
                                             p.expected_order_value,p.actual_spend,p.actual_purchased,p.actual_purchases,
                                             p."expected_purchases_N",p."bgnbd_clv_N"
                                             FROM modeling.customer_predictions p JOIN modeling.model_runs r USING(run_id)
                                             WHERE r.run_name = ANY(%s) ORDER BY p.customer_id''',
                                             (['A','B','C','A_no_cap','PROD'],)).fetchall()
            prod=next((r for r in runs if r['run_name']=='PROD'),None)
            executive=load_executive(connection,predictions,prod['test_cutoff']) if prod else None
    except (psycopg.Error,KeyError):
        raise RuntimeError('Database snapshot unavailable; check local configuration and model completion') from None
    customers={}
    for row in predictions:
        customers.setdefault((row['run_name'],row['model']),[]).append(
            Customer(row['customer_id'],row['p_purchase_N'],row['expected_order_value'],
                     row['actual_spend'],row['actual_purchased'],row['actual_purchases']))
    formatted=[]
    for row in runs:
        formatted.append({**row,'horizon_end':row['test_cutoff']+timedelta(days=row['window_days']),
                          'scoring_cutoff':row['test_cutoff'],'has_outcomes':row['base_rate_test'] is not None})
    return {'runs':formatted,'metrics':metrics,'customers':customers,'executive':executive}


class CampaignService:
    def __init__(self,snapshot):
        self.snapshot=snapshot
        self.cache=OrderedDict()
        self.lock=RLock()
        self.precompute_seconds=None
        self.views=PagedViews(snapshot.get('executive'))
        self.solution_ids=set()

    def require_run(self,run):
        if not any(r['run_name']==run for r in self.snapshot['runs']):
            raise HTTPException(status_code=404,detail='Run unavailable; complete the model job and restart the API')

    def campaign(self,request):
        tick=time.perf_counter()
        self.require_run(request.run)
        key=request.model_dump_json()
        with self.lock:
            if key in self.cache:
                value=self.cache[key]
                self.cache.move_to_end(key)
                return {**value,'cache_hit':True,'request_seconds':time.perf_counter()-tick}
        customers=self.snapshot['customers'].get((request.run,request.model))
        if customers is None:
            raise HTTPException(status_code=404,detail='Model predictions unavailable')
        assumptions=Assumptions(**{k:getattr(request,k) for k in asdict(Assumptions())})
        value=optimize(customers,request.B,request.K,assumptions,
                       include_extra_100=request.include_extra_100,interactive=request.interactive)
        assignments=value.pop('assignments')
        value['baseline'].pop('assignments')
        metadata=next(r for r in self.snapshot['runs'] if r['run_name']==request.run)
        value.update(run=request.run,model=request.model,scoring_cutoff=metadata['scoring_cutoff'],
                     horizon_end=metadata['horizon_end'])
        with self.lock:
            # A concurrent identical solve must not replace the plan already served.
            if key in self.cache:
                return {**self.cache[key],'cache_hit':True,'request_seconds':time.perf_counter()-tick}
            value['solution_id']=uuid4().hex
            self.views.store_campaign(value['solution_id'],assignments)
            self.solution_ids.add(value['solution_id'])
            self.cache[key]=value
            self.cache.move_to_end(key)
            while len(self.cache)>256:
                _,expired=self.cache.popitem(last=False)
                self.solution_ids.discard(expired['solution_id'])
                self.views.discard_campaign(expired['solution_id'])
        return {**value,'cache_hit':False,'request_seconds':time.perf_counter()-tick}

    def sensitivity(self,request):
        tick=time.perf_counter()
        base=request.model_dump(exclude={'budgets','tau_c_values'})
        points=[]
        for tau in request.tau_c_values:
            for B in request.budgets:
                result=self.campaign(OptimizeRequest(**{**base,'tau_c':tau,'B':B}))
                points.append({'tau_c':tau,'B':B,'net_value':result['net_value'],'cost':result['cost'],
                               'counts':result['counts'],'solver':result['solver'],'cache_hit':result['cache_hit']})
        return {'run':request.run,'model':request.model,'points':points,'solves':sum(not p['cache_hit'] for p in points),
                'grid_points':len(points),'seconds':time.perf_counter()-tick}


@asynccontextmanager
async def lifespan(application):
    application.state.service=CampaignService(load_snapshot())
    tick=time.perf_counter()
    # Local batch snapshot is immutable until restart; cache keys include all inputs.
    application.state.service.sensitivity(SensitivityRequest())
    application.state.service.precompute_seconds=time.perf_counter()-tick
    yield


app=FastAPI(title='Customer campaign analytics',lifespan=lifespan)
dashboard_port=int(os.environ.get('DASHBOARD_PORT','8080'))
app.add_middleware(CORSMiddleware,allow_origins=[f'http://127.0.0.1:{dashboard_port}',f'http://localhost:{dashboard_port}'],
                   allow_methods=['GET','POST'],allow_headers=['Content-Type'])


@app.exception_handler(RequestValidationError)
async def validation_error(_,error):
    # Do not echo arbitrary submitted values (or non-JSON NaN) into responses.
    return JSONResponse(status_code=422,content={'detail':[
        {key:item[key] for key in ('loc','msg','type')} for item in error.errors()]})


@app.get('/health')
def health():
    try:
        with connect() as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            connection.execute('SELECT 1')
    except (psycopg.Error,KeyError):
        raise HTTPException(status_code=503,detail='Database unavailable') from None
    return {'status':'ok','database':'ok'}


@app.get('/api/runs')
def runs():
    return {'runs':app.state.service.snapshot['runs']}


@app.get('/api/metrics')
def metrics(run:Run='A'):
    service=app.state.service
    service.require_run(run)
    rows=[r for r in service.snapshot['metrics'] if r['run_name']==run and r['segment']=='overall']
    return {'run':run,'has_outcomes':run!='PROD','models':[
        {'model':model,**{r['metric']:r['value'] for r in rows if r['model']==model}} for model in MODELS]}


@app.get('/api/calibration')
def calibration(run:Run='A',model:Model='bgnbd'):
    service=app.state.service
    service.require_run(run)
    bins={}
    for row in service.snapshot['metrics']:
        if row['run_name']==run and row['model']==model and row['metric'] in ('calib_n','calib_mean_pred','calib_observed_rate'):
            bins.setdefault(int(row['segment']),{'bin':int(row['segment'])})[row['metric']]=row['value']
    return {'run':run,'model':model,'available':bool(bins),'bins':sorted(bins.values(),key=lambda r:r['bin'])}


@app.get('/api/defaults')
def defaults():
    return {'defaults':OptimizeRequest().model_dump(),'ranges':{
        'B':[0,1_000_000_000],'K':[0,1_000_000],
        **{k:[0,1] for k in ('m','tau_e','tau_c','d')},'f_e':[0,1_000_000],'f_c':[0,1_000_000]},
        'models':MODELS,'sensitivity_grid':DEFAULT_GRID,'maximum_sensitivity_solves':15,
        'interactive_relative_gap':.005,'precompute_seconds':app.state.service.precompute_seconds,
        'assumption_note':'tau and margin are assumptions, not estimated from data; an A/B test would estimate tau'}


@app.post('/api/optimize')
def optimize_endpoint(request:OptimizeRequest):
    return app.state.service.campaign(request)


@app.post('/api/sensitivity')
def sensitivity_endpoint(request:SensitivityRequest):
    return app.state.service.sensitivity(request)


def executive_data():
    data=app.state.service.snapshot.get('executive')
    if data is None:
        raise HTTPException(status_code=503,detail='Executive data unavailable; complete PROD and restart the API')
    return data


@app.get('/api/exec/summary')
def executive_summary():
    result=executive_data().summary()
    campaign=app.state.service.campaign(OptimizeRequest())
    return {**result,'campaign_expected_profit':campaign['net_value'],
            'campaign_budget':campaign['B'],'campaign_max_coupons':campaign['K'],
            'campaign_assumptions':campaign['assumptions']}


@app.get('/api/sales/by-country')
def sales_by_country():
    data=executive_data()
    return {'as_of':data.as_of.isoformat(),'window':data.window,'rows':data.countries,
            'total':data.summary()['net_sales_12m'],'countries':sorted(data.products[k]['country'] for k in data.products if k is not None)}


@app.get('/api/sales/monthly')
def sales_monthly(country:str=Query(default='',max_length=100)):
    executive_data()
    views=app.state.service.views
    if country and country not in views.countries:
        raise HTTPException(status_code=422,detail='Unknown country')
    return views.monthly(country)


@app.get('/api/products/top')
def products_top(country:str=Query(default='',max_length=100)):
    data=executive_data()
    key=country or None
    if key not in data.products:
        raise HTTPException(status_code=404,detail='Country unavailable')
    return {'as_of':data.as_of.isoformat(),'window':data.window,**data.products[key]}


@app.get('/api/cancellations/monthly')
def cancellations_monthly():
    data=executive_data()
    return {'as_of':data.as_of.isoformat(),'rows':data.cancellations}


@app.get('/api/customers/loyalty-heatmap')
def loyalty_heatmap(limit:int=Query(default=10,ge=1,le=100),
                    offset:int=Query(default=0,ge=0,le=1_000_000),
                    customer_id:str=Query(default='',max_length=64,pattern=r'^[0-9]*$'),
                    year:int=Query(default=2011,ge=2010,le=2011)):
    executive_data()
    return app.state.service.views.loyalty(limit,offset,customer_id,year)


@app.get('/api/customers')
def customer_list(search:str=Query(default='',max_length=64),
                  sort:Literal['customer_id','days_since_last_purchase','number_of_purchases','customer_age_days',
                               'probability_of_buying_90d','expected_spend_90d']='customer_id',
                  direction:Literal['asc','desc']='asc',page:int=Query(default=1,ge=1)):
    return executive_data().customer_page(search,sort,direction,page)


CampaignAction = Literal['coupon','email','none','all']

def require_solution(solution_id):
    service=app.state.service
    if solution_id not in service.solution_ids:
        raise HTTPException(status_code=422,detail='Campaign expired or unknown; update the proposal')
    return service


@app.get('/api/campaign/customers')
def campaign_customers(solution_id:str=Query(pattern=r'^[a-f0-9]{32}$'),
                       action:CampaignAction='coupon',
                       limit:int=Query(default=15,ge=1,le=100),
                       offset:int=Query(default=0,ge=0,le=1_000_000)):
    service=app.state.service
    with service.lock:
        require_solution(solution_id)
        return service.views.campaign(solution_id,action,limit,offset)


@app.get('/api/campaign/export')
def campaign_export(solution_id:str=Query(pattern=r'^[a-f0-9]{32}$'),action:CampaignAction='coupon'):
    service=app.state.service
    with service.lock:
        require_solution(solution_id)
        content=service.views.campaign_csv(solution_id,action)
    return Response(content,media_type='text/csv',
        headers={'Content-Disposition':f'attachment; filename="campaign-{action}.csv"'})
