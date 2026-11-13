# Checks before Stage 5

Run A / BG-NBD, default assumptions, GBP 1,682 budget and 300-coupon limit.
Values read from the running read-only API after adding saved actual_purchases
to its startup snapshot. No model fitting, predictions or campaign economics
were changed. The selection is the same as the accepted M2b exact result.

| Group | Customers | Buyers | Predicted order value, whole group | Predicted order value, same buyers | Realized order value, buyers |
| --- | ---: | ---: | ---: | ---: | ---: |
| coupon | 144 | 14 | GBP 466.29 | GBP 404.03 | GBP 304.89 |
| email_only | 5,039 | 2,202 | GBP 386.73 | GBP 409.69 | GBP 463.01 |
| all_eligible | 5,254 | 2,286 | GBP 389.42 | GBP 410.28 | GBP 466.67 |

Realized order value is the unweighted average of each buyer's
actual_spend / actual_purchases, matching the Stage 3 value evaluation. It is
not total customer spend or pooled spend divided by all purchases; a purchase
occasion remains one customer-day. Nonbuyers have no observed order value.

Among the 14 coupon buyers, the same-buyer prediction exceeds realized order
value by about 32.5%. This is descriptive evidence of overestimation in that
small selected subset, while the all-eligible buyer comparison underestimates
value. It does not identify the order values of nonbuyers who might respond to
an offer, or establish a causal campaign effect. The dashboard displays the
requested whole-group mean alongside the buyer-only observed value, with the
same-buyer prediction available in the prediction cell's tooltip and API output.

Added the selection-effect and dormant-customer response-assumption sentences
to docs/optimizer.md and the dashboard backtest note. The 83.66% spend share and
98.65% customer coverage are unchanged.

The API returned 15 highest-value customers already; the screenshot showed only
the rows fitting the table's 315-pixel scroll area. Removed that height limit
and made the label reflect the returned count, so all 15 rows are visible in a
full-page screenshot. Added browser assertions guarding row count and clipping.

Verification: 64 optimizer/API tests passed in 0.45 seconds; tests distinguish
customer-weighted buyer order values from pooled order values and handle missing
purchase counts without inventing one purchase per buyer. JavaScript syntax
checks passed. Focused browser verification passed with 15 rendered rows, no vertical clipping,
all seven backtest columns, and zero console errors. Evidence: [browser check](pre_stage5_browser_check.json),
[order-value screenshot](screenshots/backtest-order-values.png), and
[all 15 customers](screenshots/top-15-customers.png).

Final docs and full-stack/network-disabled startup verification are deferred to
the end of Stage 5, after the redesign; they have not been run here. E1's scope
was absent from the user message and from the repository, so it cannot start
until those instructions arrive.
