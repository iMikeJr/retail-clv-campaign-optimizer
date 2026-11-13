"""Independent read-only SQL reconciliation of E1; writes only requested evidence."""
from datetime import date,timedelta
import json
import math
from pathlib import Path
import sys
import urllib.request

from main import connect


def main():
    with urllib.request.urlopen('http://api:8000/api/exec/summary',timeout=15) as response:
        summary=json.load(response)
    start=date.fromisoformat(summary['ranking_window']['start'])
    end=date.fromisoformat(summary['as_of'])+timedelta(days=1)
    query='''WITH valid_returns AS (
        SELECT *,row_number() OVER (PARTITION BY source_sheet,invoice,stockcode,description,quantity,
                  invoice_date,price,customer_id,country ORDER BY source_row) AS occurrence
        FROM public.raw_transactions WHERE upper(invoice) LIKE %s AND customer_id IS NOT NULL
             AND stockcode ~ %s AND quantity < 0 AND price > 0 AND invoice_date < %s),
    deduplicated AS (
        SELECT s.* FROM valid_returns s LEFT JOIN valid_returns f
            ON s.source_sheet = %s AND f.source_sheet = %s
            AND f.invoice=s.invoice AND f.stockcode=s.stockcode AND f.quantity=s.quantity
            AND f.invoice_date=s.invoice_date AND f.price=s.price AND f.customer_id=s.customer_id
            AND f.description IS NOT DISTINCT FROM s.description
            AND f.country IS NOT DISTINCT FROM s.country AND f.occurrence=s.occurrence
            WHERE f.occurrence IS NULL),
    sales AS (
        SELECT invoice,invoice_date,line_value FROM public.clean_transactions
        UNION ALL SELECT invoice,invoice_date,line_value FROM public.reversed_purchases),
    sale_dates AS (SELECT invoice,min(invoice_date)::date AS issued_on FROM sales
                  WHERE invoice_date < %s GROUP BY invoice),
    return_dates AS (SELECT invoice,min(invoice_date)::date AS issued_on FROM deduplicated GROUP BY invoice)
    SELECT (SELECT sum(line_value) FROM sales WHERE invoice_date < %s) AS gross_sales_full_history,
           (SELECT sum(-quantity*price) FROM deduplicated) AS returns_full_history,
           (SELECT sum(line_value) FROM sales WHERE invoice_date >= %s AND invoice_date < %s) AS gross_sales_12m,
           (SELECT sum(-quantity*price) FROM deduplicated WHERE invoice_date >= %s) AS returns_12m,
           (SELECT count(*) FROM sale_dates WHERE issued_on >= %s) AS sales_invoices_12m,
           (SELECT count(*) FROM return_dates WHERE issued_on >= %s) AS cancelled_invoices_12m,
           (SELECT count(*) FROM deduplicated) AS valid_return_lines,
           (SELECT count(*) FROM return_dates) AS valid_return_documents'''
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        values=conn.execute(query,('C%','^[0-9]{5}[A-Za-z]*$',end,'Year 2010-2011','Year 2009-2010',
                                  end,end,start,end,start,start,start)).fetchone()
        hashes=conn.execute('''SELECT
          (SELECT md5(string_agg(row_to_json(t)::text,'' ORDER BY run_id,model,metric,segment))
           FROM modeling.model_metrics t WHERE run_id IN
           (SELECT run_id FROM modeling.model_runs WHERE run_name = ANY(%s))) AS historical_metrics,
          (SELECT md5(string_agg(row_to_json(t)::text,'' ORDER BY run_id,model,customer_id))
           FROM modeling.customer_predictions t WHERE run_id IN
           (SELECT run_id FROM modeling.model_runs WHERE run_name = ANY(%s))) AS historical_predictions''',
           (['A','B','C','A_no_cap'],['A','B','C','A_no_cap'])).fetchone()
    values['net_sales_12m']=values['gross_sales_12m']-values['returns_12m']
    values['net_sales_full_history']=values['gross_sales_full_history']-values['returns_full_history']
    values['cancellation_rate_12m']=values['cancelled_invoices_12m']/(values['sales_invoices_12m']+values['cancelled_invoices_12m'])
    assert math.isclose(values['net_sales_12m'],summary['net_sales_12m'],abs_tol=.01)
    assert math.isclose(values['gross_sales_12m'],summary['gross_sales_12m'],abs_tol=.01)
    assert math.isclose(values['returns_12m'],summary['returns_12m'],abs_tol=.01)
    assert math.isclose(values['net_sales_full_history'],summary['net_sales_full_history'],abs_tol=.01)
    assert values['cancelled_invoices_12m']==summary['cancelled_invoices_12m']
    assert math.isclose(values['cancellation_rate_12m'],summary['cancellation_rate_12m'],abs_tol=1e-12)
    assert hashes['historical_metrics']=='04598d662434c62e47d08fd2d3f8f6fa'
    assert hashes['historical_predictions']=='b8d6623b46afe8035bb884c132667dbb'
    result={'independent_sql':values,'historical_hashes':hashes,'all_checks_passed':True}
    Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(f'Reconciliation failed ({type(error).__name__}); no connection details are logged.',file=sys.stderr)
        sys.exit(1)
