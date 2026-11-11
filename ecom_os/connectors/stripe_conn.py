"""Stripe (lecture seule dans le MVP : solde et paiements récents).

Identifiant requis :
  STRIPE_API_KEY : clé restreinte en LECTURE SEULE recommandée (rk_live_... ou rk_test_...),
                   créée dans Dashboard > Développeurs > Clés API.
Coût : pas d'abonnement ; Stripe prélève une commission par transaction.
"""
import httpx

from ..config import env
from ..core.retry import with_retry
from .base import Connector


class StripeConnector(Connector):
    key = "stripe"
    name = "Stripe"
    category = "paiement"
    required_env = ["STRIPE_API_KEY"]
    free = "Gratuit à connecter (commission par transaction uniquement)"
    docs = "https://docs.stripe.com/api"
    implemented = True

    def __init__(self, client: httpx.Client | None = None):
        self._client = client

    @with_retry(attempts=3, base_delay=1.0, retry_on=(httpx.TransportError,))
    def get(self, path: str, params: dict | None = None) -> dict:
        self.require()
        client = self._client or httpx.Client(timeout=20)
        r = client.get(f"https://api.stripe.com{path}", params=params or {},
                       auth=(env("STRIPE_API_KEY"), ""))
        r.raise_for_status()
        return r.json()

    def mode(self) -> str:
        k = env("STRIPE_API_KEY", "") or ""
        return "test" if "_test_" in k else "live" if "_live_" in k else "inconnu"

    def test_connection(self) -> dict:
        bal = self.get("/v1/balance")
        return {"ok": True, "mode": self.mode(), "livemode": bal.get("livemode"),
                "available": bal.get("available"), "pending": bal.get("pending")}

    def balance(self) -> dict:
        return self.get("/v1/balance")
