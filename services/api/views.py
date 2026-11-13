"""Parameterized read-only views over the API's immutable snapshot/cached plans.

SQLite is an in-memory index only: no source database/file is written. All
request values, including LIMIT/OFFSET and exact-ID searches, are SQL parameters.
"""
import csv
import io
import json
import math
import sqlite3
from threading import RLock


class PagedViews:
    def __init__(self, executive):
        self.lock = RLock()
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE monthly (country TEXT, month TEXT, gross_sales REAL,
                                  returns_value REAL, net_sales REAL);
            CREATE INDEX monthly_country ON monthly(country,month);
            CREATE TABLE loyalty (position INTEGER PRIMARY KEY, customer_id TEXT UNIQUE, payload TEXT);
            CREATE TABLE campaign (solution_id TEXT, customer_id TEXT, action TEXT,
                days_since_last_purchase INTEGER, expected_spend_90d REAL,
                v REAL, net_value REAL, PRIMARY KEY(solution_id,customer_id));
            CREATE INDEX campaign_rank ON campaign(solution_id,action,net_value DESC,customer_id);
        ''')
        self.executive = executive
        self.context = {r['customer_id']: r for r in executive.customers} if executive else {}
        self.heatmap_meta = {k:v for k,v in executive.heatmap.items() if k != 'rows'} if executive else {}
        with self.db:
            if executive:
                self.db.executemany('INSERT INTO monthly VALUES (?,?,?,?,?)', executive.monthly_country_rows)
                self.db.executemany('INSERT INTO loyalty VALUES (?,?,?)',
                    ((i,r['customer_id'],json.dumps(r)) for i,r in enumerate(executive.heatmap['rows'])))
        self.countries = [r[0] for r in self.db.execute('SELECT DISTINCT country FROM monthly ORDER BY country')]
        self.loyalty_total = self.db.execute('SELECT count(*) FROM loyalty').fetchone()[0]

    def monthly(self, country):
        with self.lock:
            rows = self.db.execute('''SELECT month,sum(gross_sales) gross_sales,
                sum(returns_value) returns_value,sum(net_sales) net_sales
                FROM monthly WHERE (? = '' OR country = ?) GROUP BY month ORDER BY month''',
                (country,country)).fetchall()
        by_month = {r['month']: dict(r) for r in rows}
        # Preserve the full-history month grid, even when a country has no sales.
        result = [{**by_month.get(r['month'],dict(month=r['month'],gross_sales=0.,returns_value=0.,net_sales=0.)),
                   'partial':r['partial']} for r in self.executive.monthly]
        return {'as_of':self.executive.as_of.isoformat(),'country':country,'countries':self.countries,
                'rows':result,'total':math.fsum(r['net_sales'] for r in result)}

    def loyalty(self, limit, offset, customer_id, year=None):
        with self.lock:
            match = self.db.execute('SELECT position FROM loyalty WHERE customer_id = ?', (customer_id,)).fetchone() if customer_id else None
            if match is not None:
                offset = (match['position']//limit)*limit
            rows = self.db.execute('SELECT payload FROM loyalty ORDER BY position LIMIT ? OFFSET ?', (limit,offset)).fetchall()
        rows = [json.loads(r['payload']) for r in rows]
        meta = self.heatmap_meta
        alternative = self.executive.heatmap_years.get(year) if year is not None else None
        if alternative:
            # Only the month columns change; ranking fields and order stay as stored.
            rows = [{**r,'monthly_spend':alternative['spend'][r['customer_id']]} for r in rows]
            meta = {**meta,**{k:alternative[k] for k in ('months','display_start','display_end','note')}}
        return {**meta,'as_of':self.executive.as_of.isoformat(),
                'rows':rows,
                'limit':limit,'offset':offset,'total':self.loyalty_total,
                'found':match is not None if customer_id else None,
                'highlight_id':customer_id if match is not None else None}

    def store_campaign(self, solution_id, assignments):
        def records():
            for row in assignments:
                c = self.context.get(row['customer_id'], {})
                yield (solution_id,row['customer_id'],row['action'],c.get('days_since_last_purchase'),
                       c.get('expected_spend_90d'),row['v'],row['net_value'])
        with self.lock, self.db:
            self.db.executemany('INSERT INTO campaign VALUES (?,?,?,?,?,?,?)', records())

    def discard_campaign(self, solution_id):
        with self.lock, self.db:
            self.db.execute('DELETE FROM campaign WHERE solution_id = ?', (solution_id,))

    def campaign(self, solution_id, action, limit=None, offset=0):
        params = (solution_id,action,action)
        where = "solution_id = ? AND (? = 'all' OR action = ?)"
        # Only fixed SQL fragments are composed here; every request value is bound.
        with self.lock:
            total = self.db.execute('SELECT count(*) FROM campaign WHERE '+where, params).fetchone()[0]
            query = 'SELECT customer_id,action,days_since_last_purchase,expected_spend_90d,v,net_value FROM campaign WHERE '+where+' ORDER BY net_value DESC,customer_id'
            if limit is not None:
                query += ' LIMIT ? OFFSET ?'
                params += (limit,offset)
            rows = [dict(r) for r in self.db.execute(query,params).fetchall()]
        return {'solution_id':solution_id,'context_as_of':self.executive.as_of.isoformat() if self.executive else None,'action':action,'limit':limit,'offset':offset,'total':total,'rows':rows}

    def campaign_csv(self, solution_id, action):
        result = self.campaign(solution_id,action)
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['customer_id','action','days_since_last_purchase','expected_spend_90d','order_value','expected_gain'])
        for row in result['rows']:
            writer.writerow([row['customer_id'],row['action'],row['days_since_last_purchase'],
                '' if row['expected_spend_90d'] is None else f"{row['expected_spend_90d']:.2f}",
                f"{row['v']:.2f}",f"{row['net_value']:.2f}"])
        return output.getvalue()
