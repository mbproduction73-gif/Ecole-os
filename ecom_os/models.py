"""Modèles de données (état central partagé par tous les agents)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Product(Base):
    """Produit candidat analysé par l'agent Scout."""
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    keyword: Mapped[str | None] = mapped_column(String(255))
    niche: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(60), default="manuel")
    problem_solved: Mapped[str | None] = mapped_column(Text)
    target_customer: Mapped[str | None] = mapped_column(Text)
    est_sale_price: Mapped[float | None] = mapped_column(Float)  # prix TTC envisagé (EUR)
    # Indicateurs bruts (fournis par CSV ou par un connecteur réel ; None = inconnu)
    demand_index: Mapped[float | None] = mapped_column(Float)        # 0-100 (ex. Google Trends)
    trend_growth_pct: Mapped[float | None] = mapped_column(Float)    # croissance en %
    competition_level: Mapped[float | None] = mapped_column(Float)   # 0-100 (100 = saturé)
    marketing_potential: Mapped[float | None] = mapped_column(Float) # 0-100
    return_risk: Mapped[str | None] = mapped_column(String(20))      # faible / moyen / eleve
    # Scores 0-100 par critère
    score_demand: Mapped[float | None] = mapped_column(Float)
    score_margin: Mapped[float | None] = mapped_column(Float)
    score_competition: Mapped[float | None] = mapped_column(Float)
    score_supplier: Mapped[float | None] = mapped_column(Float)
    score_logistics: Mapped[float | None] = mapped_column(Float)
    score_marketing: Mapped[float | None] = mapped_column(Float)
    score_total: Mapped[float | None] = mapped_column(Float)
    data_sufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    score_notes: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="candidat")  # candidat/analyse/shortlist/rejete
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    offers: Mapped[list["Offer"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    platform: Mapped[str | None] = mapped_column(String(60))   # CJdropshipping, BigBuy...
    country: Mapped[str | None] = mapped_column(String(60))
    eu_warehouse: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[float | None] = mapped_column(Float)         # 0-5, vérifiable
    reviews_count: Mapped[int | None] = mapped_column(Integer)
    api_integration: Mapped[bool] = mapped_column(Boolean, default=False)
    return_policy: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    offers: Mapped[list["Offer"]] = relationship(back_populates="supplier")


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    unit_cost: Mapped[float] = mapped_column(Float)
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)
    shipping_days_min: Mapped[int | None] = mapped_column(Integer)
    shipping_days_max: Mapped[int | None] = mapped_column(Integer)
    stock: Mapped[int | None] = mapped_column(Integer)
    ships_from: Mapped[str | None] = mapped_column(String(60))
    customization: Mapped[bool] = mapped_column(Boolean, default=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), default="csv")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="offers")
    supplier: Mapped[Supplier] = relationship(back_populates="offers")


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(40), default="shopify")
    domain: Mapped[str | None] = mapped_column(String(255))
    connector_key: Mapped[str | None] = mapped_column(String(40))
    launched: Mapped[bool] = mapped_column(Boolean, default=False)  # 1er lancement public = niveau C
    status: Mapped[str] = mapped_column(String(30), default="preparation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductDraft(Base):
    __tablename__ = "product_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"))
    title: Mapped[str] = mapped_column(String(255))
    subtitle: Mapped[str | None] = mapped_column(Text)
    description_html: Mapped[str] = mapped_column(Text)
    faq: Mapped[list | None] = mapped_column(JSON)
    shipping_info: Mapped[str | None] = mapped_column(Text)
    returns_info: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Float)
    compliance: Mapped[dict | None] = mapped_column(JSON)
    finance: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="brouillon")  # brouillon/publie_brouillon_shopify
    external_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="en_attente")  # en_attente/en_cours/termine/erreur/bloque
    payload: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    level: Mapped[str] = mapped_column(String(1), default="C")
    payload: Mapped[dict | None] = mapped_column(JSON)
    amount_eur: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="en_attente")  # en_attente/approuve/refuse/execute
    reason: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(60))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionLog(Base):
    __tablename__ = "action_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    agent: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(80))
    level: Mapped[str | None] = mapped_column(String(1))
    # execute / prepare / bloque / approbation_requise / non_connecte / erreur
    outcome: Mapped[str] = mapped_column(String(30))
    message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)
    spend_eur: Mapped[float] = mapped_column(Float, default=0.0)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | str | float | bool | None] = mapped_column(JSON)
