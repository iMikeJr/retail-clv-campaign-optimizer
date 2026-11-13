# Reduced Phase 2: info-tooltip inventory

The full browser check verified all 50 info icons on hover and keyboard focus. Numeric inputs and sliders reuse the corresponding control help. Country-dependent chart explanations update from the selected series; the default texts below reflect All countries.

| Label | Exact tooltip text |
| --- | --- |
| Net sales | Product sales after returns in the last 12 months, for customers we can identify. This is revenue, not profit. |
| Customers | Customers who bought in the last 12 months. The note below shows all retained accounts, including those who have not bought recently. |
| Returns | The share of invoices that record a return in the last 12 months. A return may cover only part of an order. |
| Expected profit from the campaign | Extra profit we expect from the proposed campaign after its costs. It depends on our assumptions about offer responses and margin. |
| Sales at a glance | Countries follow the source Country field. Product sales and returns use the same country filter; overlapping source entries are counted once. |
| How sales have changed | Chart shows complete months through Nov 2011; the headline uses the last 12 months. Dec 1–9: £339,118.97. £37,679.89 per calendar day, compared with £22,017.53 per day. The previous average covers Dec 2009–Nov 2011 (730 calendar days). December covers 9 days. Charts end at November; no full December month is estimated. |
| Customer loyalty ranking | Loyalty combines how recently, how often and how much customers bought in the rolling year; score ties use customer ID. These 12 calendar columns are Jan–Dec 2011, with Dec (1-9) partial. Ranking spend also includes 10–31 Dec 2010. |
| Who is likely to buy? | A purchase is one customer-day; counts and customer age use the full retained history. Age starts at the first observed purchase. Expected spend allows repeat purchases and is not profit or the extra sales caused by an offer. |
| Customer | The customer’s identifier in the source data. |
| Days since last purchase | Days from the customer’s last recorded purchase to 9 December 2011. |
| Purchases | The number of days on which this customer bought something in the retained history. Several orders on one day count as one purchase. |
| Time as customer (days) | Days from the customer’s first recorded purchase to 9 December 2011. This is the length of their recorded history, not their personal age. |
| Probability of buying · 90 days | The estimated chance that the customer buys at least once in the next 90 days, even if we do nothing. It is not a guarantee. |
| Expected spend · 90 days | What we expect the customer to spend in the next 90 days even if we do nothing. |
| Returns | A return invoice can contain a partial return; it does not establish that the whole original order was cancelled. Values are revenue returned, not lost profit. Charts show complete months through Nov 2011; notes report the partial December period separately. |
| Return invoices | Dec 1–9: 136.00. 15.11 per calendar day, compared with 9.79 per day. The previous average covers Dec 2009–Nov 2011 (730 calendar days). December covers 9 days. Charts end at November; no full December month is estimated. |
| Value returned | Dec 1–9: £174,111.46. £19,345.72 per calendar day, compared with £738.22 per day. The previous average covers Dec 2009–Nov 2011 (730 calendar days). December covers 9 days. Charts end at November; no full December month is estimated. |
| Share of invoices | Dec 1–9: 14.91%. Return invoices: 15.11 per day; previous average 9.79 per day. The previous average covers Dec 2009–Nov 2011 (730 calendar days). December covers 9 days. Charts end at November; no full December month is estimated. |
| Reset proposal | Restore the starting budget, coupon limit and assumptions for the proposal. |
| Budget (£) | The most we are willing to spend on emails and coupons. |
| Maximum coupons | A ceiling on coupons, not a target. |
| Advanced assumptions | Change the assumed margin, offer responses, costs and coupon discount used in the proposal. |
| Margin (assumption, %) | The share of each pound of sales left after product costs, before campaign costs. This is an assumption, not measured from these data. |
| Response to email (assumption, %) | The assumed share of customers who would not otherwise buy but buy because of an email. An A/B test would help estimate this. |
| Response to coupon (assumption, %) | The assumed share of customers who would not otherwise buy but buy because of a coupon. An A/B test would help estimate this. |
| Email cost (£) | The cost of sending one email, whether or not the customer buys. |
| Coupon fixed cost (£) | The fixed cost of offering one coupon, before any discount on a purchase. |
| Coupon discount (%) | The share taken off the purchase price when a customer uses the coupon. |
| Proposed outreach | These are customers to contact, not confirmed reactivations. Expected profit values one purchase occasion; it is not total future customer spend. |
| No contact | Customers we propose leaving without an email or coupon. No messages are sent from this demo. |
| Email | Customers we propose sending an email to. This is a proposed action, not a confirmed purchase. |
| Coupon | Customers we propose offering a coupon to. This is a proposed action, not a confirmed purchase. |
| Total expected cost | What we expect to spend on emails, coupon costs and discounts for this proposal. It can be less than the budget. |
| Expected profit | Extra profit we expect from the proposed campaign after its costs. It depends on our assumptions about offer responses and margin. |
| Return on investment (ROI) | Expected extra profit divided by expected campaign cost. For example, £5.43 means £5.43 profit for each £1 spent. It depends on our assumptions. |
| Customer | The customer’s identifier in the source data. |
| Recommended action | The action proposed for this customer under the current budget, coupon limit and assumptions. |
| Days since last purchase | Days from the customer’s last recorded purchase to 9 December 2011. |
| Expected spend · 90 days | What we expect the customer to spend in the next 90 days even if we do nothing. |
| Typical order value | The size of a typical purchase for this customer. Expected gain is the extra chance of buying created by the offer times this value times the margin, minus the cost. |
| Expected gain | Extra profit we expect from this action after its cost; it depends on our assumption of how customers respond to the offer. |
| Method and evidence | Select a model to inspect calibration. Lift ranks propensity; revenue capture ranks probability × expected order value. |
| Calculation status | Status: FEASIBLE_GAP_TARGET. Native status: NOT_RUN_CERTIFIED_GAP. Actual gap: 0.0033%. Target: 0.5%. The bound applies to the plan using values rounded to pennies. |
| Historical model comparison | The proposed campaign uses PROD's 09 Dec 2011 cutoff. The customer-account table always uses stored PROD/BG-NBD forecasts. Solver status and the actual certified gap are reported here, never presented as an estimated business effect. Run A underpredicts peak-season purchasing. PROD trains on that peak and scores an off-peak horizon; ML probabilities are expected to be overestimated, but future calibration is unverified. Loyalty uses R+F+M quintiles with average percentile ranks and ID tie-breaking; no-purchase-in-window accounts score 1+1+1. Heatmap colours use a logarithmic scale to preserve contrast across spend sizes. Forecasts, selection optimism, seasonality and campaign response assumptions are distinct limitations. |
| Calibration | Dashed line: perfect calibration; points above it indicate underprediction. |
| Baseline challenge | The improvement shown here compares the current interactive proposal with ratio greedy under the same assumptions. It uses unrounded expected profit, before formatting to pounds and pennies. A large improvement over the naive baseline does not establish a large gain over a sensible alternative. |
| Sensitivity to budget and response | At most 15 scenarios, 0.5% gap target, no extra-budget solve. Other current campaign assumptions are held fixed. The default grid is precomputed at API startup. |
| Run A: what was at stake, not campaign effect | These purchases occurred without the proposed campaign. Groups are selected, not randomized; the denominator excludes new customers acquired after cutoff. Buyer order value averages each buyer's spend / purchase occasions. Optimizing for high predicted value can select customers with overestimated order values; whole-group predictions and buyer-only outcomes have different populations (hover the prediction for the same-buyer mean). The model assumes the same action-response parameter tau for dormant customers (pi close to 0) as for other customers. |
| Contacted-customer realized spend | What these customers actually spent in the historical period, before any campaign. It is a reference point, not a result. |
| Share of eligible spend | The share of all eligible customers’ actual spending covered by the selected customers in the historical check. It does not show extra sales caused by a campaign. |
