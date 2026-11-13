"""Assumption-driven, one-purchase-occasion campaign optimization.

No experiment estimates margin or conversion effects: all Assumptions fields are
user-supplied scenarios. No web/database dependencies or network calls.
"""
from dataclasses import dataclass, asdict
import math
import time

from ortools.sat.python import cp_model
from ortools.linear_solver import pywraplp

ACTIONS = ("none", "email", "coupon")
SOLVER_SECONDS = 5.0
DEFAULT_BUDGET = 1682  # Frozen from PROD/bgnbd; see docs/optimizer.md.
DEFAULT_MAX_COUPONS = 300
DUAL_SCALE = 10**9


@dataclass(frozen=True)
class Assumptions:
    # Assumptions, not estimates from the retailer's observational data.
    m: float = 0.30
    tau_e: float = 0.02
    tau_c: float = 0.15
    f_e: float = 0.05
    f_c: float = 1.00
    d: float = 0.10

    def __post_init__(self):
        for key, value in asdict(self).items():
            upper = 1 if key in ("m", "tau_e", "tau_c", "d") else 1_000_000
            if isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= upper:
                raise ValueError(f"Invalid assumption: {key}")


@dataclass(frozen=True)
class Customer:
    customer_id: str
    pi: float
    v: float
    actual_spend: float | None = None
    actual_purchased: int | None = None
    actual_purchases: int | None = None


def cost_pence(value):
    """Conservative conversion; tolerate floating noise at exact penny boundaries."""
    return math.ceil(value * 100 - 1e-9)


def gain_pence(value):
    # Explicit nearest-penny ties away from zero, independent of Python's round().
    return math.floor(value * 100 + 0.5) if value >= 0 else -math.floor(-value * 100 + 0.5)


def _prepare(customers, B, K, assumptions):
    if isinstance(B, bool) or not math.isfinite(B) or not 0 <= B <= 1_000_000_000:
        raise ValueError("B must be finite and between 0 and 1000000000 GBP")
    if isinstance(K, bool) or not isinstance(K, int) or not 0 <= K <= 1_000_000:
        raise ValueError("K must be an integer between 0 and 1000000")
    customers = sorted(customers, key=lambda c: c.customer_id)
    if len({c.customer_id for c in customers}) != len(customers):
        raise ValueError("Customer IDs must be unique")
    for c in customers:
        if (not isinstance(c.customer_id, str) or not c.customer_id or
            not math.isfinite(c.pi) or not 0 <= c.pi <= 1 or
            not math.isfinite(c.v) or not 0 < c.v <= 1_000_000_000 or
            (c.actual_spend is not None and (not math.isfinite(c.actual_spend) or c.actual_spend < 0))):
            raise ValueError("Invalid customer input")
    if any(c.actual_spend is None for c in customers) and any(c.actual_spend is not None for c in customers):
        raise ValueError("Realized outcomes must be available for all customers or none")
    economics = []
    for c in customers:
        delta_e, delta_c = assumptions.tau_e * (1-c.pi), assumptions.tau_c * (1-c.pi)
        costs = (0., assumptions.f_e, assumptions.f_c + assumptions.d*c.v*(c.pi+delta_c))
        gains = (0., assumptions.m*c.v*delta_e-costs[1], assumptions.m*c.v*delta_c-costs[2])
        economics.append((costs, gains, tuple(map(cost_pence, costs)), tuple(map(gain_pence, gains))))
    return customers, economics, math.floor(B * 100 + 1e-9)


def _value(choices, economics):
    return sum(row[3][a] for a, row in zip(choices, economics))


def _baseline(customers, economics, budget, K):
    choices = [0]*len(customers)
    for i in sorted(range(len(customers)), key=lambda i: (-customers[i].pi*customers[i].v, customers[i].customer_id)):
        cost = economics[i][2][2]
        if K and cost <= budget:
            choices[i] = 2
            budget -= cost
            K -= 1
    return choices


def _unconstrained(economics, K):
    choices = [1 if row[3][1] > 0 else 0 for row in economics]
    upgrades = sorted(range(len(choices)), key=lambda i: (-(economics[i][3][2]-economics[i][3][choices[i]]), i))
    for i in upgrades[:K]:
        if economics[i][3][2] > economics[i][3][choices[i]]:
            choices[i] = 2
    return choices


def _email_assignments(economics, budget=None):
    choices = [0]*len(economics)
    for i in sorted(range(len(economics)),key=lambda i:(-economics[i][1][1],i)):
        row = economics[i]
        if row[1][1] > 0 and (budget is None or row[2][1] <= budget):
            choices[i] = 1
            if budget is not None:
                budget -= row[2][1]
    return choices


def _ratio_greedy(economics, budget, K):
    choices = _email_assignments(economics,budget)
    spent = sum(row[2][a] for row,a in zip(economics,choices))
    upgrades = []
    for i,row in enumerate(economics):
        dg,dc = row[1][2]-row[1][1],row[0][2]-row[0][1]
        if choices[i] == 1 and dg > 0:
            upgrades.append((-(dg/dc if dc > 0 else math.inf),i))
    for _,i in sorted(upgrades):
        dc = economics[i][2][2]-economics[i][2][1]
        if K and spent+dc <= budget:
            choices[i] = 2
            spent += dc
            K -= 1
    return choices


def _hint(economics, budget, K, initial=None):
    choices = list(initial) if initial is not None else [0]*len(economics)
    candidates = [(i,a) for i,row in enumerate(economics) for a in (1,2) if row[3][a] > 0]
    candidates.sort(key=lambda pair: (-economics[pair[0]][3][pair[1]] / max(economics[pair[0]][2][pair[1]], 0.001), pair))
    spent = sum(row[2][a] for row,a in zip(economics,choices))
    coupons = choices.count(2)
    for i,a in candidates:
        old = choices[i]
        row = economics[i]
        dc, dk = row[2][a]-row[2][old], int(a==2)-int(old==2)
        if row[3][a] > row[3][old] and spent+dc <= budget and coupons+dk <= K:
            choices[i] = a
            spent += dc
            coupons += dk
    return choices


def _relaxation(economics, budget, K):
    """LP upper bound and reduced costs; never change the integer objective.

    If U is the relaxed optimum and L a feasible integer value, forcing an
    unused action with reduced cost r<0 can yield at most U+r. Forbidding it
    is safe when U+r<L. Rebuilt customer multipliers give the test for 'none'.
    """
    lp = pywraplp.Solver.CreateSolver("GLOP")
    lp.set_time_limit(1000)
    budget_row = lp.RowConstraint(-lp.infinity(),budget,"budget")
    coupon_row = lp.RowConstraint(-lp.infinity(),K,"coupons")
    variables = {}
    objective = lp.Objective()
    objective.SetMaximization()
    for i,row in enumerate(economics):
        customer_row = lp.RowConstraint(-lp.infinity(),1,f"customer_{i}")
        for a in (1,2):
            if row[3][a] <= 0:
                continue
            x = lp.NumVar(0,lp.infinity(),f"lp_{i}_{a}")
            variables[i,a] = x
            customer_row.SetCoefficient(x,1)
            budget_row.SetCoefficient(x,row[2][a])
            coupon_row.SetCoefficient(x,int(a==2))
            objective.SetCoefficient(x,row[3][a])
    if lp.Solve() != pywraplp.Solver.OPTIMAL:
        return None
    choices = [0]*len(economics)
    for (i,a),x in variables.items():
        if x.solution_value() >= 1-1e-7:
            choices[i] = a
    # Numerical LP tolerances never authorize an infeasible integer incumbent.
    if (sum(row[2][a] for row,a in zip(economics,choices)) > budget or choices.count(2) > K):
        choices = [0]*len(economics)
    # Rebuild a feasible dual certificate using exact Python integer arithmetic.
    # Any nonnegative budget/coupon multipliers give a valid Lagrangian bound;
    # row maxima supply the customer multipliers. This avoids trusting floating
    # reduced costs to delete integer solutions at large monetary scales.
    lam = max(0,math.ceil(budget_row.dual_value()*DUAL_SCALE))
    mu = max(0,math.ceil(coupon_row.dual_value()*DUAL_SCALE))
    scores = {(i,a):economics[i][3][a]*DUAL_SCALE-lam*economics[i][2][a]-mu*int(a==2)
              for i,a in variables}
    maxima = [max(0, scores.get((i,1),0), scores.get((i,2),0)) for i in range(len(economics))]
    upper = lam*budget+mu*K+sum(maxima)
    reduced = {key:score-maxima[key[0]] for key,score in scores.items()}
    return upper,reduced,maxima,choices


def _solve(economics, budget, K, incumbent=None, *, relative_gap=0., time_limit=SOLVER_SECONDS):
    tick = time.perf_counter()
    hint = _hint(economics, budget, K)
    ratio_hint = _ratio_greedy(economics,budget,K)
    if _value(ratio_hint,economics) > _value(hint,economics):
        hint = ratio_hint
    relaxation = _relaxation(economics,budget,K)
    if relaxation is not None:
        lp_hint = _hint(economics,budget,K,relaxation[3])
        if _value(lp_hint,economics) > _value(hint,economics):
            hint = lp_hint
    if incumbent is not None and _value(incumbent,economics) > _value(hint,economics):
        hint = incumbent
    lower_bound = _value(hint,economics)
    if relative_gap and relaxation is not None:
        bound = relaxation[0]//DUAL_SCALE
        gap = max(0,bound-lower_bound)/max(1,abs(lower_bound))
        if gap <= relative_gap:
            return hint, {"solver":"OR-Tools GLOP / certified feasible campaign",
                          "status":"OPTIMAL_BOUND_CERTIFICATE" if gap == 0 else "FEASIBLE_GAP_TARGET",
                          "native_status":"NOT_RUN_CERTIFIED_GAP", "requested_relative_gap":relative_gap,
                          "optimality_proven":gap==0,"cp_sat_bound_pence":None,
                          "objective_pence":lower_bound,"bound_pence":bound,"optimality_gap":gap,
                          "lp_bound_pence":relaxation[0]/DUAL_SCALE,"integer_variables":0,
                          "seconds":time.perf_counter()-tick}
    model = cp_model.CpModel()
    variables = {}
    for i,row in enumerate(economics):
        for a in (1,2):
            # Nonpositive actions cannot improve on none. Prune dominated actions.
            if row[3][a] <= 0:
                continue
            if relaxation is not None and relaxation[0]+relaxation[1].get((i,a),0) < lower_bound*DUAL_SCALE:
                continue
            other = 3-a
            if row[2][other] <= row[2][a] and row[3][other] > row[3][a]:
                # Email cannot be pruned in favor of a capacity-limited coupon.
                if other == 1:
                    continue
            variables[i,a] = model.new_bool_var(f"x_{i}_{a}")
        action_sum = sum(variables.get((i,a), 0) for a in (1,2))
        if relaxation is not None and relaxation[0]-relaxation[2][i] < lower_bound*DUAL_SCALE:
            model.add(action_sum == 1)
        else:
            model.add(action_sum <= 1)
    model.add(sum(economics[i][2][a]*x for (i,a),x in variables.items()) <= budget)
    model.add(sum(x for (i,a),x in variables.items() if a==2) <= K)
    objective = sum(economics[i][3][a]*x for (i,a),x in variables.items())
    model.maximize(objective)
    for (i,a),x in variables.items():
        model.add_hint(x, int(hint[i]==a))
    model.add(objective >= _value(hint, economics))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(.001,time_limit-(time.perf_counter()-tick))
    solver.parameters.relative_gap_limit = relative_gap
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status = solver.solve(model)
    if status in (cp_model.INFEASIBLE,cp_model.MODEL_INVALID):
        raise RuntimeError("Integer model rejected a validated feasible campaign")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # A validated hint remains feasible even if the wall clock expires in presolve.
        choices = hint
        status_name = solver.status_name(status) + "_FEASIBLE_HINT"
        bound = None
    else:
        choices = [0]*len(economics)
        for (i,a),x in variables.items():
            if solver.value(x):
                choices[i] = a
        status_name = solver.status_name(status)
        bound = solver.best_objective_bound
    value = _value(choices, economics)
    cp_bound = bound
    # Always expose a valid global bound, even if CP-SAT times out in presolve.
    # The integer certificate can also tighten a loose CP-SAT search bound.
    global_bound = relaxation[0]//DUAL_SCALE if relaxation is not None else sum(max(row[3]) for row in economics)
    bound = min(bound,global_bound) if bound is not None else global_bound
    gap = max(0.,bound-value)/max(1,abs(value)) if bound is not None else None
    raw_status = solver.status_name(status)
    if status_name == "OPTIMAL" and gap and gap > 1e-12:
        status_name = "FEASIBLE_GAP_TARGET"
    return choices, {"solver": "OR-Tools CP-SAT", "status": status_name,
                     "native_status": raw_status, "requested_relative_gap": relative_gap,
                     "optimality_proven": gap == 0,
                     "cp_sat_bound_pence":cp_bound,
                     "objective_pence": value, "bound_pence": bound,
                     "optimality_gap": gap,
                     "lp_bound_pence": relaxation[0]/DUAL_SCALE if relaxation is not None else None,
                     "integer_variables": len(variables),
                     "seconds": time.perf_counter()-tick}


def _break_even(c, s):
    def threshold(intercept, slope):
        if intercept <= 0:
            return {"tau": 0., "attainable": True}
        if slope <= 0:
            return {"tau": None, "attainable": False}
        tau = intercept / slope
        return {"tau": tau, "attainable": tau <= 1}
    return {"email": threshold(s.f_e, s.m*c.v*(1-c.pi)),
            "coupon": threshold(s.f_c+s.d*c.v*c.pi, (s.m-s.d)*c.v*(1-c.pi))}


def _summarize(customers, economics, choices, assumptions):
    cost = math.fsum(row[0][a] for row,a in zip(economics,choices))
    net = math.fsum(row[1][a] for row,a in zip(economics,choices))
    scaled_cost = sum(row[2][a] for row,a in zip(economics,choices))
    scaled_net = _value(choices,economics)
    assignments = [{"customer_id": c.customer_id, "action": ACTIONS[a], "pi": c.pi, "v": c.v,
                    "cost": row[0][a], "net_value": row[1][a], "cost_pence": row[2][a],
                    "net_value_pence": row[3][a], "break_even": _break_even(c,assumptions)}
                   for c,row,a in zip(customers,economics,choices)]
    backtest = None
    by_action = {action:{"customers":choices.count(a),
                        "cost":math.fsum(row[0][a] for row,x in zip(economics,choices) if x==a),
                        "net_value":math.fsum(row[1][a] for row,x in zip(economics,choices) if x==a)}
                 for a,action in enumerate(ACTIONS)}
    if customers and customers[0].actual_spend is not None:
        selected = math.fsum(c.actual_spend for c,a in zip(customers,choices) if a)
        total = math.fsum(c.actual_spend for c in customers)
        backtest = {"label": "What was at stake, not campaign effect", "selected_realized_spend": selected,
                    "total_eligible_realized_spend": total, "share": selected/total if total else None,
                    "coverage_note": "Contacted customers cover almost every customer" if sum(bool(a) for a in choices)/len(customers)>.9 else "Contacted subset of eligible customers"}
        groups = {}
        for name,action in (("coupon",2),("email_only",1),("none",0),("all_eligible",None)):
            group = [c for c,a in zip(customers,choices) if action is None or a==action]
            n = len(group)
            # Legacy callers can supply spend without the binary outcome/count.
            buyers = [c for c in group if (c.actual_purchased if c.actual_purchased is not None else c.actual_spend>0)]
            realized_values = [c.actual_spend/c.actual_purchases for c in buyers
                               if c.actual_purchases is not None and c.actual_purchases>0]
            groups[name] = {"customers":n,"mean_predicted_pi":math.fsum(c.pi for c in group)/n if n else None,
                            "observed_purchase_rate":sum(c.actual_purchased if c.actual_purchased is not None else c.actual_spend>0 for c in group)/n if n else None,
                            "mean_realized_spend":math.fsum(c.actual_spend for c in group)/n if n else None,
                            "buyers":len(buyers),
                            "mean_predicted_order_value":math.fsum(c.v for c in group)/n if n else None,
                            "mean_predicted_order_value_buyers":math.fsum(c.v for c in buyers)/len(buyers) if buyers else None,
                            "mean_realized_order_value_buyers":math.fsum(realized_values)/len(buyers)
                            if buyers and len(realized_values)==len(buyers) else None}
        backtest["groups"] = groups
    return {"counts": {action: choices.count(i) for i,action in enumerate(ACTIONS)},
            "cost": cost, "net_value": net, "roi": net/cost if cost else None,
            "cost_pence": scaled_cost, "net_value_pence": scaled_net,
            "cost_rounding_difference": scaled_cost/100-cost,
            "net_rounding_difference": scaled_net/100-net,
            "assignments": assignments, "backtest": backtest, "by_action":by_action}


def optimize(customers, B, K=300, assumptions=None, *, include_extra_100=True, interactive=False):
    """Return the campaign, baseline and finite difference at B+100 GBP."""
    start = time.perf_counter()
    assumptions = assumptions or Assumptions()
    customers, economics, budget = _prepare(customers,B,K,assumptions)
    settings = {"relative_gap":.005 if interactive else 0.,"time_limit":1.8 if interactive else SOLVER_SECONDS}
    choices, diagnostics = _solve(economics,budget,K,**settings)
    result = _summarize(customers,economics,choices,assumptions)
    baseline = _summarize(customers,economics,_baseline(customers,economics,budget,K),assumptions)
    extra = None
    if include_extra_100:
        more, more_diagnostics = _solve(economics,budget+10000,K,choices,**settings)
        more_result = _summarize(customers,economics,more,assumptions)
        extra = {"net_value":more_result["net_value"],
                 "marginal_net_value":more_result["net_value"]-result["net_value"],
                 "marginal_net_value_pence":more_result["net_value_pence"]-result["net_value_pence"],
                 "solver":more_diagnostics}
    baselines = {}
    for name,assignment in (("naive",_baseline(customers,economics,budget,K)),
                            ("email_only",_email_assignments(economics)),
                            ("ratio_greedy",_ratio_greedy(economics,budget,K))):
        summary = _summarize(customers,economics,assignment,assumptions)
        summary.pop("assignments")
        summary["feasible"] = summary["cost_pence"] <= budget and summary["counts"]["coupon"] <= K
        summary["improvement"] = result["net_value"]-summary["net_value"]
        summary["improvement_fraction"] = summary["improvement"]/summary["net_value"] if summary["net_value"]>0 else None
        baselines[name] = summary
    improvement = result["net_value"]-baseline["net_value"]
    result.update(solver=diagnostics, B=B, K=K, assumptions=asdict(assumptions), baseline=baseline,
                  baselines=baselines, interactive=interactive,
                  improvement=improvement,
                  improvement_fraction=improvement/baseline["net_value"] if baseline["net_value"] > 0 else None,
                  extra_100=extra,
                  top_selected=sorted([a for a in result["assignments"] if a["action"] != "none"],
                                      key=lambda a: (-a["net_value"], a["customer_id"]))[:15],
                  total_seconds=time.perf_counter()-start)
    return result


def choose_default_budget(customers, K=300, assumptions=None):
    """Half the no-budget optimum's conservative cost; require budget value."""
    assumptions = assumptions or Assumptions()
    customers,economics,_ = _prepare(customers,0,K,assumptions)
    choices = _unconstrained(economics,K)
    unconstrained_cost = sum(row[2][a] for row,a in zip(economics,choices)) / 100
    B = math.floor(unconstrained_cost/2)
    while True:
        result = optimize(customers,B,K,assumptions)
        if result["extra_100"]["marginal_net_value_pence"] > 0 or B == 0:
            return {"B": B, "unconstrained_cost": unconstrained_cost, "result": result}
        B //= 2
