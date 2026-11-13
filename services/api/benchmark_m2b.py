"""M2b offline evidence from saved prediction fixtures; no new dependencies."""
import json
from pathlib import Path
import statistics
import sys
from optimizer import Customer,optimize,DEFAULT_BUDGET
from benchmark_optimizer import compact

rows=json.loads(Path(sys.argv[1]).read_text())
report={}
for run,records in rows.items():
    customers=[Customer(**r) for r in records]
    exact=optimize(customers,DEFAULT_BUDGET)
    timings=[]
    for _ in range(6):
        result=optimize(customers,DEFAULT_BUDGET,interactive=True,include_extra_100=False)
        timings.append(result["total_seconds"])
    report[run]={"exact":compact(exact),"interactive":compact(result),
                 "interactive_seconds":timings,"median_seconds":statistics.median(timings)}
Path(sys.argv[2]).write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
print(json.dumps({run:{"median_seconds":r["median_seconds"],"solver":r["interactive"]["solver"],
                      "by_action":r["exact"]["by_action"],"baselines":{k:v["net_value"] for k,v in r["exact"]["baselines"].items()},
                      "groups":r["exact"]["backtest"]} for run,r in report.items()}))
