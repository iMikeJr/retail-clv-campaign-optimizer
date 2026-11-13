import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import MagicMock
import pytest
import main
from test_api import call,scenario,fixture_snapshot
from test_executive import fixture_executive


@pytest.fixture(autouse=True)
def snapshot(monkeypatch):
    def load():
        snapshot=fixture_snapshot();snapshot['executive']=fixture_executive();return snapshot
    monkeypatch.setattr(main,'load_snapshot',load)
    monkeypatch.setattr(main,'connect',lambda:MagicMock())


def test_all_executive_routes_and_country_filter():
    async def check():
        status,_,s=await call('GET','/api/exec/summary')
        assert status==200 and s['net_sales_12m']==280
        assert s['customers']==3 and s['sales_basis']=='net_sales'
        assert s['campaign_expected_profit']>0
        assert len((await call('GET','/api/sales/by-country'))[2]['rows'])==2
        assert (await call('GET','/api/sales/monthly'))[2]['total']==340
        assert (await call('GET','/api/products/top',query='country=France'))[2]['by_revenue'][0]['revenue']==200
        assert (await call('GET','/api/products/top',query="country=%27%3BDROP%20TABLE%20x%3B--"))[0]==404
        assert len((await call('GET','/api/cancellations/monthly'))[2]['rows'])==25
        assert len((await call('GET','/api/customers/loyalty-heatmap'))[2]['months'])==12
        r=(await call('GET','/api/customers',query='search=1&sort=expected_spend_90d&direction=desc&page=1'))[2]
        assert r['total']==1 and r['page_size']==25
    scenario(check)


@pytest.mark.parametrize('query',['sort=invoice;DROP','direction=invalid','page=0','page=-1'])
def test_customer_parameters_return_422(query):
    async def check():assert (await call('GET','/api/customers',query=query))[0]==422
    scenario(check)
