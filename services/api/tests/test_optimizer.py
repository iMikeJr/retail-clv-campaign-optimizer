import itertools
import math
from pathlib import Path
import random
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from optimizer import (Assumptions, Customer, optimize, cost_pence, _prepare,
                       _solve, choose_default_budget, _relaxation, DUAL_SCALE)


def toy():
    return [Customer("A",.1,400),Customer("B",.5,400),Customer("C",.1,50)]


def test_exact_three_customer_example():
    r = optimize(toy(),10.50)
    assert [a["action"] for a in r["assignments"]] == ["coupon","email","email"]
    assert r["cost"] == pytest.approx(10.50)
    assert r["net_value"] == pytest.approx(7.17)
    assert r["cost_pence"] == 1050
    assert r["net_value_pence"] == 717
    assert r["baseline"]["net_value"] < r["net_value"]
    e = _prepare(toy(),10.50,300,Assumptions())[1]
    assert sum(row[1][1] for row in e) == pytest.approx(3.48)
    assert cost_pence(10.4) == 1040
    assert cost_pence(.050001) == 6
    assert r["solver"]["status"] == "OPTIMAL"
    assert r["solver"]["optimality_gap"] == 0


@pytest.mark.parametrize("seed",range(24))
def test_matches_exhaustive_integer_formulation(seed):
    rng = random.Random(seed)
    n = 1+seed%8
    customers = [Customer(str(i),rng.random(),rng.uniform(1,700)) for i in range(n)]
    s = Assumptions(m=rng.uniform(.1,.8),tau_e=rng.random()/3,tau_c=rng.random(),
                    f_e=rng.random(),f_c=rng.random()*3,d=rng.random()/2)
    B,K = rng.uniform(0,150),rng.randrange(n+1)
    customers,e,budget = _prepare(customers,B,K,s)
    feasible = [a for a in itertools.product(range(3),repeat=n)
                if a.count(2)<=K and sum(row[2][x] for row,x in zip(e,a))<=budget]
    best = max(sum(row[3][x] for row,x in zip(e,a)) for a in feasible)
    certificate = _relaxation(e,budget,K)
    if certificate is not None:
        upper,reduced,maxima,_ = certificate
        assert upper >= best*DUAL_SCALE
        for (i,a),r in reduced.items():
            forced = [assignment for assignment in feasible if assignment[i]==a]
            if forced:
                assert upper+r >= max(sum(row[3][x] for row,x in zip(e,assignment))
                                      for assignment in forced)*DUAL_SCALE
    choices,diag = _solve(e,budget,K)
    assert diag["status"] == "OPTIMAL"
    assert diag["objective_pence"] == best
    assert choices.count(2)<=K
    assert sum(row[2][a] for row,a in zip(e,choices))<=budget
    assert math.fsum(row[0][a] for row,a in zip(e,choices))<=B+1e-8


def test_constraints_monotonicity_and_determinism():
    customers = [Customer(str(i),.02*i,10+20*i) for i in range(20)]
    objectives=[]
    for B in (0,1,5,10,20,100):
        r = optimize(customers,B,3)
        assert sum(r["counts"].values()) == len(customers)
        assert r["counts"]["coupon"]<=3
        assert r["cost_pence"]<=math.floor(B*100+1e-9)
        assert r["cost"]<=B+1e-8
        assert r["extra_100"]["marginal_net_value_pence"]>=0
        objectives.append(r["net_value_pence"])
    assert objectives == sorted(objectives)
    first = optimize(customers,20,3)
    second = optimize(list(reversed(customers)),20,3)
    assert first["assignments"] == second["assignments"]
    assert first["solver"]["objective_pence"] == second["solver"]["objective_pence"]


def test_exact_dual_certificate_at_large_currency_scale():
    customers = [Customer(str(i),.05+.1*i,100_000_000+10_000_000*i) for i in range(8)]
    _,e,budget = _prepare(customers,20_000_000,3,Assumptions())
    feasible = [a for a in itertools.product(range(3),repeat=8)
                if a.count(2)<=3 and sum(row[2][x] for row,x in zip(e,a))<=budget]
    best = max(sum(row[3][x] for row,x in zip(e,a)) for a in feasible)
    assert _relaxation(e,budget,3)[0] >= best*DUAL_SCALE
    assert _solve(e,budget,3)[1]["objective_pence"] == best


def test_outcomes_are_descriptive_and_not_required():
    customers = [Customer("A",.1,400,100),Customer("B",.5,400,200),Customer("C",.1,50,300)]
    r = optimize(customers,10.5)
    assert r["backtest"]["selected_realized_spend"] == 600
    assert r["backtest"]["share"] == 1
    assert r["backtest"]["label"] == "What was at stake, not campaign effect"
    assert optimize(toy(),10.5)["backtest"] is None
    with pytest.raises(ValueError):
        optimize([Customer("a",.2,20,1),Customer("b",.2,20)],10)


def test_edge_cases_and_break_even():
    assert optimize([],0,0)["counts"] == dict(none=0,email=0,coupon=0)
    assert optimize([],0)["roi"] is None
    assert optimize(toy(),10.5,0)["counts"]["coupon"] == 0
    free = optimize(toy(),0,0,Assumptions(f_e=0))
    assert free["counts"]["email"] == 3
    assert free["roi"] is None
    assert optimize(toy(),100,assumptions=Assumptions(m=0))["counts"]["none"] == 3
    r = optimize([Customer("x",1,100)],100)
    assert r["assignments"][0]["break_even"]["email"]["tau"] is None
    r = optimize(toy(),10.5,assumptions=Assumptions(m=.1,d=.1))
    assert r["assignments"][0]["break_even"]["coupon"]["attainable"] is False
    a = optimize(toy(),10.5)["assignments"][0]
    assert a["break_even"]["email"]["tau"] == pytest.approx(.05/(.3*400*.9))
    assert a["break_even"]["coupon"]["tau"] == pytest.approx(5/(.2*400*.9))
    assert choose_default_budget(toy())["B"]>=0


def test_stronger_baselines_and_action_economics():
    r = optimize(toy(),10.5)
    assert r["baselines"]["email_only"]["net_value"] == pytest.approx(3.48)
    assert r["baselines"]["ratio_greedy"]["net_value"] == pytest.approx(7.17)
    assert r["baselines"]["naive"]["net_value"] == r["baseline"]["net_value"]
    assert sum(x["cost"] for x in r["by_action"].values()) == pytest.approx(r["cost"])
    assert sum(x["net_value"] for x in r["by_action"].values()) == pytest.approx(r["net_value"])
    low = optimize(toy(),.05)
    assert low["baselines"]["email_only"]["feasible"] is False
    assert low["baselines"]["ratio_greedy"]["feasible"] is True


def test_group_backtest_and_optional_interactive_solve():
    customers=[Customer("a",.1,400,100,1),Customer("b",.5,400,0,0),Customer("c",.1,50,50,1)]
    r=optimize(customers,10.5,include_extra_100=False,interactive=True)
    assert r["extra_100"] is None
    assert r["solver"]["requested_relative_gap"] == .005
    assert r["solver"]["optimality_gap"] <= .005
    groups=r["backtest"]["groups"]
    assert groups["all_eligible"]["customers"] == 3
    assert groups["all_eligible"]["observed_purchase_rate"] == pytest.approx(2/3)
    assert groups["email_only"]["mean_realized_spend"] == 25


def test_interactive_certificate_can_avoid_integer_search(monkeypatch):
    import optimizer
    def fail_if_called():
        raise AssertionError('Certified gap already meets the target')
    monkeypatch.setattr(optimizer.cp_model,'CpSolver',fail_if_called)
    result=optimize(toy(),10.5,interactive=True,include_extra_100=False)
    assert result['solver']['native_status']=='NOT_RUN_CERTIFIED_GAP'
    assert result['solver']['optimality_gap']<=.005


def test_backtest_order_values_are_customer_means_among_buyers():
    customers=[Customer('a',.1,400,100,1,2),Customer('b',.5,400,0,0,0),
               Customer('c',.1,50,50,1,5)]
    result=optimize(customers,10.5,include_extra_100=False)
    groups=result['backtest']['groups']
    assert groups['coupon']['mean_predicted_order_value']==400
    assert groups['coupon']['mean_realized_order_value_buyers']==50
    assert groups['email_only']['mean_predicted_order_value']==225
    assert groups['email_only']['mean_realized_order_value_buyers']==10
    all_customers=groups['all_eligible']
    assert all_customers['buyers']==2
    assert all_customers['mean_predicted_order_value']==pytest.approx(850/3)
    assert all_customers['mean_predicted_order_value_buyers']==225
    assert all_customers['mean_realized_order_value_buyers']==30
    assert groups['none']['mean_realized_order_value_buyers'] is None
    # Missing purchase counts cannot silently become one order per buyer.
    legacy=optimize([Customer('a',.1,400,100,1)],20,include_extra_100=False)
    assert legacy['backtest']['groups']['all_eligible']['mean_realized_order_value_buyers'] is None


@pytest.mark.parametrize("kwargs",[{"B":-1},{"B":float("nan")},{"B":float("inf")},
                                  {"B":1,"K":1.2},{"B":1,"K":True},{"B":1,"K":-1}])
def test_invalid_campaign_inputs(kwargs):
    with pytest.raises(ValueError):
        optimize(toy(),**kwargs)


@pytest.mark.parametrize("kwargs",[{"m":1.1},{"tau_c":-.1},{"d":float("nan")},{"f_e":-1}])
def test_invalid_assumptions(kwargs):
    with pytest.raises(ValueError):
        Assumptions(**kwargs)


@pytest.mark.parametrize("customers",[[Customer("x",1.1,10)],[Customer("x",.1,0)],
                                    [Customer("x",.1,10),Customer("x",.2,30)]])
def test_invalid_customers(customers):
    with pytest.raises(ValueError):
        optimize(customers,10)
