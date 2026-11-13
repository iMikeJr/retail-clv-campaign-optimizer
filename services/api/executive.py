"""Read-only executive aggregates. No ETL/model writes, fitting or campaign changes."""
from datetime import timedelta
import math

import numpy as np
import pandas as pd

RAW_COLUMNS = ['invoice','stockcode','description','quantity','invoice_date','price','customer_id','country']
PRIMARY_RULES = ['1_overlap_duplicates','2_repeated_lines_within_sheet','3_missing_customer_id',
                 '4_cancellations','5_nonpositive_quantity_or_price','6_nonproduct_stockcode','7_quick_reversals']
CUSTOMER_SORTS = ('customer_id','days_since_last_purchase','number_of_purchases','customer_age_days',
                  'probability_of_buying_90d','expected_spend_90d')
FOOTNOTES = {
    'sales':'Net sales are product sales less valid returns for known customers, with overlapping source entries counted once; revenue is not profit.',
    'population':'Lines without customer IDs and non-product codes are excluded, following the ETL population. Customer panels use retained clean purchases.',
    'rankings':'Rankings use the rolling 12 months ending at the scoring date; December is partial. Sales and cancellation trends use the whole history.',
    'cancellations':'Cancellation rate counts return invoices, which can represent partial returns; it is not the percentage of original orders fully cancelled.',
    'loyalty':'Loyalty combines how recently, how often and how much a customer bought over the rolling year; ties use customer ID. Heatmap columns show the latest 12 calendar months.',
    'customer_history':'A purchase is one customer-day; customer age starts at the first observed clean purchase. Dormant customers remain listed.',
    'customer_forecasts':'Expected spend allows repeat purchases; it is not profit or the extra sales caused by an offer.'
}


def deduplicate_cancellations(raw):
    """ETL overlap_mask projected onto C invoices; invoice is part of the key.

    Same eight-value identity, per-sheet occurrence and second-sheet-only drop.
    Restricting to C invoices cannot change any match because invoice is a key.
    Within-sheet repeats are deliberately retained; NULL keys match as in ETL.
    """
    raw=raw.sort_values(['source_sheet','source_row']).copy()
    raw['occurrence']=raw.groupby(['source_sheet',*RAW_COLUMNS],dropna=False,sort=False).cumcount()
    keys=[*RAW_COLUMNS,'occurrence']
    first=raw.loc[raw.source_sheet.eq('Year 2009-2010'),keys]
    second=raw.loc[raw.source_sheet.eq('Year 2010-2011')]
    matches=second.merge(first,on=keys,how='left',indicator=True,validate='one_to_one')
    drop=second.index[matches['_merge'].eq('both').to_numpy()]
    return raw.drop(index=drop).drop(columns='occurrence'),len(drop)


def load_executive(connection,predictions,as_of):
    """Called inside main.load_snapshot's existing REPEATABLE READ READ ONLY tx."""
    as_of=pd.Timestamp(as_of).date()
    start=(pd.Timestamp(as_of)-pd.DateOffset(years=1)+pd.Timedelta(days=1)).date()
    end=as_of+timedelta(days=1)
    # Restoring reversed_purchases before subtracting returns prevents double debit.
    sales=connection.execute('''WITH sales AS (
        SELECT invoice_date,country,line_value FROM public.clean_transactions
        UNION ALL SELECT invoice_date,country,line_value FROM public.reversed_purchases)
        SELECT date_trunc('month',invoice_date)::date AS month,country,
               invoice_date::date >= %s AS in_last_12m,sum(line_value) AS gross_sales
        FROM sales WHERE invoice_date < %s GROUP BY 1,2,3''',(start,end)).fetchall()
    products=connection.execute('''WITH sales AS (
        SELECT invoice_date,country,stockcode,description,quantity,line_value FROM public.clean_transactions
        UNION ALL SELECT invoice_date,country,stockcode,description,quantity,line_value FROM public.reversed_purchases)
        SELECT country,stockcode,max(description) AS description,sum(quantity)::bigint AS units,sum(line_value) AS revenue
        FROM sales WHERE invoice_date >= %s AND invoice_date < %s GROUP BY country,stockcode''',(start,end)).fetchall()
    invoices=connection.execute('''WITH sales AS (
        SELECT invoice,invoice_date FROM public.clean_transactions
        UNION ALL SELECT invoice,invoice_date FROM public.reversed_purchases), issued AS (
        SELECT invoice,min(invoice_date)::date AS issued_on FROM sales WHERE invoice_date < %s GROUP BY invoice)
        SELECT date_trunc('month',issued_on)::date AS month,issued_on >= %s AS in_last_12m,
               count(*) AS sales_invoices FROM issued GROUP BY 1,2''',(end,start)).fetchall()
    daily=connection.execute('''WITH invoices AS (
        SELECT customer_id,invoice,min(invoice_date)::date AS purchase_date,sum(line_value) AS purchase_value
        FROM public.clean_transactions WHERE invoice_date < %s GROUP BY customer_id,invoice)
        SELECT customer_id,purchase_date,sum(purchase_value) AS purchase_value
        FROM invoices GROUP BY customer_id,purchase_date ORDER BY customer_id,purchase_date''',(end,)).fetchall()
    raw_returns=connection.execute('''SELECT invoice,stockcode,description,quantity,invoice_date,price,
        customer_id,country,source_sheet,source_row FROM public.raw_transactions
        WHERE upper(invoice) LIKE %s ORDER BY source_sheet,source_row''',('C%',)).fetchall()
    rfm=connection.execute('SELECT customer_id,frequency,recency,"T",monetary_value,cutoff_date FROM public.customer_rfm').fetchall()
    quality=connection.execute('SELECT rule,unit,standalone_rows,removed_rows,removed_line_value FROM public.data_quality_report').fetchall()
    audit=connection.execute('''SELECT (SELECT count(*) FROM public.raw_transactions) AS raw_rows,
        (SELECT count(*) FROM public.clean_transactions) AS clean_rows,
        (SELECT sum(line_value) FROM public.clean_transactions) AS clean_sales,
        (SELECT count(*) FROM public.reversed_purchases) AS reversed_rows,
        (SELECT sum(line_value) FROM public.reversed_purchases) AS reversed_sales,
        (SELECT max(invoice_date)::date FROM public.raw_transactions) AS data_end''').fetchone()
    return ExecutiveAnalytics(sales=sales,products=products,invoices=invoices,daily=daily,
                              raw_returns=raw_returns,rfm=rfm,quality=quality,audit=audit,
                              predictions=predictions,as_of=as_of)


class ExecutiveAnalytics:
    def __init__(self,*,sales,products,invoices,daily,raw_returns,rfm,quality,audit,predictions,as_of):
        self.as_of=pd.Timestamp(as_of).date()
        self.start=(pd.Timestamp(self.as_of)-pd.DateOffset(years=1)+pd.Timedelta(days=1)).date()
        self.window={'start':self.start.isoformat(),'end':self.as_of.isoformat()}
        sales=pd.DataFrame(sales,columns=['month','country','in_last_12m','gross_sales'])
        sales['month']=pd.to_datetime(sales.month)
        sales['country']=sales.country.fillna('Unknown')
        returns,overlap_removed=deduplicate_cancellations(pd.DataFrame(raw_returns,columns=[*RAW_COLUMNS,'source_sheet','source_row']))
        returns['invoice_date']=pd.to_datetime(returns.invoice_date)
        self.reconciliation=self._audit(audit,quality,returns,overlap_removed)
        returns=returns.loc[returns.invoice_date.lt(pd.Timestamp(self.as_of)+pd.Timedelta(days=1))
                            & returns.customer_id.notna() & returns.stockcode.str.fullmatch(r'[0-9]{5}[A-Za-z]*',na=False)
                            & returns.quantity.lt(0) & returns.price.gt(0)].copy()
        returns['country']=returns.country.fillna('Unknown')
        returns['return_value']=-returns.quantity*returns.price
        returns['month']=returns.invoice_date.dt.to_period('M').dt.to_timestamp()
        returns['in_last_12m']=returns.invoice_date.ge(pd.Timestamp(self.start))
        keys=['month','country','in_last_12m']
        credits=returns.groupby(keys,dropna=False,as_index=False).agg(returns_value=('return_value','sum'))
        facts=sales.merge(credits,on=keys,how='outer').fillna({'gross_sales':0.,'returns_value':0.})
        facts['net_sales']=facts.gross_sales-facts.returns_value
        last_year=facts.loc[facts.in_last_12m]
        self._net_history=float(facts.net_sales.sum())
        self._net_12m=float(last_year.net_sales.sum())
        self._gross_12m=float(last_year.gross_sales.sum())
        self._returns_12m=float(last_year.returns_value.sum())
        self._gross_history=float(facts.gross_sales.sum())
        self._returns_history=float(facts.returns_value.sum())
        months=pd.date_range(facts.month.min(),pd.Timestamp(self.as_of).replace(day=1),freq='MS')
        monthly=facts.groupby('month')[['gross_sales','returns_value','net_sales']].sum().reindex(months,fill_value=0)
        self.monthly=[{'month':month.strftime('%Y-%m'),**{key:float(row[key]) for key in monthly.columns},
                       'partial':month.year==self.as_of.year and month.month==self.as_of.month}
                      for month,row in monthly.iterrows()]
        grouped=facts.groupby(['country','month'])[['gross_sales','returns_value','net_sales']].sum().reset_index()
        self.monthly_country_rows=[(str(r.country),r.month.strftime('%Y-%m'),float(r.gross_sales),float(r.returns_value),float(r.net_sales)) for r in grouped.itertuples()]
        countries=last_year.groupby('country',as_index=False).net_sales.sum().sort_values(['net_sales','country'],ascending=[False,True])
        self.country_all=[{'country':row.country,'net_sales':float(row.net_sales),
                           'share':float(row.net_sales)/self._net_12m if self._net_12m else None}
                          for row in countries.itertuples()]
        self.countries=self.country_all[:10]
        if len(self.country_all)>10:
            other=math.fsum(row['net_sales'] for row in self.country_all[10:])
            self.countries.append({'country':'Other','net_sales':other,'share':other/self._net_12m if self._net_12m else None})
        self.products=self._products(products,returns)
        self.cancellations,self.invoice_totals=self._cancellations(invoices,returns,months)
        self.customers,self.heatmap,self.rfm_source=self._customers(daily,rfm,predictions)
        self.sorted_customers={}
        for key in CUSTOMER_SORTS:
            ordered=sorted(self.customers,key=lambda r:r['customer_id'])
            for direction in ('asc','desc'):
                self.sorted_customers[key,direction]=sorted(ordered,key=lambda r:r[key],reverse=direction=='desc')
        self._reconcile_totals(audit)

    def _audit(self,audit,quality,cancellations,overlap_removed):
        q={row['rule']:row for row in quality}
        if audit['raw_rows']-sum(q[key]['removed_rows'] for key in PRIMARY_RULES)!=audit['clean_rows']:
            raise ValueError('Executive raw/clean rows do not reconcile to the ETL quality report')
        if audit['reversed_rows']!=q['7_quick_reversals']['removed_rows'] or not math.isclose(
            audit['reversed_sales'] or 0,q['7_quick_reversals']['removed_line_value'],abs_tol=.01):
            raise ValueError('Executive reversed purchases do not reconcile to the ETL quality report')
        known=len(cancellations.loc[cancellations.customer_id.notna()])
        if known!=q['4_cancellations']['removed_rows']:
            raise ValueError('Deduplicated cancellation rows do not match ETL rule 4')
        return {'raw_rows':audit['raw_rows'],'clean_rows':audit['clean_rows'],
                'overlap_rows_removed':q['1_overlap_duplicates']['removed_rows'],
                'cancellation_overlap_rows_removed':overlap_removed,'known_customer_cancellation_rows':known,
                'clean_sales_full_history':float(audit['clean_sales'] or 0),
                'restored_quick_reversal_sales':float(audit['reversed_sales'] or 0),
                'restored_quick_reversal_rows':audit['reversed_rows'],'quality_report_matched':True}

    def _products(self,products,returns):
        gross=pd.DataFrame(products,columns=['country','stockcode','description','units','revenue'])
        gross['country']=gross.country.fillna('Unknown')
        credits=returns.loc[returns.in_last_12m].groupby(['country','stockcode'],as_index=False).agg(
            return_units=('quantity','sum'),return_value=('return_value','sum'),return_description=('description','max'))
        combined=gross.merge(credits,on=['country','stockcode'],how='outer')
        combined['description']=combined.description.fillna(combined.return_description).fillna('Description unavailable')
        for col in ('units','revenue','return_units','return_value'):
            combined[col]=combined[col].fillna(0)
        combined['units']+=combined.return_units
        combined['revenue']-=combined.return_value
        result={}
        for country in [None,*sorted(set(combined.country))]:
            group=combined if country is None else combined.loc[combined.country.eq(country)]
            aggregate=group.groupby('stockcode',as_index=False).agg(description=('description','max'),
                          revenue=('revenue','sum'),units=('units','sum'))
            def ranked(key):
                return [{'stockcode':r.stockcode,'description':r.description,'revenue':float(r.revenue),'units':int(r.units)}
                        for r in aggregate.sort_values([key,'stockcode'],ascending=[False,True]).head(10).itertuples()]
            result[country]={'country':country,'by_revenue':ranked('revenue'),'by_units':ranked('units')}
        self.product_total=float(combined.revenue.sum())
        return result

    def _cancellations(self,invoices,returns,months):
        sales=pd.DataFrame(invoices,columns=['month','in_last_12m','sales_invoices'])
        sales['month']=pd.to_datetime(sales.month)
        issued=returns.groupby('invoice',as_index=False).agg(issued_on=('invoice_date','min'))
        issued['month']=issued.issued_on.dt.to_period('M').dt.to_timestamp()
        cancel_counts=issued.groupby('month').size()
        sales_counts=sales.groupby('month').sales_invoices.sum()
        values=returns.groupby('month').return_value.sum()
        records=[]
        for month in months:
            n_cancel=int(cancel_counts.get(month,0));n_sales=int(sales_counts.get(month,0))
            records.append({'month':month.strftime('%Y-%m'),'cancelled_invoices':n_cancel,
                            'sales_invoices':n_sales,'total_invoices':n_cancel+n_sales,
                            'cancellation_value':float(values.get(month,0)),
                            'cancellation_rate':n_cancel/(n_cancel+n_sales) if n_cancel+n_sales else None,
                            'partial':month.year==self.as_of.year and month.month==self.as_of.month})
        cancel_year=int(issued.issued_on.ge(pd.Timestamp(self.start)).sum())
        sales_year=int(sales.loc[sales.in_last_12m,'sales_invoices'].sum())
        return records,{'cancelled_invoices_12m':cancel_year,'total_invoices_12m':cancel_year+sales_year,
                        'cancellation_rate_12m':cancel_year/(cancel_year+sales_year) if cancel_year+sales_year else None}

    def _customers(self,daily,rfm,predictions):
        daily=pd.DataFrame(daily,columns=['customer_id','purchase_date','purchase_value'])
        daily['purchase_date']=pd.to_datetime(daily.purchase_date)
        stored=pd.DataFrame(rfm)
        asof=pd.Timestamp(self.as_of)
        if not stored.empty and pd.to_datetime(stored.cutoff_date).eq(asof).all():
            lifetime=stored.set_index('customer_id')
            source='customer_rfm'
        else:
            lifetime=daily.groupby('customer_id').agg(first=('purchase_date','min'),last=('purchase_date','max'),
                                                    purchases=('purchase_date','size'))
            lifetime['frequency']=lifetime.purchases-1
            lifetime['recency']=(lifetime['last']-lifetime['first']).dt.days
            lifetime['T']=(asof-lifetime['first']).dt.days
            source='clean_transactions; customer_rfm cutoff differs'
        pred=pd.DataFrame([r for r in predictions if r['run_name']=='PROD' and r['model']=='bgnbd']).set_index('customer_id')
        if set(lifetime.index)!=set(pred.index):
            raise ValueError('PROD and lifetime customer populations differ')
        forecast=pred['expected_purchases_N']*pred.expected_order_value
        if not np.allclose(forecast,pred['bgnbd_clv_N'],rtol=1e-10,atol=1e-8):
            raise ValueError('Stored BG/NBD spend does not equal expected purchases times order value')
        customers=[{'customer_id':str(cid),'days_since_last_purchase':int(row['T']-row.recency),
                    'number_of_purchases':int(row.frequency+1),'customer_age_days':int(row['T']),
                    'probability_of_buying_90d':float(pred.loc[cid,'p_purchase_N']),
                    'expected_spend_90d':float(forecast.loc[cid])} for cid,row in lifetime.iterrows()]
        year=daily.loc[daily.purchase_date.ge(pd.Timestamp(self.start))]
        annual=year.groupby('customer_id').agg(last=('purchase_date','max'),F=('purchase_date','size'),M=('purchase_value','sum'))
        annual=annual.reindex(lifetime.index)
        annual['F']=annual.F.fillna(0);annual['M']=annual.M.fillna(0)
        annual['R']=(asof-annual['last']).dt.days.fillna((asof-pd.Timestamp(self.start)).days+1)
        for key,ascending in (('R',False),('F',True),('M',True)):
            annual[key+'_score']=np.ceil(annual[key].rank(method='average',pct=True,ascending=ascending)*5).astype(int).clip(1,5)
        inactive=annual.F.eq(0)
        annual.loc[inactive,['R_score','F_score','M_score']]=1
        annual['loyalty_score']=annual[['R_score','F_score','M_score']].sum(axis=1)
        annual=annual.rename_axis('customer_id').reset_index().sort_values(['loyalty_score','customer_id'],ascending=[False,True])
        columns=pd.date_range(asof.replace(day=1)-pd.DateOffset(months=11),asof.replace(day=1),freq='MS')
        visible=daily.loc[daily.purchase_date.ge(columns[0])].copy()
        visible['month']=visible.purchase_date.dt.strftime('%Y-%m')
        spend=visible.groupby(['customer_id','month']).purchase_value.sum()
        rows=[{'customer_id':str(r.customer_id),'loyalty_score':int(r.loyalty_score),
               'R':int(r.R_score),'F':int(r.F_score),'M':int(r.M_score),
               'purchase_days_12m':int(r.F),'spend_12m':float(r.M),
               'monthly_spend':[float(spend.get((r.customer_id,c.strftime('%Y-%m')),0)) for c in columns]}
              for r in annual.itertuples()]
        self.active_customers_12m=int(year.customer_id.nunique())
        # Alternative display year for the heatmap columns; ranking and the default 2011 payload are untouched.
        months_2010=[f'2010-{m:02d}' for m in range(1,13)]
        prior=daily.loc[daily.purchase_date.dt.year.eq(2010)].copy()
        prior['month']=prior.purchase_date.dt.strftime('%Y-%m')
        spend_2010=prior.groupby(['customer_id','month']).purchase_value.sum()
        self.heatmap_years={2010:{'months':months_2010,'display_start':'2010-01-01','display_end':'2010-12-31',
            'note':'Calendar year 2010 columns; the ranking still uses the latest 12 months.',
            'spend':{str(cid):[float(spend_2010.get((cid,m),0)) for m in months_2010] for cid in annual.customer_id}}}
        return customers,{'months':[c.strftime('%Y-%m') for c in columns],'rows':rows,
                          'rank_window':self.window,'display_start':columns[0].date().isoformat(),
                          'display_end':self.as_of.isoformat(),
                          'note':'Latest 12 calendar months (current month partial); rolling-year rankings also include the preceding December 10–31.'},source

    def _reconcile_totals(self,audit):
        country=math.fsum(row['net_sales'] for row in self.countries)
        monthly=math.fsum(row['net_sales'] for row in self.monthly)
        for actual,expected in ((country,self._net_12m),(monthly,self._net_history),(self.product_total,self._net_12m)):
            if not math.isclose(actual,expected,rel_tol=1e-10,abs_tol=.01):
                raise ValueError('Executive aggregate totals do not reconcile')
        if pd.Timestamp(audit['data_end']).date()<=self.as_of and not math.isclose(
                self._gross_history,self.reconciliation['clean_sales_full_history']+self.reconciliation['restored_quick_reversal_sales'],
                rel_tol=1e-10,abs_tol=.01):
            raise ValueError('Executive gross sales do not reconcile to cleaned plus reversed purchases')
        self.reconciliation.update(net_sales_full_history=self._net_history,gross_sales_full_history=self._gross_history,
                                   returns_full_history=self._returns_history,net_sales_12m=self._net_12m,
                                   country_sum_12m=country,monthly_sum_full_history=monthly,
                                   products_sum_12m=self.product_total,aggregate_totals_matched=True)

    def summary(self):
        return {'as_of':self.as_of.isoformat(),'ranking_window':self.window,'sales_basis':'net_sales',
                'net_sales_12m':self._net_12m,'gross_sales_12m':self._gross_12m,
                'returns_12m':self._returns_12m,'net_sales_full_history':self._net_history,
                'customers':len(self.customers),'active_customers_12m':self.active_customers_12m,
                **self.invoice_totals,'rfm_source':self.rfm_source,'footnotes':FOOTNOTES,
                'reconciliation':self.reconciliation}

    def customer_page(self,search,sort,direction,page):
        ordered=self.sorted_customers[sort,direction]
        filtered=[r for r in ordered if search in r['customer_id']] if search else ordered
        return {'as_of':self.as_of.isoformat(),'rows':filtered[(page-1)*25:page*25],
                'total':len(filtered),'page':page,'page_size':25,'pages':math.ceil(len(filtered)/25),
                'search':search,'sort':sort,'direction':direction,'rfm_source':self.rfm_source}
