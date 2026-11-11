import pytest

from ecom_os.core import permissions as P
from ecom_os.core.state import set_setting
from ecom_os.models import ActionLog, Approval


def test_levels_classification():
    for a in ["research", "create_draft", "report", "compare_suppliers"]:
        assert P.level_of(a) == "A"
    for a in ["publish_product", "update_stock", "edit_page", "publish_organic_post", "reply_customer_simple"]:
        assert P.level_of(a) == "B"
    for a in ["ad_spend", "supplier_purchase", "payment", "contract", "bank_details_change",
              "sensitive_price_change", "refund", "permanent_delete", "first_public_launch"]:
        assert P.level_of(a) == "C"


def test_unknown_action_is_level_c(session):
    assert P.level_of("action_bizarre") == "C"
    d = P.authorize(session, "action_bizarre")
    assert not d.allowed and d.status == "approbation_requise"


def test_level_a_allowed(session):
    d = P.authorize(session, "research")
    assert d.allowed and d.level == "A"


def test_level_b_blocked_until_configured(session):
    d = P.authorize(session, "publish_product")
    assert not d.allowed and d.status == "bloque_config"
    set_setting(session, "level_b_enabled", True)
    assert P.authorize(session, "publish_product").allowed


@pytest.mark.parametrize("action", sorted(P.LEVEL_C))
def test_every_level_c_creates_pending_approval_and_never_executes(session, action):
    executed = []
    d, res = P.run_guarded(session, action, lambda: executed.append(1), payload={"x": 1})
    assert not d.allowed and d.status == "approbation_requise"
    assert executed == [] and res is None
    appr = session.get(Approval, d.approval_id)
    assert appr.status == "en_attente" and appr.action == action


def test_level_c_executes_only_after_approval_and_only_once(session):
    executed = []
    d, _ = P.run_guarded(session, "contract", lambda: executed.append(1))
    aid = d.approval_id
    # pas encore approuvée
    d2, _ = P.run_guarded(session, "contract", lambda: executed.append(1), approval_id=aid)
    assert not d2.allowed and executed == []
    P.approve(session, aid)
    d3, _ = P.run_guarded(session, "contract", lambda: executed.append(1), approval_id=aid)
    assert d3.allowed and executed == [1]
    assert session.get(Approval, aid).status == "execute"
    d4, _ = P.run_guarded(session, "contract", lambda: executed.append(1), approval_id=aid)
    assert not d4.allowed and executed == [1]


def test_approval_cannot_be_reused_for_other_action(session):
    d, _ = P.run_guarded(session, "refund", lambda: None)
    P.approve(session, d.approval_id)
    d2 = P.authorize(session, "payment", approval_id=d.approval_id)
    assert not d2.allowed and d2.status == "refuse"


def test_rejected_approval_blocks(session):
    d, _ = P.run_guarded(session, "refund", lambda: None)
    P.reject(session, d.approval_id)
    d2 = P.authorize(session, "refund", approval_id=d.approval_id)
    assert not d2.allowed
    with pytest.raises(ValueError):
        P.approve(session, d.approval_id)


def test_budget_zero_prevents_approving_spend(session):
    d = P.authorize(session, "ad_spend", amount_eur=20.0)
    with pytest.raises(ValueError, match="budget"):
        P.approve(session, d.approval_id)
    set_setting(session, "budget_ads_eur", 50.0)
    assert P.approve(session, d.approval_id).status == "approuve"


def test_stop_all_blocks_every_level(session):
    set_setting(session, "level_b_enabled", True)
    d, _ = P.run_guarded(session, "payment", lambda: None)
    set_setting(session, "emergency_stop", True)
    for action in ["research", "publish_product", "payment"]:
        r = P.authorize(session, action)
        assert not r.allowed and r.status == "bloque_stop"
    # même une approbation existante ne passe pas
    assert not P.authorize(session, "payment", approval_id=d.approval_id).allowed
    with pytest.raises(PermissionError):
        P.approve(session, d.approval_id)
    assert session.query(Approval).count() == 1  # aucune nouvelle approbation créée pendant STOP
    assert session.query(ActionLog).filter_by(outcome="bloque").count() >= 3


def test_price_change_classification(session):
    assert P.classify_price_change(session, 20.0, 21.0) == "price_change_minor"
    assert P.classify_price_change(session, 20.0, 25.0) == "sensitive_price_change"
    assert P.classify_price_change(session, 0, 25.0) == "sensitive_price_change"


def test_decisions_are_logged(session):
    P.authorize(session, "refund")
    assert session.query(ActionLog).filter_by(outcome="approbation_requise").count() == 1
