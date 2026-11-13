"""E1 read-only HTTP benchmark and real-data reconciliation; no new dependencies."""
import json
import math
from pathlib import Path
import statistics
import sys
import time
import urllib.request

base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000'
output=Path(sys.argv[2] if len(sys.argv)>2 else 'docs/project-log/stage5_e1_verification.json')
for _ in range(30):
    try:
        with urllib.request.urlopen(base+'/health',timeout=1):break
    except OSError:time.sleep(.5)
else:raise RuntimeError('API did not become healthy')
paths=['/api/exec/summary','/api/sales/by-country','/api/sales/monthly','/api/products/top',
       '/api/products/top?country=United%20Kingdom','/api/cancellations/monthly',
       '/api/customers/loyalty-heatmap','/api/customers',
       '/api/customers?search=123&sort=expected_spend_90d&direction=desc&page=1',
       '/api/customers?sort=probability_of_buying_90d&direction=desc&page=2']
responses={};timings={}
for path in paths:
    times=[]
    for attempt in range(11):
        tick=time.perf_counter()
        with urllib.request.urlopen(base+path,timeout=20) as response:
            data=json.load(response)
        seconds=time.perf_counter()-tick
        if attempt:times.append(seconds)
    responses[path]=data
    timings[path]={'warm_median_ms':statistics.median(times)*1000,'warm_max_ms':max(times)*1000,'repeats':len(times)}
summary=responses['/api/exec/summary'];countries=responses['/api/sales/by-country'];monthly=responses['/api/sales/monthly']
assert math.isclose(sum(r['net_sales'] for r in countries['rows']),summary['net_sales_12m'],abs_tol=.01)
assert math.isclose(sum(r['share'] for r in countries['rows']),1.,abs_tol=1e-10)
assert len(countries['rows'])==11 and countries['rows'][-1]['country']=='Other'
assert math.isclose(sum(r['net_sales'] for r in monthly['rows']),summary['net_sales_full_history'],abs_tol=.01)
assert math.isclose(sum(r['cancellation_value'] for r in responses['/api/cancellations/monthly']['rows']),
                    summary['reconciliation']['returns_full_history'],abs_tol=.01)
heatmap=responses['/api/customers/loyalty-heatmap']
assert len(heatmap['rows'])==25 and len(heatmap['months'])==12
assert all(len(row['monthly_spend'])==12 for row in heatmap['rows'])
customers=responses['/api/customers'];assert len(customers['rows'])==25
assert customers['total']==summary['customers']
assert all(item['warm_max_ms']<300 for item in timings.values())
output.write_text(json.dumps({'summary':summary,'countries':countries,'monthly':monthly,
                              'products':responses['/api/products/top'],'cancellations':responses['/api/cancellations/monthly'],
                              'loyalty_heatmap':heatmap,'customer_page':customers,'timings':timings,
                              'reconciliation_passed':True},indent=2,allow_nan=False)+'\n')
print(json.dumps({'summary':summary,'top5_countries':countries['rows'][:5],'loyalty_rows':len(heatmap['rows']),
                  'customer_examples':customers['rows'][:3],'timings':timings},indent=2))
