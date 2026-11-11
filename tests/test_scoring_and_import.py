from ecom_os.agents import scout, store_builder, supplier
from ecom_os.connectors import csv_import
from ecom_os.models import Offer, Product, ProductDraft, Supplier

from .conftest import OFFERS_CSV, PRODUCTS_CSV


def test_unit_scores():
    assert scout.score_demand(None, 10) is None
    assert scout.score_demand(70, 20) == 74
    assert scout.score_demand(95, 500) == 100
    assert scout.score_margin(50) == 100 and scout.score_margin(-5) == 0
    assert scout.score_competition(30) == 70
    assert scout.score_supplier(5, 1000) == 100 and scout.score_supplier(5, 10) == 85
    assert scout.score_logistics(4, False) == 100 and scout.score_logistics(30, True) == 10
    assert scout.score_logistics(12, True) == 60


def test_combine_requires_enough_data():
    total, ok = scout.combine({"demand": 80, "margin": None, "competition": 50, "supplier": 80,
                               "logistics": 80, "marketing": 80})
    assert total is None and ok is False
    total, ok = scout.combine({"demand": 100, "margin": 100, "competition": 100, "supplier": 100,
                               "logistics": 100, "marketing": None})
    assert ok and total == 100


def test_csv_import_products_and_offers(session):
    r = csv_import.import_products(session, PRODUCTS_CSV)
    assert r == {"created": 2, "updated": 0, "errors": []}
    r2 = csv_import.import_offers(session, OFFERS_CSV.encode("utf-8"))
    assert r2["created"] == 2 and r2["errors"] == []
    assert session.query(Supplier).count() == 2
    eu = session.query(Supplier).filter_by(name="Fournisseur UE").one()
    assert eu.eu_warehouse is True and eu.rating == 4.6
    assert session.query(Offer).filter_by(unit_cost=7.5).count() == 1
    # ré-import = mise à jour, pas de doublon
    r3 = csv_import.import_products(session, PRODUCTS_CSV)
    assert r3["created"] == 0 and r3["updated"] == 2


def test_csv_import_rejects_bad_rows(session):
    bad = "name,demand_index,est_sale_price\nOK,50,10\n,50,10\nTrop,150,10\nTexte,abc,10\n"
    r = csv_import.import_products(session, bad)
    assert r["created"] == 1 and len(r["errors"]) == 3
    r2 = csv_import.import_offers(session, "product_name,supplier_name,unit_cost\nInconnu,X,5\n")
    assert r2["created"] == 0 and "inconnu" in r2["errors"][0]["error"]
    r3 = csv_import.import_products(session, "foo,bar\n1,2\n")
    assert r3["errors"][0]["line"] == 1


def test_find_winners_ranks_only_sufficient_data(session):
    csv_import.import_products(session, PRODUCTS_CSV)
    csv_import.import_offers(session, OFFERS_CSV)
    res = scout.find_winners(session)
    names_ranked = [r["name"] for r in res["ranked"]]
    names_insuf = [r["name"] for r in res["insufficient_data"]]
    assert names_ranked == ["Produit Test A"]
    assert names_insuf == ["Produit Test B"]
    a = session.query(Product).filter_by(name="Produit Test A").one()
    assert a.data_sufficient and 0 <= a.score_total <= 100
    b = session.query(Product).filter_by(name="Produit Test B").one()
    assert b.score_total is None and b.status != "shortlist"


def test_supplier_ranking_prefers_eu_fast(session):
    csv_import.import_products(session, PRODUCTS_CSV)
    csv_import.import_offers(session, OFFERS_CSV)
    p = session.query(Product).filter_by(name="Produit Test A").one()
    ranked = supplier.rank_offers(session, p)
    assert ranked[0]["supplier"] == "Fournisseur UE"


def test_build_draft_contains_required_sections(session):
    csv_import.import_products(session, PRODUCTS_CSV)
    csv_import.import_offers(session, OFFERS_CSV)
    p = session.query(Product).filter_by(name="Produit Test A").one()
    d = store_builder.build_draft(session, p)
    assert "14 jours" in d.returns_info and "2 ans" in d.returns_info
    assert "2 à 5 jours" in d.shipping_info
    assert len(d.faq) >= 4 and d.finance["price_ht"] > 0
    ids = [i["id"] for i in d.compliance["items"]]
    assert {"tva", "rgpd", "retractation", "gpsr"} <= set(ids)
    assert session.query(ProductDraft).count() == 1


def test_compliance_flags():
    from ecom_os.agents.compliance import check_product
    r = check_product(Product(name="Chargeur USB Disney pour enfant"))
    assert "electrique" in r["flags"] and "enfant_jouet" in r["flags"]
    assert "disney" in r["ip_flags"] and r["risk"] == "élevé"
