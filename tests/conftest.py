import os

import pytest

os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["GOOGLE_TRENDS_DISABLED"] = "1"  # pas d'appel réseau dans les tests
for k in ["SHOPIFY_STORE_DOMAIN", "SHOPIFY_ADMIN_TOKEN", "STRIPE_API_KEY", "DASHBOARD_TOKEN"]:
    os.environ.pop(k, None)

from ecom_os import db  # noqa: E402

PRODUCTS_CSV = """name,keyword,niche,problem_solved,target_customer,est_sale_price,demand_index,trend_growth_pct,competition_level,marketing_potential,return_risk
Produit Test A,produit a,maison,Gagner du temps,Parents actifs,34.90,70,20,40,80,faible
Produit Test B,produit b,sport,Douleur,Sportifs,19.90,,,,,
"""
OFFERS_CSV = """product_name;supplier_name;platform;supplier_country;eu_warehouse;supplier_rating;reviews_count;unit_cost;shipping_cost;shipping_days_min;shipping_days_max;stock
Produit Test A;Fournisseur UE;BigBuy;ES;oui;4,6;1200;7,50;3,90;2;5;500
Produit Test A;Fournisseur CN;CJdropshipping;CN;non;4.2;300;4.10;5.20;8;15;2000
"""


@pytest.fixture()
def session():
    db.configure("sqlite:///:memory:")
    s = db.SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client():
    db.configure("sqlite:///:memory:")
    from fastapi.testclient import TestClient

    from ecom_os.api.main import app
    import ecom_os.db as dbm
    orig = dbm.configure
    dbm.configure = lambda url=None: None  # garder la base mémoire du test
    try:
        with TestClient(app) as c:
            yield c
    finally:
        dbm.configure = orig
