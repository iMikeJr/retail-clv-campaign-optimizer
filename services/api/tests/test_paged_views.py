"""Paged campaign and loyalty routes: bound values, cached plans and reconciliation."""
import csv
import io
from unittest.mock import MagicMock
from urllib.parse import urlencode

import pytest

import main
from optimizer import Customer
from views import PagedViews
from test_api import call, scenario, fixture_snapshot
from test_executive import fixture_executive,fixture_inputs


def snapshot():
    s=fixture_snapshot()
    s['executive']=fixture_executive()
    for key in s['customers']:
        s['customers'][key]=[Customer(str(i+1),c.pi,c.v,c.actual_spend,c.actual_purchased,c.actual_purchases)
                             for i,c in enumerate(s['customers'][key])]
    # Enough customers for several pages, with near-certain buyers left uncontacted.
    s['customers']['PROD','bgnbd'] += [Customer(str(1000+i),1. if i%4==0 else .1,100.+i*5) for i in range(37)]
    return s


@pytest.fixture(autouse=True)
def fake_database(monkeypatch):
    monkeypatch.setattr(main,'load_snapshot',snapshot)
    monkeypatch.setattr(main,'connect',lambda:MagicMock())


async def csv_call(query):
    messages=[]
    async def receive():return {'type':'http.request','body':b'','more_body':False}
    async def send(message):messages.append(message)
    await main.app({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'GET',
        'scheme':'http','path':'/api/campaign/export','raw_path':b'/api/campaign/export',
        'query_string':query.encode(),'root_path':'','headers':[],
        'server':('test',80),'client':('127.0.0.1',1)},receive,send)
    start=next(m for m in messages if m['type']=='http.response.start')
    return start['status'],dict(start['headers']),b''.join(m.get('body',b'') for m in messages).decode()


def test_country_series_add_up_month_by_month_including_historical_only_country():
    async def check():
        status,_,overall=await call('GET','/api/sales/monthly')
        assert status==200 and 'United States' in overall['countries']
        filtered=[]
        for country in overall['countries']:
            code,_,result=await call('GET','/api/sales/monthly',query=urlencode({'country':country}))
            assert code==200 and result['country']==country
            assert [r['month'] for r in result['rows']]==[r['month'] for r in overall['rows']]
            assert result['total']==pytest.approx(sum(r['net_sales'] for r in result['rows']))
            filtered.append(result)
        for i,row in enumerate(overall['rows']):
            for key in ['net_sales','gross_sales','returns_value']:
                assert sum(c['rows'][i][key] for c in filtered)==pytest.approx(row[key])
        assert overall['total']==340
        assert (await call('GET','/api/sales/monthly',query='country='))[2]['rows']==overall['rows']
    scenario(check)


@pytest.mark.parametrize('country',['Atlantis',"France';DROP TABLE monthly;--",'x'*101])
def test_invalid_country_422(country):
    async def check():assert (await call('GET','/api/sales/monthly',query=urlencode({'country':country})))[0]==422
    scenario(check)


def test_loyalty_pages_and_exact_search_preserve_ranking_and_top_ten():
    async def check():
        expected=main.app.state.service.snapshot['executive'].heatmap['rows']
        default=(await call('GET','/api/customers/loyalty-heatmap'))[2]
        assert default['limit']==10 and default['offset']==0 and default['rows']==expected[:10]
        pages=[]
        for offset in range(default['total']):
            status,_,data=await call('GET','/api/customers/loyalty-heatmap',query=f'limit=1&offset={offset}')
            assert status==200 and data['offset']==offset and data['total']==len(expected)
            pages+=data['rows']
        assert pages==expected
        jump=(await call('GET','/api/customers/loyalty-heatmap',query='limit=1&offset=0&customer_id=1'))[2]
        assert jump['offset']==1 and jump['highlight_id']=='1' and jump['found'] is True
        assert jump['rows'][0]['customer_id']=='1'
        missing=(await call('GET','/api/customers/loyalty-heatmap',query='customer_id=999999'))[2]
        assert missing['found'] is False and missing['highlight_id'] is None
        assert (await call('GET','/api/customers/loyalty-heatmap',query='offset=100'))[2]['rows']==[]
    scenario(check)


def test_lapsed_customer_legitimately_returns_an_all_zero_heatmap_row():
    """Lapsed (reactivation) customers stay in the ranking; their 12 monthly cells are real zeros."""
    async def check():
        status,_,data=await call('GET','/api/customers/loyalty-heatmap',query='customer_id=3')
        assert status==200 and data['found'] is True and data['highlight_id']=='3'
        row=next(r for r in data['rows'] if r['customer_id']=='3')
        assert row['monthly_spend']==[0.]*12 and row['purchase_days_12m']==0 and row['spend_12m']==0
        assert len(data['months'])==12
    scenario(check)


def test_year_defaults_to_2011_and_leaves_the_response_unchanged():
    async def check():
        plain=(await call('GET','/api/customers/loyalty-heatmap'))[2]
        explicit=(await call('GET','/api/customers/loyalty-heatmap',query='year=2011'))[2]
        assert explicit==plain
        assert plain['months']==[f'2011-{m:02d}' for m in range(1,13)] and 'year' not in plain
    scenario(check)


def test_year_2010_changes_only_the_month_columns_not_the_ranking():
    async def check():
        base=(await call('GET','/api/customers/loyalty-heatmap'))[2]
        old=(await call('GET','/api/customers/loyalty-heatmap',query='year=2010'))[2]
        assert old['months']==[f'2010-{m:02d}' for m in range(1,13)]
        assert old['display_start']=='2010-01-01' and old['display_end']=='2010-12-31'
        assert [r['customer_id'] for r in old['rows']]==[r['customer_id'] for r in base['rows']]
        strip=lambda r:{k:v for k,v in r.items() if k!='monthly_spend'}
        assert [strip(r) for r in old['rows']]==[strip(r) for r in base['rows']]
        assert all(len(r['monthly_spend'])==12 for r in old['rows'])
        assert {k:old[k] for k in ('total','limit','offset')}=={k:base[k] for k in ('total','limit','offset')}
        paged=(await call('GET','/api/customers/loyalty-heatmap',query='year=2010&limit=1&offset=2'))[2]
        assert paged['rows'][0]['customer_id']==base['rows'][2]['customer_id']
        found=(await call('GET','/api/customers/loyalty-heatmap',query='year=2010&customer_id=3'))[2]
        assert found['highlight_id']=='3' and found['found'] is True
    scenario(check)


def test_year_2010_spend_matches_that_customers_2010_purchases():
    daily=fixture_inputs()['daily']
    async def check():
        rows=(await call('GET','/api/customers/loyalty-heatmap',query='year=2010'))[2]['rows']
        for r in rows:
            expected=sum(d['purchase_value'] for d in daily
                         if d['customer_id']==r['customer_id'] and d['purchase_date'].startswith('2010-'))
            assert sum(r['monthly_spend'])==pytest.approx(expected)
        one=next(r for r in rows if r['customer_id']=='1')
        assert one['monthly_spend'][11]==30 and sum(one['monthly_spend'])==30
        assert sum(next(r for r in rows if r['customer_id']=='3')['monthly_spend'])==0
    scenario(check)


@pytest.mark.parametrize('year',['2009','2012','abc','1.5','','-2010','2010%27%20OR%201=1'])
def test_invalid_year_422(year):
    async def check():assert (await call('GET','/api/customers/loyalty-heatmap',query=f'year={year}'))[0]==422
    scenario(check)


def test_loyalty_can_page_beyond_the_old_25_row_cap():
    e=fixture_executive()
    e.heatmap['rows']=[dict(e.heatmap['rows'][0],customer_id=f'{i:04}') for i in range(57)]
    views=PagedViews(e)
    pages=[views.loyalty(10,offset,'') for offset in range(0,57,10)]
    assert [r for page in pages for r in page['rows']]==e.heatmap['rows']
    assert views.loyalty(10,0,'0056')['offset']==50
    assert len(pages[-1]['rows'])==7


@pytest.mark.parametrize('query',['limit=0','limit=-1','limit=101','limit=1.5','limit=abc',
    'offset=-1','offset=1000001','offset=1.5','offset=abc','customer_id=abc',
    'customer_id=1%27%20OR%201=1','customer_id='+'1'*65])
def test_invalid_heatmap_parameters_422(query):
    async def check():assert (await call('GET','/api/customers/loyalty-heatmap',query=query))[0]==422
    scenario(check)


def test_campaign_pages_csv_and_counts_reconcile_without_a_new_solve(monkeypatch):
    async def check():
        status,_,result=await call('POST','/api/optimize',{'B':10.5,'K':1})
        assert status==200
        token=result['solution_id']
        assert 'assignments' not in result and len(result['top_selected'])<=15
        repeated=(await call('POST','/api/optimize',{'B':10.5,'K':1}))[2]
        assert repeated['cache_hit'] and repeated['solution_id']==token
        def no_solve(*a,**k):raise AssertionError('Paging/export must not optimize again')
        monkeypatch.setattr(main,'optimize',no_solve)
        all_rows=[]
        for action in ['coupon','email','none','all']:
            query={'solution_id':token,'action':action,'limit':7,'offset':0}
            code,_,first=await call('GET','/api/campaign/customers',query=urlencode(query))
            assert code==200
            assert first['total']==(sum(result['counts'].values()) if action=='all' else result['counts'][action])
            rows=[]
            for offset in range(0,first['total'],7):
                query['offset']=offset
                rows+=(await call('GET','/api/campaign/customers',query=urlencode(query)))[2]['rows']
            assert len(rows)==len({r['customer_id'] for r in rows})==first['total']
            assert rows==sorted(rows,key=lambda r:(-r['net_value'],r['customer_id']))
            if action!='all':assert all(r['action']==action for r in rows)
            else:all_rows=rows
            code,headers,text=await csv_call(urlencode({'solution_id':token,'action':action}))
            assert code==200 and headers[b'content-type'].startswith(b'text/csv')
            assert b'attachment' in headers[b'content-disposition']
            exported=list(csv.DictReader(io.StringIO(text)))
            assert len(exported)==first['total']
            assert list(exported[0])==['customer_id','action','days_since_last_purchase','expected_spend_90d','order_value','expected_gain'] if exported else True
            for a,b in zip(rows,exported):
                assert (a['customer_id'],a['action'])==(b['customer_id'],b['action'])
                assert b['order_value']==f"{a['v']:.2f}" and b['expected_gain']==f"{a['net_value']:.2f}"
        assert len(all_rows)==40
        one=next(r for r in all_rows if r['customer_id']=='1')
        assert one['days_since_last_purchase']==338 and one['expected_spend_90d']==200
        assert (await call('GET','/api/campaign/customers',query=urlencode({'solution_id':token,'offset':1000})))[2]['rows']==[]
        default=(await call('GET','/api/campaign/customers',query=urlencode({'solution_id':token})))[2]
        assert default['action']=='coupon' and default['limit']==15
    scenario(check)


@pytest.mark.parametrize('params',[{'action':'invalid'},{'action':"coupon' OR 1=1"},
    {'limit':0},{'limit':101},{'limit':1.5},{'limit':'abc'},
    {'offset':-1},{'offset':1000001},{'offset':1.5},{'offset':'abc'},
    {'solution_id':'bad'},{'solution_id':'a'*33},{'solution_id':'a'*32}])
def test_invalid_campaign_parameters_422(params):
    async def check():
        token=(await call('POST','/api/optimize',{}))[2]['solution_id']
        assert (await call('GET','/api/campaign/customers',query=urlencode({'solution_id':token,**params})))[0]==422
    scenario(check)


@pytest.mark.parametrize('query',['','solution_id=bad','solution_id='+'f'*32,
    'solution_id='+'f'*32+'&action=invalid'])
def test_invalid_export_parameters_422(query):
    async def check():assert (await csv_call(query))[0]==422
    scenario(check)


def test_different_assumptions_keep_separate_cached_plans():
    async def check():
        a=(await call('POST','/api/optimize',{'m':0}))[2]
        b=(await call('POST','/api/optimize',{}))[2]
        assert a['solution_id']!=b['solution_id']
        rows=(await call('GET','/api/campaign/customers',query=urlencode({'solution_id':a['solution_id'],'action':'none'})))[2]
        assert rows['total']==40 and all(r['net_value']==0 for r in rows['rows'])
        assert (await call('GET','/api/campaign/customers',query=urlencode({'solution_id':a['solution_id'],'action':'coupon'})))[2]['rows']==[]
        assert b['counts']['coupon']>0
    scenario(check)


def test_missing_solution_id_on_list_returns_422():
    async def check():assert (await call('GET','/api/campaign/customers'))[0]==422
    scenario(check)


def test_export_rejects_invalid_action_with_valid_plan_and_handles_empty_filter():
    async def check():
        r=(await call('POST','/api/optimize',{'m':0}))[2]
        token=r['solution_id']
        assert (await csv_call(urlencode({'solution_id':token,'action':'invalid'})))[0]==422
        status,_,text=await csv_call(urlencode({'solution_id':token,'action':'coupon'}))
        assert status==200 and len(list(csv.DictReader(io.StringIO(text))))==0
    scenario(check)
