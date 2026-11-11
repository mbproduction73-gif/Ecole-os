"""Google Trends via la bibliothèque gratuite pytrends (API NON officielle).

Aucun identifiant requis. Limites : pas de garantie de service, Google peut limiter
le nombre de requêtes (erreur 429). Les valeurs sont un indice relatif 0-100, pas un volume.
"""
from ..config import env
from ..core.retry import with_retry
from .base import CONNECTE, Connector, NON_CONNECTE

try:  # pragma: no cover - dépend de l'environnement
    from pytrends.request import TrendReq
    _AVAILABLE = True
except Exception:  # pragma: no cover
    TrendReq = None
    _AVAILABLE = False


class GoogleTrendsConnector(Connector):
    key = "google_trends"
    name = "Google Trends (pytrends, non officiel)"
    category = "tendances"
    required_env = []
    free = "Gratuit (non officiel, limité en fréquence)"
    docs = "https://github.com/GeneralMills/pytrends"
    implemented = _AVAILABLE

    def is_configured(self) -> bool:
        return _AVAILABLE and env("GOOGLE_TRENDS_DISABLED", "0") != "1"

    def status(self) -> dict:
        s = super().status()
        if not _AVAILABLE:
            s.update(status=NON_CONNECTE, detail="Bibliothèque pytrends indisponible.")
        elif env("GOOGLE_TRENDS_DISABLED", "0") == "1":
            s.update(status=NON_CONNECTE, detail="Désactivé (GOOGLE_TRENDS_DISABLED=1).")
        else:
            s.update(status=CONNECTE, detail="Sans clé. API non officielle : peut être limitée (429).")
        return s

    @with_retry(attempts=2, base_delay=5.0)
    def interest(self, keyword: str, geo: str = "BE", timeframe: str = "today 3-m") -> dict:
        """Indice moyen 0-100 sur la période + croissance (moyenne dernier tiers vs premier tiers)."""
        self.require()
        p = TrendReq(hl="fr-BE", tz=-60, timeout=(5, 20))
        p.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = p.interest_over_time()
        if df is None or df.empty or keyword not in df:
            return {"keyword": keyword, "geo": geo, "points": 0, "mean": None, "growth_pct": None}
        series = df[keyword].astype(float)
        n = len(series)
        third = max(1, n // 3)
        first, last = series.iloc[:third].mean(), series.iloc[-third:].mean()
        growth = None if first == 0 else round((last - first) / first * 100, 1)
        return {"keyword": keyword, "geo": geo, "timeframe": timeframe, "points": n,
                "mean": round(float(series.mean()), 1), "max": float(series.max()), "growth_pct": growth}

    def test_connection(self) -> dict:
        return {"ok": True, **self.interest("dropshipping", geo="BE")}
