import pytest

from ecom_os.agents.finance import MarginInput, compute_margin


def test_margin_reference_case():
    r = compute_margin(MarginInput(sale_price_ttc=30.25, supplier_cost=8, shipping_cost=4, vat_rate=0.21,
                                   payment_fee_pct=0.03, payment_fee_fixed=0.25, ads_cost_per_order=5,
                                   variable_fees=0.5, returns_rate=0.1))
    # HT = 25 ; frais paiement = 0.9075+0.25 = 1.1575 ; retours = 0.1*12 = 1.2
    assert r["price_ht"] == 25.0
    assert r["payment_fees"] == 1.16
    assert r["returns_provision"] == 1.2
    assert r["margin_before_ads"] == pytest.approx(25 - 8 - 4 - 1.1575 - 0.5 - 1.2, abs=0.01)
    assert r["contribution_margin"] == pytest.approx(10.1425 - 5, abs=0.01)
    assert r["break_even_cpa"] == pytest.approx(10.14, abs=0.01)
    assert r["break_even_roas"] == pytest.approx(30.25 / 10.1425, abs=0.01)
    assert r["profitable"] is True


def test_unprofitable_product_has_no_break_even():
    r = compute_margin(MarginInput(sale_price_ttc=10, supplier_cost=9, shipping_cost=3))
    assert r["contribution_margin"] < 0 and r["profitable"] is False
    assert r["break_even_cpa"] is None and r["break_even_roas"] is None


def test_zero_vat_franchise():
    r = compute_margin(MarginInput(sale_price_ttc=20, supplier_cost=5, vat_rate=0, payment_fee_pct=0,
                                   payment_fee_fixed=0, returns_rate=0))
    assert r["price_ht"] == 20 and r["contribution_margin"] == 15


@pytest.mark.parametrize("kw", [{"sale_price_ttc": 0, "supplier_cost": 1}, {"sale_price_ttc": 10, "supplier_cost": -1},
                                {"sale_price_ttc": 10, "supplier_cost": 1, "returns_rate": 2}])
def test_invalid_inputs(kw):
    with pytest.raises(ValueError):
        compute_margin(MarginInput(**kw))
