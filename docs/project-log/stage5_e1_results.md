# Stage 5 E1: definitions, read-only endpoints and sanity-check results

E1 completed; **stop before E2 and the page redesign**. All seven executive
endpoints are implemented with cached/precomputed aggregates. Existing campaign,
model evidence and health endpoints remain available. No ETL/model output or
optimizer implementation was changed; no push was made.

## Headline values

As of **09 December 2011**. Ranking/KPI window: **10 December 2010–09 December
2011**, inclusive. Revenue excludes lines without customer IDs and non-product
codes, matching the ETL's known-customer product population.

- **Net sales, last 12 months: GBP 7,983,782.90**.
  Gross eligible product sales GBP 8,451,542.90, less valid returns
  GBP 467,760.00. This is faithful return-adjusted net sales, not the
  clean-sales fallback, and it is revenue rather than profit.
- Retained customers: **5,851**, including dormant customers;
  **4,260** bought during the ranking window.
- Annual cancellation-document rate: **15.62%** =
  3,262 C-prefixed return invoices /
  20,890 total eligible sales + return invoices. Partial
  returns are included; this is not a count of fully cancelled original orders.
- Default proposed-campaign expected profit: **GBP 9,122.55**,
  from the existing interactive PROD/BG-NBD scenario with GBP 1,682
  budget and 300 maximum coupons. This is assumption-driven,
  not observed retailer profit; optimizer inputs and equations are unchanged.

### Top five countries in the ranking window

| Country (original source label) | Net sales (GBP) | Share |
| --- | ---: | ---: |
| United Kingdom | 6,550,864.61 | 82.05% |
| Netherlands | 283,301.94 | 3.55% |
| EIRE | 242,439.63 | 3.04% |
| Germany | 196,039.67 | 2.46% |
| France | 175,839.06 | 2.20% |

The endpoint returns the top ten plus Other and the full available-country list
for product filtering. Country shares use the annual net-sales denominator.

### Loyalty and customer-table sanity check

**25 loyalty rows × 12 calendar-month columns**, January–December 2011, with
December partial. Scores use rolling-year clean purchase-day R/F/M quintiles
and sum to 3–15; identical inputs keep equal scores and final ties use customer
ID. First five selected customer IDs are 12347, 12362, 12388, 12417, 12423,
all with score 15. This is the requested discrete-score selection, not a second
ranking by raw spend.

The rolling-year rank window also includes 10–31 December 2010, outside the
12 displayed calendar columns. Both ranking and display intervals are explicit
in the response. This calendar/rolling distinction is part of the E1 sanity check.

The customer table includes all retained customers, uses the matching-cutoff
**customer_rfm**, and returns 25 rows per page. Examples:

| Customer | Days since purchase | Purchase days | Customer age (days) | Probability of buying within 90 days | Expected spend over 90 days (GBP) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12346 | 529 | 2 | 647 | 12.55% | 41.50 |
| 12347 | 2 | 8 | 404 | 73.07% | 836.31 |
| 12348 | 75 | 5 | 438 | 51.49% | 292.26 |

A purchase is one customer-day. Expected spend is expected purchase count ×
Gamma-Gamma order value, verified against saved BG/NBD CLV for every customer;
it is not probability × value and not incremental campaign impact. Search is
literal customer-ID substring matching; sorting and pagination use precomputed
in-memory orders with fixed 25-row pages.

## Net-sales reconciliation

The whole-history bridge through 09 December 2011 is:

```text
clean product sales                          GBP   16,733,758.54
+ quick-reversal purchases added back         GBP      391,167.69
= eligible sales before cancellation credits  GBP   17,124,926.23
- valid product cancellation returns          GBP      713,009.65
= net sales                                  GBP   16,411,916.58
```

Restoring the reversed purchases before subtracting credits prevents charging
the same return twice. No raw row is summed before the overlap rule is applied.
Source reconciliation to data_quality_report:

- Raw rows 1,067,371, less ETL primary removals, equal 786,895
  clean rows. The full ETL overlap removal count is 22,523.
- Cancellation projection removes 329
  overlapping copies; 18,446 known-customer
  cancellation rows then match the ETL rule-4 removal count exactly.
- Restored rows: 1,292; their GBP
  391,167.69 value matches rule 7 exactly.
- Valid product return lines: 17,641 across 7,282 return documents over the full
  history. Other cancellation entries are outside this product/customer scope.

Country totals (including Other) and product totals equal **annual** net sales;
monthly totals equal **whole-history** net sales. These are deliberately different
windows. Source gross = clean + reversed purchases; source returns and invoice
counts also matched an independent SQL implementation of overlap deduplication.
All monetary reconciliations passed to one penny; unrounded API floats can differ
at tiny summation-order precision.

Independent SQL and historical model hashes: [reconciliation evidence](stage5_e1_reconciliation.json).
The four historical runs' complete metric/prediction hashes still match the
pre-Stage-4 snapshot. ETL, model and optimizer source code is unchanged. Model
integration tests used and cleaned their reserved test runs; no production run
was republished.

## Tests and latency

- **81 API/optimizer/executive tests passed in 0.79 seconds** in the pinned Linux
  API image, including every existing API/optimizer case. New fixtures cover
  NULL-key overlaps, retained repeats, double-return prevention, cutoff boundaries,
  missing countries, invoice versus line counts, dormant customers, lifetime RFM
  reuse/fallback, matched CLV, loyalty ties, 25-row pagination, country filtering,
  literal search, validation and reconciliation failures.
- **21 model tests passed in 57.72 seconds**, including the original 17.
- **39 ETL tests passed in 0.87 seconds**.
- Built and started only the API service against the existing dataset; all new
  routes were exercised via actual local HTTP calls. Heavy work is at startup,
  in the read-only snapshot; every endpoint met the 300 ms warm target.

| Request | Warm median (ms) | Warm maximum (ms), 10 repeats |
| --- | ---: | ---: |
| `/api/exec/summary` | 1.85 | 3.34 |
| `/api/sales/by-country` | 1.14 | 2.02 |
| `/api/sales/monthly` | 1.97 | 3.89 |
| `/api/products/top` | 1.13 | 2.06 |
| `/api/products/top?country=United%20Kingdom` | 1.01 | 1.96 |
| `/api/cancellations/monthly` | 1.19 | 2.62 |
| `/api/customers/loyalty-heatmap` | 0.98 | 2.19 |
| `/api/customers` | 0.81 | 2.03 |
| `/api/customers?search=123&sort=expected_spend_90d&direction=desc&page=1` | 1.92 | 2.15 |
| `/api/customers?sort=probability_of_buying_90d&direction=desc&page=2` | 0.87 | 5.95 |

Full saved outputs and timings: [E1 verification](stage5_e1_verification.json).
Reproduce warm checks with `services/api/benchmark_executive.py`; reproduce
independent read-only SQL with `services/api/verify_executive_data.py` in the API
image/Compose environment. These are local measurements, not a concurrency SLA.

## Definitions ready for E2

[dashboard_metrics.md](../dashboard_metrics.md) defines all populations, dates,
sales/returns, invoice-rate denominator, RFM quintiles/ties, heatmap windows,
customer lifetimes and forecast units. Short plain-language footnotes are in the
summary response, ready for E2 rendering. No dashboard file was changed in E1.

The full-stack clean rebuild/start and startup with networking disabled remain
scheduled once, at the end of Stage 5 after the redesign. E1 does not claim that
final verification or the redesigned UI has been completed. No external services
or OpenAI API were called by the API.
