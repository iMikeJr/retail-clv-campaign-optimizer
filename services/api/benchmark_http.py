"""Local stdlib HTTP timing probe. Does not change database or source results."""
import json
from pathlib import Path
import statistics
import sys
import time
import urllib.request

base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000'
output=Path(sys.argv[2] if len(sys.argv)>2 else 'docs/project-log/stage4_m3_http_benchmark.json')

def call(path,body=None):
    request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                                   headers={'Content-Type':'application/json'})
    start=time.perf_counter()
    with urllib.request.urlopen(request,timeout=60) as response:
        result=json.load(response)
    return result,time.perf_counter()-start

for _ in range(45):
    try:
        health,_=call('/health'); break
    except OSError:
        time.sleep(1)
else: raise RuntimeError('API did not become healthy')
defaults,_=call('/api/defaults')
runs,_=call('/api/runs')
uncached=[]
for i in range(6):
    result,seconds=call('/api/optimize',{'B':1682.11+i*.11})
    uncached.append({'seconds':seconds,'cache_hit':result['cache_hit'],'solver':result['solver']})
cached=[]
for _ in range(6):
    result,seconds=call('/api/optimize',{})
    cached.append({'seconds':seconds,'cache_hit':result['cache_hit'],'solver':result['solver']})
extra,extra_seconds=call('/api/optimize',{'include_extra_100':True})
sensitivity,warm_seconds=call('/api/sensitivity',{})
cold,cold_seconds=call('/api/sensitivity',{'budgets':[500.17,1000.17,1682.17,2500.17,3500.17]})
repeat,repeat_seconds=call('/api/sensitivity',{'budgets':[500.17,1000.17,1682.17,2500.17,3500.17]})
report={'health':health,'runs':[r['run_name'] for r in runs['runs']],
        'startup_precompute_seconds':defaults['precompute_seconds'],
        'uncached_optimize':uncached,'uncached_median_seconds':statistics.median(r['seconds'] for r in uncached),
        'cached_optimize':cached,'cached_median_seconds':statistics.median(r['seconds'] for r in cached),
        'optional_extra_100':{'seconds':extra_seconds,'result':extra['extra_100']},
        'default_sensitivity':{'seconds':warm_seconds,'response':sensitivity},
        'uncached_sensitivity':{'seconds':cold_seconds,'response':cold},
        'cached_sensitivity':{'seconds':repeat_seconds,'response':repeat}}
output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:report[k] for k in ('startup_precompute_seconds','uncached_median_seconds','cached_median_seconds')}))
print(json.dumps({'sensitivity_uncached_seconds':cold_seconds,'sensitivity_cached_seconds':repeat_seconds,'default_grid_new_solves':sensitivity['solves']}))
