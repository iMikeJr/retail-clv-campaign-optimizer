# Executive dashboard metric definitions

These metrics come from read-only API endpoints on top of the ETL and model
outputs; no ETL output, model table, fitted parameter, prediction or optimizer
equation is changed by them. The executive dashboard renders them without
altering the underlying results. All amounts are GBP and all source
Country values denote countries, not geographic groupings.

## Date and population

- As-of date: **2011-12-09**, read from PROD's stored scoring cutoff. The entire
  day is included; SQL uses an exclusive 2011-12-10 upper bound.
- Ranking/KPI window: **2010-12-10 through 2011-12-09**, inclusive. This is the
  12-month interval `(as_of minus one calendar year, as_of]`, not all of 2011.
  Country/product rankings and annual RFM scores use this rolling window.
- Sales/cancellation trends: the whole observed history through the as-of day,
  by calendar month, including partial December 2011. Missing months are zero;
  a cancellation rate with zero invoices is NULL, not zero.
- Heatmap: **January–December 2011**, the latest 12 calendar-month columns,
  December partial. Ranking spend additionally includes 10–31 December 2010;
  therefore its rolling-year total need not equal the sum of the 12 displayed
  cells. Both intervals are explicit in the endpoint metadata.
- Sales population follows ETL rules 1–6: known customer ID, non-C positive
  quantity/price, valid product code `[0-9]{5}[A-Za-z]*`, with overlap copies
  removed but within-sheet repeats retained. Lines without customer IDs are
  **excluded**, including their cancellations. This is not whole-retailer sales
  including anonymous transactions.
- Customer panels list all customers with a retained clean purchase by cutoff,
  including dormant customers; they are not restricted to buyers in the last
  year. The financial population can also include sales later quickly reversed
  and valid returns from customers without a surviving clean purchase.

## Net sales, countries and products

A product line's revenue is `quantity * price`. It is **revenue, not profit**:
there is no product cost data. The implementation uses faithful return-adjusted
net sales, not the clean-sales fallback:

```text
eligible gross sales = clean_transactions + reversed_purchases
net sales = eligible gross sales - valid cancellation return value
return value = -quantity * price, for negative-quantity C-prefixed product lines
```

Quick-reversal purchases are added back **before** subtracting cancellations;
otherwise their sales were already removed by ETL rule 7 and their returns
would be charged twice. Prices can differ between the original purchase and
return, so matched quick reversals need not net to zero. Returns are not forcibly
matched to a retained purchase: they are valid observed credits, potentially
against older purchases. No clipping or inferred missing purchase is added.

Cancellation lines come from raw_transactions only after reproducing the ETL's
one-to-one overlap rule: match all eight original values, including NULLs and
within-sheet occurrence, then drop matched second-sheet rows only. The query
projects onto C-prefixed invoices; because invoice is part of the identity,
this projection does not change any overlap match. Raw rows are never summed
without that step. Missing-customer and non-product credits are then excluded;
valid returns require negative quantity and positive price.

Country is the line's Country. Missing country is the labeled `Unknown` bucket;
no inference of a customer's residence is made. Country rankings return top 10
plus `Other` when additional countries exist. Shares use total rolling-year net
sales, including Other; negative values are retained if observed. A zero total
has NULL shares. Net values and shares are not silently normalized or clipped.

Product aggregation uses StockCode, with a deterministic alphabetic maximum
non-null description as a representative label. Both top-10 lists are returned:
by return-adjusted revenue and by net units (`sold units - returned units`),
with StockCode ascending breaking ties. Country filters apply to both sales and
returns. Product revenue is still revenue, not campaign profit. Product totals,
country totals and the annual net-sales KPI share the same population/window.

Monthly net sales use each eligible line's recorded InvoiceDate month. All
unrounded amounts are retained in the API; the UI will format currency.

## Cancellation rate

`cancelled invoices / total invoices` counts eligible C-prefixed **return
documents**, not product lines and not an inferred count of fully cancelled
original orders. Partial returns can have their own C invoice.

- A sale invoice has at least one eligible positive product line in the
  reconstructed rules-1–6 sales population.
- A cancellation invoice has at least one valid negative product return line.
- Each invoice is counted once, dated by its earliest eligible line, following
  the ETL's earliest-line invoice convention. Monthly denominator is sales
  invoices + cancellation invoices in that month.
- Monthly cancellation value is the positive absolute value of valid returns
  dated in that month. Return documents and their monetary line entries are
  separately identifiable; values are not interpreted as lost profit.
- The headline rate uses the same rolling-year interval and is a ratio of
  counts, not an unweighted mean of monthly percentages.

## Loyalty and customer fields

Loyalty uses **retained clean purchase spend**, not net sales; it follows the
ETL/model's purchase population and excludes cancellation invoices and quick
reversals. Aggregate lines into customer/invoice using earliest eligible date,
then combine invoices on the same calendar day into one purchase occasion.

For each retained customer, within the ranking window:

- R = days from the most recent purchase day to as-of; smaller is better.
- F = number of purchase days, **including the first** purchase day in the window.
- M = sum of clean purchase values in the window, with no model value cap.

Compute each component's empirical percentile rank over all retained customers,
using average ranks for identical values. R ranks descending (small recency gets
a high percentile); F and M rank ascending. Score is `ceil(5 * percentile)`,
clamped to 1–5. Customers without a purchase in the window receive R=F=M=1.
Thus identical inputs get identical scores rather than splitting ties into
arbitrary quintiles. Loyalty score is R+F+M, 3–15. Sort score descending, then
customer ID ascending as stored (text), and return up to 25 rows. Customer ID
breaks final score ties; no second spend ranking is introduced.

Each heatmap cell is clean purchase spend in its calendar month, zero when no
purchase occurred. It is not profit, modeled spend or an offer effect.

Customer-table lifetime fields reuse customer_rfm when its cutoff is exactly
the PROD as-of date:

```text
days since last purchase = T - recency
number of purchases = frequency + 1
customer age in days = T
```

If that cutoff differs, recompute these lifetime fields from clean transactions
through as-of and return that source explicitly; do not overwrite customer_rfm.
The snapshot requires the customer IDs to match PROD/BG-NBD predictions.

Probability of buying is PROD/BG-NBD's stored `p_purchase_N`. Expected spend over
90 days is stored expected purchase count times Gamma-Gamma order value; verify
it equals the stored `bgnbd_clv_N`. **It is not probability times order value**,
which values only one purchase occasion. Neither is incremental campaign impact.

The headline campaign profit uses the existing default PROD/BG-NBD interactive
campaign calculation and unchanged assumptions. It is expected incremental
scenario margin minus contact/discount cost, not observed profit. The dashboard updates
this KPI from the existing optimize endpoint as the stakeholder changes inputs.

## Read-only endpoints and caching

All source SELECTs use static SQL and bound date/prefix parameters, inside the
same REPEATABLE READ, READ ONLY startup transaction as the existing model
snapshot. No raw sale rows are copied into the API; SQL pre-aggregates sales,
products and customer-day purchases. Only the small cancellation projection is
loaded for exact overlap reconciliation. Data-quality, source, financial and
prediction checks run before the startup snapshot can be served.

Heavy aggregates, product filters and customer sort orders are precomputed in
memory at API startup. Request parameters never become SQL. Restart the API
after ETL/model refresh to replace its immutable snapshot and caches.

| Endpoint | Contents / parameters |
| --- | --- |
| `GET /api/exec/summary` | Dates, sales definition, annual/history totals, customer counts, annual cancellation rate, default campaign profit, footnotes and reconciliation. |
| `GET /api/sales/by-country` | Top 10 + Other, shares, annual total, available countries. |
| `GET /api/sales/monthly` | Full-history calendar months, gross/returns/net values, partial-month flag, history total. |
| `GET /api/products/top?country=` | Both top-10 lists; absent/empty country means all; unknown country returns 404. |
| `GET /api/cancellations/monthly` | Invoice counts, return values, rates and partial-month flags over full history. |
| `GET /api/customers/loyalty-heatmap` | Up to 25 customers, scores, annual RFM values and 12 calendar-month spend cells; optional `year` (2010 or 2011, default 2011) selects the months shown without changing the ranking. |
| `GET /api/customers` | Literal customer-ID substring `search`, `sort`, `direction=asc|desc`, `page>=1`; always 25 rows per page. |

Customer sort keys are `customer_id`, `days_since_last_purchase`,
`number_of_purchases`, `customer_age_days`, `probability_of_buying_90d`, and
`expected_spend_90d`; ties use customer ID ascending. The API default remains
customer ID ascending; the dashboard explicitly requests expected_spend_90d
descending on initial load, using the existing endpoint. Search, sorting and
pagination remain available. Empty/out-of-range pages return no rows with correct totals; invalid
sort/direction/page values return 422. SQL-like search text is a literal string,
not a query. Existing API endpoints and optimizer behavior are unchanged.

## Reconciliation checks

Before serving data, verify: raw rows minus all seven ETL primary removal counts
= clean row count; reversed rows/value = rule 7 removal counts/value;
deduplicated known-customer cancellation rows = rule 4 sequential removals;
country annual sum = annual net sales; product annual sum = annual net sales;
monthly history sum = history net sales; and full-history gross sales = cleaned
sales + restored reversed sales when the source ends at as-of.

The same rolling-year country total must **not** be compared directly with the
full-history monthly total: these are different intervals. Both intervals and
sums are returned explicitly. Measured values, fixture tests, real-data checks
and warm HTTP latency are recorded in the
[endpoint verification report](project-log/stage5_e1_results.md). The final clean full-stack and externally isolated startup verification is
recorded in [final verification report](project-log/stage5_final_verification.md).


## Dashboard wording and presentation

- Header: **Data as of 09 Dec 2011**. The **Customers** KPI is the **4,260**
  accounts with a purchase in the rolling year, with **5,851 total accounts**
  as a small footnote. The searchable table still contains all 5,851 accounts.
- Use **Returns**, including the monthly panel and headline share of invoices.
  Partial returns are included; the existing `/api/cancellations/monthly` URL
  and its fields are unchanged for compatibility.
- The visible population note is **Sales to identified customers only (about
  77% of lines)**. This approximate identified-ID share refers to source lines,
  not a sales-value coverage estimate or the percentage of rows left after all
  cleaning rules. Anonymous sales remain excluded from the metric.
- The heatmap and every monthly chart label the partial final month
  **Dec (1-9)**. Calendar-month figures earlier in the history keep their year
  context. The rolling-versus-calendar distinction is unchanged.
- Header campaign label: **Expected profit from the campaign**, paired with
  the available budget, e.g. **invest £1,682, expect £9,123 in profit**. Header
  currency values are rounded to whole pounds for readability; detailed values
  and the actual expected campaign cost remain visible in the campaign panel.
  The investment figure is the budget ceiling; actual expected cost may be
  lower, and profit per pound uses actual expected cost as its denominator.
- Primary campaign inputs are budget and maximum coupons. The six economic
  assumptions are collapsed under **Advanced assumptions**; the visible banner
  states **The response to each offer and the margin are assumptions, not
  estimated from data; an A/B test would estimate them.**
- The executive page uses plain **probability of buying**, **response to the
  offer (assumption)** and **profit** wording. All technical evidence is in
  **Method and evidence**, collapsed by default at the bottom. Historical model
  comparison, calibration, actual status/gap, three baselines, sensitivity and
  the grouped Run A backtest remain available. Technical evidence loads when
  this section opens; existing endpoints, scoring and optimization are unchanged.
- Heatmap colour is a monotone logarithmic transformation of monthly spend,
  used only to retain visual contrast across large differences. Hover/focus
  shows the original GBP value; no spend value or loyalty score is transformed.
  Customer-table sorting and filtering use unrounded API values, not formatted
  strings. Top selected customers are all rendered, up to 15, without vertical
  clipping. They are proposed contacts, not a claimed count of reactivations.

Development history, screenshots and raw evidence are in the
[project log](project-log/README.md).

## Final display refinements

Sales and return-rate charts show Dec (1-9) through a dotted connecting segment
and hollow marker. Return-count/value bars use a hollow dotted outline. Short
notes identify the incomplete month; amounts, rates, dates and tooltips are not
rescaled, extrapolated or removed. Full-month points retain solid styling.

The account page initially ranks expected_spend_90d descending across all
5,851 accounts, before pagination. It retains all six interactive sort keys and
customer-ID search. This is a frontend request choice; API defaults do not change.

The 15 selected-customer rows add days_since_last_purchase and expected_spend_90d
by exact customer-ID matching against the existing customer endpoint. The lookup
is cached in the page and uses PROD/BG-NBD even if the campaign model changes.
Campaign action, expected gain and row order still come from the optimize result.
Loading/unavailable context is explicit and failed lookups retry on the next
proposal update; a failed lookup never becomes zero. A stale proposal cannot
overwrite the current table. These descriptive fields do not affect selection.


## Presentation refinements

The underlying definitions and API responses above remain unchanged. Current UI differences supersede the earlier presentation descriptions: the heatmap shows top 10, the account table presents 10 rows with a full pager, and monthly sales/Returns charts contain only complete months through November 2011. December 1–9 totals appear separately with calendar-day averages beside those for Dec 2009–Nov 2011 (730 days); no extrapolation is used. The invoice-share note compares return invoices/day and the ratio of summed return invoices to summed total invoices; a percentage is not divided by days. UK share remains a fraction of total annual net sales, and other-country bars use an independent linear scale starting at zero. See [presentation report](project-log/stage5_polish_phase1.md) and [exact help wording](project-log/stage5_polish_phase1_tooltips.md).


## Table labels and campaign comparison

Current presentation supersedes the preceding UI description: probability percentages remain without bars because all default first-page probabilities exceed 98%; the UI label for customer_age_days is **Time as customer (days)**. **Typical order value** displays the existing selected-action field `v`, distinct from expected 90-day spend. Expected gain remains margin × v × assumed incremental probability − expected cost. The sales December comparison sits below its title; Returns uses short daily/rate comparisons, with totals and longer definitions available through info tooltips. The UI's improvement over ratio greedy is the current interactive plan's unrounded expected profit less the same baseline's unrounded profit; the old static exact-solve comparison is removed. See [arithmetic and verification](project-log/stage5_polish_fix.md).


## Country filter, paging and export

Financial and loyalty definitions above are unchanged. Monthly country filtering uses all full-history country/month facts, including historical-only countries; blank country means all countries. Every filtered series retains the overall month grid with zeroes where that country has no activity. Gross sales, returns and net sales sum to the unfiltered values month by month. The UK headline remains a rolling-year amount/share and is independent of the monthly selector and product selector.

The heatmap now pages the complete ranking (10 rows in the UI) rather than truncating after 25 rows; the first ten customers and all scores are unchanged. An exact numeric ID finds its zero-based rank, jumps to floor(rank / limit) × limit, and highlights that row. Colour contrast remains relative to the displayed page; values shown on hover/focus remain original GBP amounts.

Campaign rows are cached directly from the unchanged optimizer's assignments. A solution ID identifies that exact plan; action filtering, sorting, paging and CSV all query the same records, never another solve. No contact has the optimizer's zero cost/gain, not a probability-of-not-buying field. Descriptive recency and expected 90-day spend remain the current PROD/BG-NBD context, separately labeled by `context_as_of`, even for a cached historical plan. Export has the six table fields, two-decimal currency, and all rows in the current action filter. The default optimize response retains its top-15 preview for compatibility and adds only a solution identifier.
