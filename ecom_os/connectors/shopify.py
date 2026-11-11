"""Shopify Admin API (GraphQL).

Identifiants requis :
  SHOPIFY_STORE_DOMAIN : ex. maboutique.myshopify.com
  SHOPIFY_ADMIN_TOKEN  : jeton Admin API d'une app personnalisée (Paramètres > Apps >
                         Développer des apps), scopes : read_products, write_products,
                         read_orders, read_inventory.
Coût : inclus dans l'abonnement Shopify (pas de frais API).
"""
import httpx

from ..config import env
from ..core.retry import with_retry
from .base import Connector

API_VERSION = "2025-10"


class ShopifyConnector(Connector):
    key = "shopify"
    name = "Shopify Admin API"
    category = "boutique"
    required_env = ["SHOPIFY_STORE_DOMAIN", "SHOPIFY_ADMIN_TOKEN"]
    free = "Gratuit (inclus dans l'abonnement Shopify)"
    docs = "https://shopify.dev/docs/api/admin-graphql"
    implemented = True

    def __init__(self, client: httpx.Client | None = None):
        self._client = client

    def _url(self):
        domain = env("SHOPIFY_STORE_DOMAIN", "").replace("https://", "").strip("/")
        version = env("SHOPIFY_API_VERSION", API_VERSION)
        return f"https://{domain}/admin/api/{version}/graphql.json"

    @with_retry(attempts=3, base_delay=1.0, retry_on=(httpx.TransportError,))
    def graphql(self, query: str, variables: dict | None = None) -> dict:
        self.require()
        client = self._client or httpx.Client(timeout=20)
        r = client.post(self._url(), json={"query": query, "variables": variables or {}},
                        headers={"X-Shopify-Access-Token": env("SHOPIFY_ADMIN_TOKEN"),
                                 "Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            raise RuntimeError(f"Erreur Shopify : {data['errors']}")
        return data["data"]

    def test_connection(self) -> dict:
        d = self.graphql("{ shop { name myshopifyDomain currencyCode plan { publicDisplayName } } "
                         "productsCount { count } }")
        return {"ok": True, "shop": d["shop"], "products_count": d["productsCount"]["count"]}

    def list_products(self, first: int = 50) -> list[dict]:
        d = self.graphql("query($n:Int!){ products(first:$n){ nodes{ id title status totalInventory } } }",
                         {"n": first})
        return d["products"]["nodes"]

    def orders_summary(self) -> dict:
        d = self.graphql("{ ordersCount { count } }")
        return {"orders_count": d["ordersCount"]["count"]}

    def create_draft_product(self, title: str, description_html: str, price: float | None) -> dict:
        """Crée le produit en statut DRAFT (réversible, invisible des clients). Niveau B."""
        q = ("mutation($p: ProductCreateInput!){ productCreate(product:$p){ product{ id title status } "
             "userErrors{ field message } } }")
        d = self.graphql(q, {"p": {"title": title, "descriptionHtml": description_html, "status": "DRAFT"}})
        res = d["productCreate"]
        if res["userErrors"]:
            raise RuntimeError(f"Shopify userErrors : {res['userErrors']}")
        return res["product"]
