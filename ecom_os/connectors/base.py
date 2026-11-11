"""Interface commune des connecteurs.

Règle absolue : un connecteur non configuré renvoie l'état « non connecté » et lève
NotConnectedError pour toute demande de données. Il ne renvoie JAMAIS de données simulées.
"""
from ..config import env
from ..core.retry import NonRetryableError

CONNECTE = "connecté"
NON_CONNECTE = "non connecté"
ERREUR = "erreur"


class NotConnectedError(NonRetryableError):
    def __init__(self, key: str, missing: list[str] | None = None):
        self.key = key
        self.missing = missing or []
        msg = f"Intégration « {key} » non connectée"
        if self.missing:
            msg += f" (variables manquantes : {', '.join(self.missing)})"
        super().__init__(msg)


class Connector:
    key: str = "base"
    name: str = "Base"
    category: str = "autre"          # boutique / paiement / tendances / fournisseur / publicite
    required_env: list[str] = []
    free: str = "?"                  # info coût pour le propriétaire
    docs: str = ""
    implemented: bool = False        # True si l'appel API réel est codé dans le MVP

    def missing_env(self) -> list[str]:
        return [k for k in self.required_env if not env(k)]

    def is_configured(self) -> bool:
        return self.implemented and not self.missing_env()

    def require(self):
        if not self.is_configured():
            raise NotConnectedError(self.key, self.missing_env())

    def status(self) -> dict:
        configured = self.is_configured()
        if not self.implemented:
            detail = "Interface prête, intégration API pas encore implémentée dans le MVP. Aucune donnée simulée."
        elif configured:
            detail = "Identifiants présents. Utilisez « Tester » pour vérifier la connexion réelle."
        else:
            detail = "Identifiants manquants : " + ", ".join(self.missing_env())
        return {
            "key": self.key, "name": self.name, "category": self.category,
            "status": CONNECTE if configured else NON_CONNECTE,
            "implemented": self.implemented, "required_env": self.required_env,
            "missing_env": self.missing_env() if self.implemented else self.required_env,
            "cost": self.free, "detail": detail, "docs": self.docs,
        }

    def test_connection(self) -> dict:
        """Appel réel minimal. Les sous-classes implémentées le surchargent."""
        self.require()
        return {"ok": True}
