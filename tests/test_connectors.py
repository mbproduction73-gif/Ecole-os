import httpx
import pytest

from ecom_os.connectors import registry
from ecom_os.connectors.base import NotConnectedError
from ecom_os.connectors.shopify import ShopifyConnector
from ecom_os.connectors.stripe_conn import StripeConnector

STUBS = ["cjdropshipping", "zendrop", "bigbuy", "aliexpress", "meta_ad_library", "tiktok_creative_center",
         "google_ads", "meta_ads", "tiktok_ads", "woocommerce"]


def test_all_unconfigured_are_non_connecte():
    st = {s["key"]: s for s in registry.statuses()}
    for k in STUBS + ["shopify", "stripe", "google_trends"]:
        assert st[k]["status"] == "non connecté", k


@pytest.mark.parametrize("key", STUBS)
def test_stubs_never_return_data(key, monkeypatch):
    c = registry.get(key)
    for var in c.required_env:  # même avec des variables présentes, un stub reste non connecté
        monkeypatch.setenv(var, "x")
    assert c.status()["status"] == "non connecté"
    with pytest.raises(NotConnectedError):
        c.fetch()
    with pytest.raises(NotConnectedError):
        c.test_connection()


def test_shopify_and_stripe_raise_when_missing():
    with pytest.raises(NotConnectedError):
        ShopifyConnector().test_connection()
    with pytest.raises(NotConnectedError):
        StripeConnector().balance()


def test_shopify_configured_uses_real_http_shape(monkeypatch):
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", "demo.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ADMIN_TOKEN", "shpat_test")
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["token"] = req.headers["X-Shopify-Access-Token"]
        return httpx.Response(200, json={"data": {"ordersCount": {"count": 3}}})
    c = ShopifyConnector(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert c.status()["status"] == "connecté"
    assert c.orders_summary() == {"orders_count": 3}
    assert seen["url"].startswith("https://demo.myshopify.com/admin/api/") and seen["token"] == "shpat_test"


def test_stripe_mode_detection(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "rk_test_abc")
    assert StripeConnector().mode() == "test"
