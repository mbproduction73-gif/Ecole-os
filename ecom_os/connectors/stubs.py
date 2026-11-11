"""Connecteurs pas encore implémentés : état « non connecté », AUCUNE donnée simulée.

Chaque docstring indique les identifiants nécessaires pour une future intégration.
"""
from .base import Connector, NotConnectedError


class _Stub(Connector):
    implemented = False

    def fetch(self, *args, **kwargs):
        raise NotConnectedError(self.key, self.required_env)

    def test_connection(self) -> dict:
        raise NotConnectedError(self.key, self.required_env)


class CJDropshippingConnector(_Stub):
    """CJdropshipping API v2. Requiert CJ_API_EMAIL + CJ_API_KEY (compte gratuit,
    clé dans Developer > API). Permet catalogue, stock, prix, création de commandes."""
    key, name, category = "cjdropshipping", "CJdropshipping", "fournisseur"
    required_env = ["CJ_API_EMAIL", "CJ_API_KEY"]
    free = "Compte et API gratuits (paiement à la commande)"
    docs = "https://developers.cjdropshipping.com/"


class ZendropConnector(_Stub):
    """Zendrop : pas d'API publique documentée ; intégration via l'app Shopify Zendrop.
    Requiert ZENDROP_API_KEY si un accès partenaire est obtenu."""
    key, name, category = "zendrop", "Zendrop", "fournisseur"
    required_env = ["ZENDROP_API_KEY"]
    free = "Plan gratuit limité ; plans payants pour l'automatisation"
    docs = "https://www.zendrop.com/"


class BigBuyConnector(_Stub):
    """BigBuy API (entrepôt en Espagne, livraison UE rapide). Requiert BIGBUY_API_KEY,
    disponible avec un abonnement BigBuy payant."""
    key, name, category = "bigbuy", "BigBuy (entrepôt UE)", "fournisseur"
    required_env = ["BIGBUY_API_KEY"]
    free = "PAYANT (abonnement requis pour l'API)"
    docs = "https://api.bigbuy.eu/rest/doc"


class AliExpressConnector(_Stub):
    """AliExpress Open Platform (Dropshipping API). Requiert ALIEXPRESS_APP_KEY,
    ALIEXPRESS_APP_SECRET et un jeton OAuth vendeur/affilié (validation de l'app)."""
    key, name, category = "aliexpress", "AliExpress Open Platform", "fournisseur"
    required_env = ["ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET", "ALIEXPRESS_ACCESS_TOKEN"]
    free = "Gratuit (candidature développeur à faire valider)"
    docs = "https://openservice.aliexpress.com/"


class MetaAdLibraryConnector(_Stub):
    """Meta Ad Library API. Requiert META_ADLIB_TOKEN (compte développeur Meta + vérification
    d'identité). Dans l'UE, renvoie les publicités diffusées dans l'UE (DSA)."""
    key, name, category = "meta_ad_library", "Meta Ad Library", "tendances"
    required_env = ["META_ADLIB_TOKEN"]
    free = "Gratuit (vérification d'identité Meta requise)"
    docs = "https://www.facebook.com/ads/library/api/"


class TikTokCreativeCenterConnector(_Stub):
    """TikTok Creative Center : pas d'API publique officielle pour les tendances produits.
    Une intégration passerait par TikTok Business API (TIKTOK_BUSINESS_TOKEN). Consultation manuelle sinon."""
    key, name, category = "tiktok_creative_center", "TikTok Creative Center", "tendances"
    required_env = ["TIKTOK_BUSINESS_TOKEN"]
    free = "Gratuit en consultation web ; pas d'API publique de tendances"
    docs = "https://ads.tiktok.com/business/creativecenter/"


class GoogleAdsConnector(_Stub):
    """Google Ads API. Requiert GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID,
    GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_REFRESH_TOKEN, GOOGLE_ADS_CUSTOMER_ID.
    Toute dépense = niveau C."""
    key, name, category = "google_ads", "Google Ads", "publicite"
    required_env = ["GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET",
                    "GOOGLE_ADS_REFRESH_TOKEN", "GOOGLE_ADS_CUSTOMER_ID"]
    free = "API gratuite ; les publicités sont payantes (niveau C)"
    docs = "https://developers.google.com/google-ads/api/docs/start"


class MetaAdsConnector(_Stub):
    """Meta Marketing API. Requiert META_ACCESS_TOKEN (utilisateur système) + META_AD_ACCOUNT_ID.
    Toute dépense = niveau C."""
    key, name, category = "meta_ads", "Meta Ads (Facebook/Instagram)", "publicite"
    required_env = ["META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID"]
    free = "API gratuite ; les publicités sont payantes (niveau C)"
    docs = "https://developers.facebook.com/docs/marketing-apis"


class TikTokAdsConnector(_Stub):
    """TikTok Business API (Marketing). Requiert TIKTOK_BUSINESS_TOKEN + TIKTOK_ADVERTISER_ID."""
    key, name, category = "tiktok_ads", "TikTok Ads", "publicite"
    required_env = ["TIKTOK_BUSINESS_TOKEN", "TIKTOK_ADVERTISER_ID"]
    free = "API gratuite ; les publicités sont payantes (niveau C)"
    docs = "https://business-api.tiktok.com/portal/docs"


class WooCommerceConnector(_Stub):
    """WooCommerce REST API. Requiert WOO_URL, WOO_CONSUMER_KEY, WOO_CONSUMER_SECRET
    (WooCommerce > Réglages > Avancé > REST API)."""
    key, name, category = "woocommerce", "WooCommerce", "boutique"
    required_env = ["WOO_URL", "WOO_CONSUMER_KEY", "WOO_CONSUMER_SECRET"]
    free = "Plugin gratuit ; hébergement WordPress payant"
    docs = "https://woocommerce.github.io/woocommerce-rest-api-docs/"
