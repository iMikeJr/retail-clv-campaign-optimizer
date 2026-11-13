"""Read-only HTTP reconciliation and timings for paged views, country filter and CSV export; stdlib only."""
import csv
import io
import json
import math
from pathlib import Path
import statistics
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen

API='http://127.0.0.1:8000'
timings={}


def request(path,params=None,body=None,category='other',raw=False):
    url=API+path+('?' + urlencode(params) if params else '')
    r=Request(url,data=json.dumps(body).encode() if body is not None else None,
              headers={'Content-Type':'application/json'} if body is not None else {})
    tick=time.perf_counter()
    with urlopen(r,timeout=20) as response:
        content=response.read()
        assert response.status==200
    elapsed=(time.perf_counter()-tick)*1000
    timings.setdefault(category,[]).append(elapsed)
    return content.decode() if raw else json.loads(content)


def close(a,b):assert math.isclose(a,b,rel_tol=1e-10,abs_tol=.00001),(a,b)


def main():
    monthly=request('/api/sales/monthly',category='monthly')
    sums={r['month']:{k:0. for k in ('gross_sales','returns_value','net_sales')} for r in monthly['rows']}
    for country in monthly['countries']:
        data=request('/api/sales/monthly',{'country':country},category='monthly')
        assert [r['month'] for r in data['rows']]==list(sums)
        for row in data['rows']:
            for key in sums[row['month']]:sums[row['month']][key]+=row[key]
    for row in monthly['rows']:
        for key,value in sums[row['month']].items():close(value,row[key])
    loyalty=[]
    first=request('/api/customers/loyalty-heatmap',category='loyalty')
    for offset in range(0,first['total'],10):
        page=request('/api/customers/loyalty-heatmap',{'limit':10,'offset':offset},category='loyalty')
        assert page['total']==first['total'] and page['offset']==offset
        loyalty+=page['rows']
    assert len(loyalty)==len({r['customer_id'] for r in loyalty})==first['total']
    assert loyalty==sorted(loyalty,key=lambda r:(-r['loyalty_score'],r['customer_id']))
    assert first['rows']==loyalty[:10]
    last=loyalty[-1]['customer_id']
    jump=request('/api/customers/loyalty-heatmap',{'customer_id':last},category='loyalty')
    assert jump['highlight_id']==last and jump['offset']==(len(loyalty)-1)//10*10
    result=request('/api/optimize',body={},category='optimize_cached')
    assert 'assignments' not in result and len(result['top_selected'])<=15
    token=result['solution_id']
    totals={};campaign_all=[]
    for action in ['coupon','email','none','all']:
        params={'solution_id':token,'action':action,'limit':15,'offset':0}
        first_page=request('/api/campaign/customers',params,category='campaign_page')
        total=first_page['total'];rows=[]
        assert total==(sum(result['counts'].values()) if action=='all' else result['counts'][action])
        for offset in range(0,total,15):
            params['offset']=offset
            page=request('/api/campaign/customers',params,category='campaign_page')
            assert page['solution_id']==token and page['total']==total
            rows+=page['rows']
        assert rows==sorted(rows,key=lambda r:(-r['net_value'],r['customer_id']))
        assert len(rows)==len({r['customer_id'] for r in rows})==total
        assert all(action=='all' or r['action']==action for r in rows)
        text=request('/api/campaign/export',{'solution_id':token,'action':action},category='campaign_csv',raw=True)
        exported=list(csv.DictReader(io.StringIO(text)))
        assert len(exported)==total
        for row,export in zip(rows,exported):
            assert row['customer_id']==export['customer_id'] and row['action']==export['action']
            assert export['order_value']==f"{row['v']:.2f}" and export['expected_gain']==f"{row['net_value']:.2f}"
            assert export['expected_spend_90d']==f"{row['expected_spend_90d']:.2f}"
        totals[action]={'paginated_rows':len(rows),'csv_rows':len(exported)}
        if action=='all':campaign_all=rows
    # Compare all campaign context with the unchanged account endpoint.
    accounts={}
    for page in range(1,math.ceil(len(campaign_all)/25)+1):
        data=request('/api/customers',{'page':page},category='existing_customers')
        accounts.update({r['customer_id']:r for r in data['rows']})
    for row in campaign_all:
        account=accounts[row['customer_id']]
        assert account['days_since_last_purchase']==row['days_since_last_purchase']
        close(account['expected_spend_90d'],row['expected_spend_90d'])
    uncached=[]
    for budget in range(1692,2002):
        r=request('/api/optimize',body={'B':budget},category='optimize_probes')
        assert 'assignments' not in r and len(r['top_selected'])<=15
        if r['cache_hit']:
            continue
        timings.setdefault('optimize_uncached',[]).append(timings['optimize_probes'][-1])
        uncached.append({'budget':budget,'response_bytes':len(json.dumps(r)),'server_seconds':r['request_seconds']})
        if len(uncached)==10:
            break
    assert len(uncached)==10, 'Could not collect ten uncached requests'
    for _ in range(5):request('/api/optimize',body={},category='optimize_cached')
    summary={k:{'requests':len(v),'median_ms':statistics.median(v),'max_ms':max(v)} for k,v in timings.items()}
    for key in ['monthly','loyalty','campaign_page','campaign_csv']:assert summary[key]['max_ms']<300,(key,summary[key])
    assert summary['optimize_uncached']['max_ms']<1000,summary['optimize_uncached']
    assert math.isclose(result['net_value'],9122.550711942204,abs_tol=1e-8)
    output={'all_checks_passed':True,'country_count':len(monthly['countries']),'months_reconciled':len(monthly['rows']),
        'monthly_sum':monthly['total'],'loyalty_total':len(loyalty),'loyalty_first_ten_ids':[r['customer_id'] for r in first['rows']],
        'campaign':totals,'context_rows_matched':len(campaign_all),'default_profit':result['net_value'],
        'latency':summary,'uncached_slider_samples':uncached}
    Path('docs/project-log/stage5_phase2_http.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
