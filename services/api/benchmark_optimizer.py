"""Read-only DB benchmark; writes evidence only to the explicitly requested file.

Run inside the API image with its standard POSTGRES_* environment. Never logs
connection details or exceptions containing credentials. No web server needed.
"""
import argparse
from dataclasses import asdict
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

from optimizer import (Assumptions,Customer,DEFAULT_BUDGET,DEFAULT_MAX_COUPONS,
                       choose_default_budget,optimize)


def load_customers():
    import psycopg
    with psycopg.connect(host=os.environ["POSTGRES_HOST"], dbname=os.environ["POSTGRES_DB"],
                        user=os.environ["POSTGRES_USER"],password=os.environ["POSTGRES_PASSWORD"],
                        connect_timeout=3,options="-c statement_timeout=10000") as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows=conn.execute('''SELECT r.run_name,p.customer_id,p."p_purchase_N",p.expected_order_value,p.actual_spend
                            FROM modeling.customer_predictions p JOIN modeling.model_runs r USING(run_id)
                            WHERE r.run_name IN (%s,%s) AND p.model=%s
                            ORDER BY r.run_name,p.customer_id''',("A","PROD","bgnbd")).fetchall()
    result={run:[] for run in ("A","PROD")}
    for run,*row in rows:
        result[run].append(Customer(*row))
    if not all(result.values()):
        raise ValueError("Both A and PROD must exist before benchmarking")
    return result


def compact(result):
    result=dict(result)
    result.pop("assignments")
    result["baseline"]=dict(result["baseline"])
    result["baseline"].pop("assignments")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,help="Optional JSON fixture instead of DB")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--choose-default",action="store_true")
    parser.add_argument("--run",choices=("PROD","A"),help="Benchmark just one run in this process")
    args=parser.parse_args()
    if args.run is None and not args.choose_default:
        # Each dataset gets its own fresh process and first solve; imports and
        # data loading are excluded from optimizer timings in both cases.
        with tempfile.TemporaryDirectory(prefix="campaign-benchmark-") as directory:
            combined = None
            for run in ("PROD","A"):
                output = Path(directory)/f"{run}.json"
                command = [sys.executable,__file__,"--run",run,"--output",str(output)]
                if args.input:
                    command.extend(["--input",str(args.input)])
                child = subprocess.run(command,capture_output=True,text=True)
                if child.returncode:
                    raise RuntimeError("Isolated benchmark process failed")
                print(child.stdout,end="",flush=True)
                report=json.loads(output.read_text())
                if combined is None:
                    combined=report
                else:
                    combined["runs"].update(report["runs"])
            args.output.write_text(json.dumps(combined,indent=2,allow_nan=False)+"\n")
        return
    customers=({run:[Customer(**x) for x in rows] for run,rows in json.loads(args.input.read_text()).items()}
               if args.input else load_customers())
    report={"python":platform.python_version(),"platform":platform.platform(),
            "versions":{p:version(p) for p in ("ortools","pandas","numpy")},
            "assumptions":asdict(Assumptions()),"B":DEFAULT_BUDGET,"K":DEFAULT_MAX_COUPONS,
            "model":"bgnbd","runs":{}}
    if args.choose_default:
        default=choose_default_budget(customers["PROD"])
        default.pop("result")
        args.output.write_text(json.dumps(default,indent=2)+"\n")
        print(json.dumps(default))
        return
    for run in ([args.run] if args.run else ("PROD","A")):
        timings=[]
        first_assignments=None
        for attempt in range(6):
            start=time.perf_counter()
            result=optimize(customers[run],DEFAULT_BUDGET)
            timings.append({"attempt":attempt,"base_solve_seconds":result["solver"]["seconds"],
                            "extra_solve_seconds":result["extra_100"]["solver"]["seconds"],
                            "campaign_seconds":time.perf_counter()-start,
                            "status":result["solver"]["status"],
                            "extra_status":result["extra_100"]["solver"]["status"]})
            assignment=[(a["customer_id"],a["action"]) for a in result["assignments"]]
            if first_assignments is None:
                first_assignments=assignment
                saved=compact(result)
            elif first_assignments!=assignment:
                raise RuntimeError("Repeated real-data solves returned different assignments")
        warm=timings[1:]
        report["runs"][run]={"eligible_customers":len(customers[run]),"result":saved,
                             "timings":timings,"assignments_identical":True,
                             "warm_median_base_solve_seconds":statistics.median(t["base_solve_seconds"] for t in warm),
                             "warm_median_campaign_seconds":statistics.median(t["campaign_seconds"] for t in warm)}
        print(json.dumps({"run":run,"counts":saved["counts"],"solver":saved["solver"],"timings":timings}),flush=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    try:
        main()
    except Exception as error:
        print(f"Benchmark failed ({type(error).__name__}); check inputs and configuration.",file=sys.stderr)
        sys.exit(1)
