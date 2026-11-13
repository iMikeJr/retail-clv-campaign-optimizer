"""Hand-computed fixture: overlap copies, retained repeats and quick reversals."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import date
import copy

import pandas as pd
import pytest

from executive import ExecutiveAnalytics,PRIMARY_RULES,deduplicate_cancellations


def fixture_inputs():
    sales=[dict(month='2009-12-01',country='United States',in_last_12m=False,gross_sales=50.),
           dict(month='2010-12-01',country='United Kingdom',in_last_12m=False,gross_sales=10.),
           dict(month='2010-12-01',country='United Kingdom',in_last_12m=True,gross_sales=20.),
           dict(month='2011-01-01',country='United Kingdom',in_last_12m=True,gross_sales=120.),
           dict(month='2011-06-01',country='France',in_last_12m=True,gross_sales=200.)]
    products=[dict(country='United Kingdom',stockcode='10000',description='Item A',units=14,revenue=140.),
              dict(country='France',stockcode='20000',description='Item B',units=20,revenue=200.)]
    invoices=[dict(month=r['month'],in_last_12m=r['in_last_12m'],sales_invoices=2 if r['month']=='2011-01-01' else 1)
              for r in sales]
    daily=[dict(customer_id='1',purchase_date=d,purchase_value=v) for d,v in
           [('2010-12-09',10.),('2010-12-10',20.),('2011-01-05',100.)]]
    daily.extend([dict(customer_id='2',purchase_date='2011-06-01',purchase_value=200.),
                  dict(customer_id='3',purchase_date='2009-12-01',purchase_value=50.)])
    template=dict(invoice='C1',stockcode='10000',description=None,quantity=-2,invoice_date='2011-01-06',
                  price=10.,customer_id='1',country='United Kingdom')
    raw=[]
    for sheet,n in [('Year 2009-2010',2),('Year 2010-2011',3)]:
        raw.extend(dict(template,source_sheet=sheet,source_row=i+2) for i in range(n))
    raw.extend([dict(template,invoice='C2',stockcode='M',quantity=-1,price=5.,source_sheet='Year 2009-2010',source_row=8),
                dict(template,invoice='C3',customer_id=None,source_sheet='Year 2009-2010',source_row=9)])
    rfm=[dict(customer_id='1',frequency=2,recency=27,T=365,monetary_value=60.,cutoff_date=date(2011,12,9)),
         dict(customer_id='2',frequency=0,recency=0,T=191,monetary_value=0.,cutoff_date=date(2011,12,9)),
         dict(customer_id='3',frequency=0,recency=0,T=738,monetary_value=0.,cutoff_date=date(2011,12,9))]
    quality=[dict(rule=key,unit='rows',standalone_rows=0,removed_rows=0,removed_line_value=0.) for key in PRIMARY_RULES]
    for q in quality:
        q['removed_rows']={'1_overlap_duplicates':2,'3_missing_customer_id':1,'4_cancellations':4,'7_quick_reversals':1}.get(q['rule'],0)
        if q['rule']=='7_quick_reversals':q['removed_line_value']=20.
    audit=dict(raw_rows=13,clean_rows=5,clean_sales=380.,reversed_rows=1,reversed_sales=20.,data_end=date(2011,12,9))
    predictions=[dict(run_name='PROD',model='bgnbd',customer_id=c,p_purchase_N=p,expected_order_value=v,
                      expected_purchases_N=n,bgnbd_clv_N=n*v) for c,p,v,n in [('1',.8,100.,2.),('2',.4,200.,1.),('3',.1,50.,.25)]]
    return dict(sales=sales,products=products,invoices=invoices,daily=daily,raw_returns=raw,rfm=rfm,
                quality=quality,audit=audit,predictions=predictions,as_of=date(2011,12,9))


def fixture_executive():return ExecutiveAnalytics(**fixture_inputs())


def test_overlap_drops_only_matched_second_sheet_copies_and_keeps_repeats():
    source=pd.DataFrame(fixture_inputs()['raw_returns'])
    kept,removed=deduplicate_cancellations(source)
    assert removed==2
    assert len(kept.loc[kept.invoice.eq('C1')])==3
    assert kept.loc[kept.invoice.eq('C1'),'description'].isna().all()


def test_net_sales_reconcile_and_reversals_are_not_subtracted_twice():
    data=fixture_executive();s=data.summary()
    assert s['net_sales_12m']==280
    assert s['net_sales_full_history']==340
    assert s['reconciliation']['gross_sales_full_history']==400
    assert s['reconciliation']['returns_full_history']==60
    assert sum(r['net_sales'] for r in data.monthly)==340
    assert sum(r['net_sales'] for r in data.countries)==280
    assert sum(r['share'] for r in data.countries)==pytest.approx(1)
    assert data.countries[0]['country']=='France'
    assert data.countries[0]['share']==pytest.approx(200/280)
    assert data.product_total==280
    assert data.products[None]['by_revenue'][0]['stockcode']=='20000'
    assert data.products['United Kingdom']['by_units'][0]['units']==8


def test_cancellation_rate_counts_documents_not_lines():
    data=fixture_executive()
    january=next(r for r in data.cancellations if r['month']=='2011-01')
    assert january['cancelled_invoices']==1
    assert january['total_invoices']==3
    assert january['cancellation_value']==60
    assert january['cancellation_rate']==pytest.approx(1/3)
    assert data.invoice_totals['cancellation_rate_12m']==.2
    assert len(data.cancellations)==25


def test_customers_keep_dormant_accounts_and_use_stored_rfm_and_count_clv():
    data=fixture_executive()
    assert data.rfm_source=='customer_rfm'
    rows=data.customer_page('', 'customer_id','asc',1)['rows']
    assert len(rows)==3
    assert rows[0]['days_since_last_purchase']==338
    assert rows[0]['number_of_purchases']==3
    assert rows[0]['customer_age_days']==365
    assert rows[0]['expected_spend_90d']==200
    assert rows[0]['expected_spend_90d']!=.8*100
    assert rows[2]['days_since_last_purchase']==738
    assert data.active_customers_12m==2
    assert data.customer_page('2','customer_id','asc',1)['total']==1
    assert data.customer_page("%';--",'customer_id','asc',1)['total']==0
    assert data.customer_page('','customer_id','asc',2)['rows']==[]
    assert data.customer_page('','probability_of_buying_90d','desc',1)['rows'][0]['customer_id']=='1'


def test_loyalty_rolling_window_includes_boundary_and_heatmap_has_12_columns():
    data=fixture_executive()
    assert data.heatmap['rank_window']['start']=='2010-12-10'
    assert data.heatmap['months']==[f'2011-{m:02d}' for m in range(1,13)]
    rows=data.heatmap['rows']
    assert [r['customer_id'] for r in rows]==['2','1','3']
    one=next(r for r in rows if r['customer_id']=='1')
    assert one['spend_12m']==120 and one['purchase_days_12m']==2
    assert one['monthly_spend'][0]==100
    assert all(len(r['monthly_spend'])==12 for r in rows)
    assert rows[-1]['loyalty_score']==3


def test_mismatched_rfm_cutoff_recomputes_without_writing():
    inputs=fixture_inputs()
    for r in inputs['rfm']:r['cutoff_date']=date(2011,6,1);r['T']=0
    data=ExecutiveAnalytics(**inputs)
    assert data.rfm_source.startswith('clean_transactions')
    assert data.customers[0]['days_since_last_purchase']==338


@pytest.mark.parametrize('kind',['quality','forecast','sales'])
def test_bad_reconciliation_stops_snapshot(kind):
    inputs=copy.deepcopy(fixture_inputs())
    if kind=='quality':inputs['audit']['clean_rows']+=1
    if kind=='forecast':inputs['predictions'][0]['bgnbd_clv_N']+=1
    if kind=='sales':inputs['products'][0]['revenue']+=1
    with pytest.raises(ValueError):ExecutiveAnalytics(**inputs)


def test_identical_rfm_values_keep_equal_scores_and_id_breaks_final_tie():
    inputs=fixture_inputs()
    inputs['sales']=[r for r in inputs['sales'] if not (r['month']=='2010-12-01' and r['in_last_12m'])]
    for r in inputs['sales']:
        if r['country']=='France':r.update(month='2011-01-01',gross_sales=100.)
    inputs['invoices']=[dict(month=r['month'],in_last_12m=r['in_last_12m'],
                             sales_invoices=2 if r['country']=='United Kingdom' and r['month']=='2011-01-01' else 1)
                        for r in inputs['sales']]
    inputs['daily']=[r for r in inputs['daily'] if r['purchase_date']!='2010-12-10']
    for r in inputs['daily']:
        if r['customer_id']=='2':r.update(purchase_date='2011-01-05',purchase_value=100.)
    inputs['rfm'][0].update(frequency=1,monetary_value=100.)
    inputs['rfm'][1]['T']=338
    inputs['products'][0].update(units=12,revenue=120.)
    inputs['products'][1].update(units=10,revenue=100.)
    inputs['audit'].update(raw_rows=12,clean_rows=4,clean_sales=260.)
    data=ExecutiveAnalytics(**inputs)
    first,second=data.heatmap['rows'][:2]
    assert (first['customer_id'],second['customer_id'])==('1','2')
    assert first['loyalty_score']==second['loyalty_score']==15
    assert (first['R'],first['F'],first['M'])==(second['R'],second['F'],second['M'])


def test_pagination_returns_25_rows_and_preserves_final_partial_page():
    data=fixture_executive()
    # Exercise pagination independently of the financial fixture's three customers.
    data.sorted_customers['customer_id','asc']=[dict(data.customers[0],customer_id=f'{i:03}') for i in range(55)]
    assert len(data.customer_page('','customer_id','asc',1)['rows'])==25
    assert data.customer_page('','customer_id','asc',2)['rows'][0]['customer_id']=='025'
    last=data.customer_page('','customer_id','asc',3)
    assert len(last['rows'])==5 and last['total']==55 and last['pages']==3
    assert data.customer_page('','customer_id','asc',4)['rows']==[]


def test_missing_country_is_an_explicit_bucket_and_totals_are_preserved():
    inputs=fixture_inputs()
    for collection in ('sales','products','raw_returns'):
        for row in inputs[collection]:
            if row['country']=='United Kingdom':row['country']=None
    data=ExecutiveAnalytics(**inputs)
    assert next(r['net_sales'] for r in data.countries if r['country']=='Unknown')==80
    assert data.summary()['net_sales_12m']==280
    assert data.products['Unknown']['by_revenue'][0]['revenue']==80
