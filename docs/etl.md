# ETL and data cleaning

The ETL service loads both sheets of the source workbook, applies seven
audited cleaning rules, builds a cutoff-specific RFM table and writes a data
quality report, replacing all six tables in one PostgreSQL transaction.

## Source and tables

Source: Chen, D. (2012), [Online Retail II, UCI Machine Learning Repository](https://doi.org/10.24432/C5CG6D),
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Transactions cover 2009-12-01 through 2011-12-09, from a UK online gift-ware
retailer with many wholesale customers. Values are in GBP. The ETL transforms
the source as described below; the workbook is never modified or committed.

| Table | Contents |
| --- | --- |
| `raw_transactions` | All 1,067,371 source lines: 525,461 from `Year 2009-2010` and 541,910 from `Year 2010-2011`. The ETL fails if either count differs. |
| `clean_transactions` | Full-history lines surviving the sequential removal rules, with `is_repeated_line` and `line_value = quantity * price`. |
| `data_quality_report` | Seven cleaning-rule counts, reversal-window diagnostics, and group, StockCode, customer, and customer-day metrics. Printed after a successful commit. |
| `excluded_stockcodes` | Distinct codes actually removed at rule 6, with `row_count` and the first non-null `sample_description` in source order. |
| `customer_rfm` | One non-null row per customer with an eligible purchase, including the cutoff date. |
| `reversed_purchases` | Purchase lines removed by rule 7, with matching cancellation invoice, timestamp, source sheet/row, and `gap_minutes`. Both purchase and cancellation source identities are unique. |

Columns use snake_case names. `source_sheet` and `source_row` identify the source
line; row numbers are physical Excel rows, starting at 2 after the header. Raw
rows are not removed or cleaned. Invoice and StockCode are read as strings, so
numeric `85048` and text `"85048"` represent the same code. Customer IDs are read
as nullable integers and stored as integer-like strings; guests remain SQL NULL.
Other empty cells remain NULL, while literal text such as `NA` is preserved.
Prices and monetary aggregates use floating-point values without currency rounding.

`schema.sql` explicitly creates each table if absent. Every run truncates and
reloads all six tables inside a single SQLAlchemy transaction, using PostgreSQL
COPY for bulk insertion. Primary keys enforce source-row and customer uniqueness.
The report's `removed_line_value` column is added idempotently for existing databases.

## Cleaning rules

Rules 1–6 are evaluated independently on raw rows for standalone counts, then
applied in this order for actual removals. Rule 7 uses the post-overlap source:

1. Remove a row from `Year 2010-2011` only if all eight source columns and its
   within-sheet occurrence number match a row in `Year 2009-2010`. Null values
   match null values. This matches overlap copies one-to-one.
2. Retain all identical lines within a sheet. Flag only occurrences after the
   first physical row in each identical group. Report extra copies and the number
   of repeated groups across raw sheets. Group identity includes the source sheet.
3. Remove missing Customer IDs.
4. Remove invoices whose string starts with `C`, case-insensitively.
5. Remove remaining lines with `quantity <= 0` or `price <= 0`.
6. Remove StockCode strings that do not fully match `^[0-9]{5}[A-Za-z]*$`.
   No code list is hard-coded; whitespace is not stripped to make codes pass.
7. Remove purchase lines with a matched quick reversal, using
   `REVERSAL_WINDOW_HOURS` (default 24). This rule runs last and leaves all rule
   1–6 counts unchanged.

For rule 7, start with raw lines after overlap removal. Cancellation candidates
have a known customer and an invoice string starting with `C`, case-insensitively;
they remain candidates even though rule 4 removes them from cleaned purchases.
Purchase candidates have a known customer, a non-cancellation invoice, positive
quantity, and positive price. Match exactly on customer, string StockCode, and
opposite quantity. Prices may differ. The cancellation must be strictly later
than the purchase, with an elapsed gap no greater than the configured window.

Process cancellations chronologically. Each takes the closest unused earlier
purchase; a purchase and a cancellation can each participate in at most one
pair. For equal-time cancellations, process source sheet/row in ascending order.
For equal-time purchase candidates, choose the largest source sheet/row. These
tie rules make repeated runs deterministic without discarding legitimate repeats.
Only matched purchase lines surviving rules 1–6 are actually removed. Each
diagnostic window is matched independently with the same algorithm; returns
outside the configured window do not remove a purchase.

For example, customer 16446's purchase `581483` is matched to `C581484` 12 minutes
later. Customer 15749's January purchase and April cancellation are more than
24 hours apart; the April repurchase follows that cancellation, so neither
purchase is removed by the default quick-reversal rule. These are inferred
reversal candidates, not source-confirmed labels of order-entry mistakes.

For example, three identical first-sheet lines and two identical second-sheet
lines leave three retained lines after overlap removal. The second and third
first-sheet occurrences are flagged; identical lines are not discarded merely
because they repeat within a sheet.

For the six primary rule rows, `standalone_rows` counts matches in the original
raw data, and `removed_rows` counts actual sequential removals. Rule 2 always
removes zero rows. Sum the seven primary rule rows' `removed_rows` to reconcile
raw versus final clean row totals.

For `7_quick_reversals`, `standalone_rows` counts all matched positive purchase
lines in the post-overlap source, including non-products. `removed_rows` counts
only those surviving rules 1–6. `removed_line_value` is the total GBP value of
the purchases actually removed; it is zero on other report rows.

Additional report rows have an explicit `unit`:

- `2_repeated_line_groups`: raw within-sheet duplicate groups, stored in
  `standalone_rows`; `removed_rows` is zero.
- `rows_remaining_rules_3_4_5_only`: raw rows surviving only rules 3, 4, and 5.
  Overlap copies, repeated lines, and non-products remain in this diagnostic count.
- `6_nonproduct_distinct_stockcodes`: raw distinct non-product codes in
  `standalone_rows`, and distinct codes actually removed at rule 6 in `removed_rows`.
  The primary rule-6 row separately contains raw and sequential row counts.
- `7_matches_1_hour`, `7_matches_24_hours`, `7_matches_7_days`,
  `7_matches_30_days`, and `7_matches_unlimited`: independently computed
  one-to-one pair counts on the post-overlap source, stored in `standalone_rows`
  with unit `pairs`. Their `removed_rows` is zero; these are comparisons, not
  additional removals. They include non-products, explaining any difference from
  the rule-7 sequential removal count.
- `customers_rfm_changed_by_rule7`: customers whose `frequency` or
  `monetary_value` differs from a baseline built with rules 1–6 at the same cutoff.
  Count a customer once if either changes, including customers who lose all
  eligible purchases and disappear from RFM.
- `customers_with_id_in_raw`, `customers_in_rfm`, and
  `customers_without_valid_purchase`: distinct known raw customers, customers in
  RFM at the cutoff, and known raw customers absent from the full cleaned history.
- `customers_first_purchase_after_cutoff`: customers present in cleaned history
  whose first purchase date is later than the cutoff. These differ from customers
  without any valid purchase.
- `customers_lost_at_rule6`: customers with at least one raw line passing rules
  3–5, but no lines left after rule 6, measured across the full history regardless
  of cutoff. In the source workbook, 64 customers have no purchase after rules
  3–5, and a further 26 lose all their remaining lines at rule 6, giving the final
  90 customers without a valid purchase before rule 7. For example, a customer with only a
  positive-quantity, positive-price `POST` line passes rules 3–5 but loses that
  line at rule 6. A customer with a retained product line is not counted here.
- `customer_days_with_multiple_invoices`: eligible customer calendar dates with
  more than one distinct invoice, before collapsing invoices to daily purchases.

Diagnostic and customer counts occupy `standalone_rows`; their `removed_rows`
is zero, except for the rule-6 distinct-code comparison described above.

## RFM definitions

Filter cleaned **lines** to the whole cutoff day before aggregating. An invoice
is grouped by customer and invoice string, dated by its earliest eligible line
timestamp, and valued as the sum of its eligible line values. Then combine all
of a customer's invoices on the same calendar date into one purchase occasion.

Full-history `clean_transactions`, `reversed_purchases`, and window diagnostics
are retrospective. For historical RFM, apply the same rule-7 matching using only
cancellations observed through the cutoff day. Later cancellations cannot revise
an earlier customer's RFM with future information. Consequently, full-history
customer exclusion counts and historical RFM counts need not form a partition.

- `frequency`: number of distinct purchase dates minus one.
- `recency`: calendar days from the first purchase date to the last.
- `T`: calendar days from the first purchase date to the cutoff date.
- `monetary_value`: mean daily purchase value across repeat purchase dates,
  excluding the entire first purchase date. It is zero when `frequency = 0`.

For example, daily purchase totals of GBP 30, 50, and 70 on January 1, 2, and 4,
with a January 5 cutoff, give `frequency=2`, `recency=3`, `T=4`, and
`monetary_value=(50+70)/2=60`. Two invoices on January 2 still represent one
purchase occasion. Lines a few minutes apart within one invoice also count once.

## Tests and dependency pins

The ETL runtime needs pandas, openpyxl, SQLAlchemy, and the psycopg PostgreSQL
driver. Pytest is included only in the development dependency set. Docker runtime
images do not install pytest. Both direct and transitive dependency versions are
pinned; regenerate the ETL locks with:

```sh
uv pip compile services/etl/requirements.in --python-version 3.12 --no-header --no-annotate --output-file services/etl/requirements.txt
uv pip compile services/etl/requirements-dev.in --python-version 3.12 --no-header --no-annotate --output-file services/etl/requirements-dev.txt
```

Run the unit tests from the repository root, without Docker or the real workbook:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r services/etl/requirements-dev.txt
.venv/bin/python -m pytest services/etl/tests -q
```

Tests use tiny in-memory data and temporary Excel fixtures to cover identifier
types, cancellations, product patterns, one-to-one overlap matching, retained
repetitions, sequential versus standalone counts, invoice/day aggregation,
repeat-only monetary value, cutoff boundaries, one-to-one reversal matching,
window boundaries, changed RFM, and unchanged rule 1–6 counts.

## Verified default-window results

At cutoff `2011-12-09` with a 24-hour window, rule 7 removes 1,292 product lines
worth GBP 391,167.69. Clean rows fall from 788,187 to 786,895; RFM customers fall
from 5,852 to 5,851. Frequency or monetary value changes for 245 customers.
Customer 12773 loses all eligible purchases. All six earlier rules keep their
previous standalone and sequential counts.

The independent post-overlap one-to-one diagnostics, including non-products, are:

| Maximum elapsed gap | Matched pairs |
| --- | ---: |
| 1 hour | 1,025 |
| 24 hours | 1,381 |
| 7 days | 2,631 |
| 30 days | 4,558 |
| Unlimited | 6,422 |

Top 10 customers by `monetary_value` before and after rule 7, at the same cutoff
(GBP, rounded for display; each side is ranked independently):

| Rank | Before customer | Before value | After customer | After value |
| ---: | --- | ---: | --- | ---: |
| 1 | 16446 | 168,469.60 | 15749 | 21,535.90 |
| 2 | 12346 | 38,662.96 | 18102 | 8,748.76 |
| 3 | 15749 | 21,535.90 | 13902 | 8,416.40 |
| 4 | 18102 | 8,768.19 | 12415 | 8,326.35 |
| 5 | 13902 | 8,416.40 | 17450 | 6,743.32 |
| 6 | 12415 | 7,872.59 | 12357 | 6,207.67 |
| 7 | 17450 | 6,856.90 | 14646 | 5,789.34 |
| 8 | 12357 | 6,207.67 | 16684 | 4,332.75 |
| 9 | 14646 | 5,789.34 | 14091 | 4,010.08 |
| 10 | 16684 | 4,293.93 | 12378 | 4,008.62 |

Customer 16446 changes from frequency 1 and monetary value GBP 168,469.60 to
frequency 0 and monetary value 0. Customer 12346 changes from frequency 2 to 1
and monetary value GBP 38,662.955 to GBP 142.31. Customer 15749 is unchanged:
the matching January return occurred 97 days later, while the April purchase
followed the cancellation. A mean can increase if a lower-value repeat purchase
date is removed; the repeat-date monetary definition remains unchanged.
