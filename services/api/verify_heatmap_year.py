"""Live check of the heatmap year parameter against the API and Postgres (read-only)."""
import json
import os
import time
import urllib.error
import urllib.request

import psycopg

API=os.environ.get('API_URL','http://127.0.0.1:8000')
DSN=os.environ['HEATMAP_DSN']  # e.g. postgresql://user:password@127.0.0.1:5433/dbname
CUSTOMER='13902'


def get(query):
    start=time.perf_counter()
    with urllib.request.urlopen(f'{API}/api/customers/loyalty-heatmap?{query}',timeout=15) as r:
        return json.load(r),(time.perf_counter()-start)*1000


def main():
    default,_=get('')
    assert get('year=2011')[0]==default
    old,_=get('year=2010')
    assert old['months']==[f'2010-{m:02d}' for m in range(1,13)]
    assert [(r['customer_id'],r['loyalty_score']) for r in old['rows']]==[(r['customer_id'],r['loyalty_score']) for r in default['rows']]
    try:
        urllib.request.urlopen(f'{API}/api/customers/loyalty-heatmap?year=2009',timeout=15)
        raise AssertionError('year=2009 must be rejected')
    except urllib.error.HTTPError as error:
        assert error.code==422
    row=next(r for r in get(f'year=2010&customer_id={CUSTOMER}')[0]['rows'] if r['customer_id']==CUSTOMER)
    assert sum(row['monthly_spend'])>0,'13902 should have spend in 2010'
    with psycopg.connect(DSN) as connection:
        checked=0
        for customer in {r['customer_id'] for r in old['rows']}|{CUSTOMER}:
            page=next(r for r in get(f'year=2010&customer_id={customer}')[0]['rows'] if r['customer_id']==customer)
            expected=connection.execute('''SELECT coalesce(sum(line_value),0) FROM public.clean_transactions
                WHERE customer_id=%s AND invoice_date>=%s AND invoice_date<%s''',(customer,'2010-01-01','2011-01-01')).fetchone()[0]
            assert abs(sum(page['monthly_spend'])-float(expected))<.01,(customer,sum(page['monthly_spend']),expected)
            checked+=1
    latencies=[get(f'year={y}&offset={o}')[1] for y in (2010,2011) for o in range(0,200,10)]
    print({'customers_reconciled_to_database':checked,'spend_13902_2010':round(sum(row['monthly_spend']),2),
           'max_ms':round(max(latencies),1),'median_ms':round(sorted(latencies)[len(latencies)//2],1)})
    assert max(latencies)<300


if __name__=='__main__':
    main()
