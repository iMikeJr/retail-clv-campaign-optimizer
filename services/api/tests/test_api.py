"""ASGI integration tests using only stdlib and existing runtime dependencies."""
import asyncio
from datetime import date,datetime,timezone
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main
from optimizer import Customer


def fixture_snapshot():
    runs=[]; customers={}; metrics=[]
    for run in ('A','PROD'):
        runs.append({'run_name':run,'run_id':run,'train_cutoff':date(2011,6,12),
                     'test_cutoff':date(2011,9,10),'scoring_cutoff':date(2011,9,10),
                     'horizon_end':date(2011,12,9),'has_outcomes':run=='A',
                     'created_at':datetime(2026,1,1,tzinfo=timezone.utc),'n_test':3})
        for model in main.MODELS:
            customers[run,model]=[Customer('a',.1,400,100 if run=='A' else None,actual_purchases=2 if run=='A' else None),
                                  Customer('b',.5,400,0 if run=='A' else None,actual_purchases=0 if run=='A' else None),
                                  Customer('c',.1,50,20 if run=='A' else None,actual_purchases=1 if run=='A' else None)]
            metrics.append(dict(run_name=run,model=model,metric='mean_predicted_probability',segment='overall',value=.2))
            if run=='A':
                metrics.extend(dict(run_name=run,model=model,metric=m,segment='1',value=v)
                               for m,v in [('calib_n',3),('calib_mean_pred',.2),('calib_observed_rate',2/3)])
    return dict(runs=runs,customers=customers,metrics=metrics)


@pytest.fixture(autouse=True)
def fake_database(monkeypatch):
    monkeypatch.setattr(main,'load_snapshot',fixture_snapshot)
    monkeypatch.setattr(main,'connect',lambda:MagicMock())


async def call(method,path,body=None,origin=None,query=''):
    messages=[]
    headers=[(b'content-type',b'application/json')]
    if origin: headers.append((b'origin',origin.encode()))
    sent=False
    async def receive():
        nonlocal sent
        if not sent:
            sent=True
            return {'type':'http.request','body':json.dumps(body).encode() if body is not None else b'', 'more_body':False}
        await asyncio.sleep(1)
        return {'type':'http.disconnect'}
    async def send(message): messages.append(message)
    await main.app({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,
                    'scheme':'http','path':path,'raw_path':path.encode(),'query_string':query.encode(),
                    'root_path':'','headers':headers,'server':('test',80),'client':('127.0.0.1',1)},receive,send)
    start=next(m for m in messages if m['type']=='http.response.start')
    data=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
    return start['status'],dict(start['headers']),json.loads(data) if data else None


def scenario(function):
    async def run():
        async with main.app.router.lifespan_context(main.app):
            await function()
    asyncio.run(run())


def test_endpoints_and_precomputed_grid():
    async def check():
        assert (await call('GET','/health'))[0] == 200
        assert len((await call('GET','/api/runs'))[2]['runs']) == 2
        assert (await call('GET','/api/defaults'))[2]['maximum_sensitivity_solves'] == 15
        assert len((await call('GET','/api/metrics',query='run=A'))[2]['models']) == 5
        assert (await call('GET','/api/calibration',query='run=A&model=bgnbd'))[2]['available']
        assert not (await call('GET','/api/calibration',query='run=PROD&model=bgnbd'))[2]['available']
        grid=(await call('POST','/api/sensitivity',{}))[2]
        assert grid['solves']==0 and grid['grid_points']==15
        status,_,r=await call('POST','/api/optimize',dict(B=10.5))
        assert status==200 and r['extra_100'] is None
        assert r['net_value']==pytest.approx(7.17)
        assert r['by_action']['coupon']['customers']==1
        assert set(r['baselines'])=={'naive','email_only','ratio_greedy'}
        assert r['solver']['optimality_gap']<=.005
        repeated=(await call('POST','/api/optimize',dict(B=10.5)))[2]
        assert repeated['cache_hit']
        assert (await call('POST','/api/optimize',dict(B=10.5,include_extra_100=True)))[2]['extra_100'] is not None
        group=(await call('POST','/api/optimize',dict(B=10.5,run='A')))[2]['backtest']['groups']['all_eligible']
        assert group['customers']==3
        assert group['mean_realized_order_value_buyers']==35
    scenario(check)


@pytest.mark.parametrize('body',[{'B':-1},{'K':1.5},{'m':1.1},{'tau_c':-1},{'f_e':-1},{'d':2},
                                  {'run':"A'; DROP TABLE modeling.model_runs;--"},{'model':'other'},
                                  {'unknown':1},{'B':'NaN'}])
def test_invalid_optimize_returns_422(body):
    async def check(): assert (await call('POST','/api/optimize',body))[0]==422
    scenario(check)


@pytest.mark.parametrize('body',[{'budgets':list(range(6)),'tau_c_values':[.1,.2,.3]},
                                  {'budgets':[-1]},{'tau_c_values':[1.1]},
                                  {'budgets':[1,1]},{'interactive':False},{'include_extra_100':True}])
def test_invalid_sensitivity_returns_422(body):
    async def check(): assert (await call('POST','/api/sensitivity',body))[0]==422
    scenario(check)


def test_cors_and_missing_run():
    async def check():
        for origin in ('http://localhost:8080','http://127.0.0.1:8080'):
            status,headers,_=await call('GET','/api/defaults',origin=origin)
            assert status==200 and headers[b'access-control-allow-origin'].decode()==origin
        assert b'access-control-allow-origin' not in (await call('GET','/api/defaults',origin='https://example.com'))[1]
        assert (await call('GET','/api/metrics',query='run=B'))[0]==404
    scenario(check)
