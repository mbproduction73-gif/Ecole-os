"""Registre des connecteurs."""
from .google_trends import GoogleTrendsConnector
from .shopify import ShopifyConnector
from .stripe_conn import StripeConnector
from .stubs import (AliExpressConnector, BigBuyConnector, CJDropshippingConnector, GoogleAdsConnector,
                    MetaAdLibraryConnector, MetaAdsConnector, TikTokAdsConnector,
                    TikTokCreativeCenterConnector, WooCommerceConnector, ZendropConnector)

_CLASSES = [ShopifyConnector, StripeConnector, GoogleTrendsConnector, CJDropshippingConnector,
            ZendropConnector, BigBuyConnector, AliExpressConnector, MetaAdLibraryConnector,
            TikTokCreativeCenterConnector, GoogleAdsConnector, MetaAdsConnector, TikTokAdsConnector,
            WooCommerceConnector]


def all_connectors() -> dict:
    return {c.key: c() for c in _CLASSES}


def get(key: str):
    conns = all_connectors()
    if key not in conns:
        raise KeyError(key)
    return conns[key]


def statuses() -> list[dict]:
    return [c.status() for c in all_connectors().values()]
