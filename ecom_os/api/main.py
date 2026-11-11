"""API FastAPI + tableau de bord statique."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import db
from ..agents import compliance, director, finance, scout, store_builder, supplier
from ..config import env
from ..connectors import csv_import, registry
from ..connectors.base import NotConnectedError
from ..core import permissions, scheduler
from ..core.logs import log_action
from ..core.state import DEFAULT_SETTINGS, all_settings, get_setting, set_setting
from ..models import ActionLog, Approval, Offer, Product, ProductDraft, Store, Supplier, Task

STATIC = Path(__file__).resolve().parent.parent / "dashboard" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.configure()
    if env("DISABLE_SCHEDULER", "0") != "1":
        with db.session_scope() as s:
            hour = int(get_setting(s, "daily_pipeline_hour") or 7)
        scheduler.start(hour=hour)
    yield
    scheduler.shutdown()


app = FastAPI(title="Ecom-OS", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def token_guard(request: Request, call_next):
    """Si DASHBOARD_TOKEN est défini, toutes les routes /api (sauf /api/health) l'exigent."""
    token = env("DASHBOARD_TOKEN")
    p = request.url.path
    if token and p.startswith("/api") and p != "/api/health":
        given = request.headers.get("x-token") or request.query_params.get("token")
        if given != token:
            return JSONResponse({"detail": "Jeton d'accès invalide"}, status_code=401)
    return await call_next(request)


def ser(obj, exclude=()):
    if obj is None:
        return None
    out = {}
    for c in obj.__table__.columns:
        if c.name in exclude:
            continue
        v = getattr(obj, c.name)
        out[c.name] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


# ---------- Santé / synthèse ----------
@app.get("/api/health")
def health():
    return {"ok": True, "scheduler": scheduler.status()}


@app.get("/api/dashboard")
def dashboard(s: Session = Depends(db.get_session)):
    conns = registry.statuses()
    return {
        "products": s.query(Product).count(),
        "shortlist": s.query(Product).filter_by(status="shortlist").count(),
        "suppliers": s.query(Supplier).count(),
        "offers": s.query(Offer).count(),
        "drafts": s.query(ProductDraft).count(),
        "published_drafts": s.query(ProductDraft).filter_by(status="brouillon_shopify").count(),
        "approvals_pending": s.query(Approval).filter_by(status="en_attente").count(),
        "tasks_pending": s.query(Task).filter(Task.status.in_(["en_attente", "en_cours"])).count(),
        "spend_eur": round(sum(l.spend_eur or 0 for l in s.query(ActionLog).all()), 2),
        "connected": [c["key"] for c in conns if c["status"] == "connecté"],
        "settings": {k: get_setting(s, k) for k in ("emergency_stop", "auto_mode", "level_b_enabled",
                                                     "budget_ads_eur", "budget_purchase_eur")},
        "scheduler": scheduler.status(),
    }


# ---------- Produits ----------
class ProductIn(BaseModel):
    name: str = Field(min_length=1)
    keyword: str | None = None
    niche: str | None = None
    problem_solved: str | None = None
    target_customer: str | None = None
    est_sale_price: float | None = Field(default=None, ge=0)
    demand_index: float | None = Field(default=None, ge=0, le=100)
    trend_growth_pct: float | None = None
    competition_level: float | None = Field(default=None, ge=0, le=100)
    marketing_potential: float | None = Field(default=None, ge=0, le=100)
    return_risk: str | None = None
    notes: str | None = None


@app.get("/api/products")
def list_products(s: Session = Depends(db.get_session)):
    rows = s.query(Product).order_by(Product.score_total.desc().nulls_last(), Product.id).all()
    return [ser(p) | {"offers_count": len(p.offers)} for p in rows]


@app.post("/api/products", status_code=201)
def create_product(body: ProductIn, s: Session = Depends(db.get_session)):
    if s.query(Product).filter_by(name=body.name).first():
        raise HTTPException(409, "Un produit avec ce nom existe déjà")
    p = Product(**body.model_dump(), source="manuel")
    p.keyword = p.keyword or p.name
    s.add(p)
    s.flush()
    log_action(s, "proprietaire", "create_product", "execute", f"Produit « {p.name} » ajouté", level="A")
    return ser(p)


@app.get("/api/products/{pid}")
def get_product(pid: int, s: Session = Depends(db.get_session)):
    p = s.get(Product, pid)
    if not p:
        raise HTTPException(404, "Produit introuvable")
    offers = [{k: v for k, v in r.items() if k != "offer"} for r in supplier.rank_offers(s, p)]
    return ser(p) | {"offers": offers, "compliance": compliance.check_product(p)}


@app.post("/api/products/{pid}/reject")
def reject_product(pid: int, s: Session = Depends(db.get_session)):
    p = s.get(Product, pid)
    if not p:
        raise HTTPException(404, "Produit introuvable")
    p.status = "rejete"
    log_action(s, "proprietaire", "analyze", "execute", f"Produit « {p.name} » écarté", level="A")
    return ser(p)


@app.delete("/api/products/{pid}")
def delete_product(pid: int, approval_id: int | None = None, s: Session = Depends(db.get_session)):
    """Suppression définitive = niveau C."""
    p = s.get(Product, pid)
    if not p:
        raise HTTPException(404, "Produit introuvable")
    d, _ = permissions.run_guarded(s, "permanent_delete", lambda: s.delete(p), agent="proprietaire",
                                   payload={"product_id": pid, "name": p.name}, approval_id=approval_id)
    return d.to_dict()


# ---------- Import CSV ----------
@app.post("/api/import/products")
async def import_products(file: UploadFile = File(...), s: Session = Depends(db.get_session)):
    return csv_import.import_products(s, await file.read())


@app.post("/api/import/offers")
async def import_offers(file: UploadFile = File(...), s: Session = Depends(db.get_session)):
    return csv_import.import_offers(s, await file.read())


@app.get("/api/templates/{kind}.csv", response_class=PlainTextResponse)
def csv_template(kind: str):
    if kind not in ("products", "offers"):
        raise HTTPException(404, "Modèle inconnu")
    return PlainTextResponse(csv_import.template(kind), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=modele_{kind}.csv"})


# ---------- Fournisseurs ----------
@app.get("/api/suppliers")
def list_suppliers(s: Session = Depends(db.get_session)):
    return [ser(x) | {"offers_count": len(x.offers)} for x in s.query(Supplier).all()]


@app.get("/api/offers/compare")
def compare_offers(s: Session = Depends(db.get_session)):
    return supplier.compare_all(s)


class SupplierRequestIn(BaseModel):
    product_id: int
    supplier_name: str
    kind: str = "échantillon"


@app.post("/api/suppliers/request")
def supplier_request(body: SupplierRequestIn, s: Session = Depends(db.get_session)):
    p = s.get(Product, body.product_id)
    if not p:
        raise HTTPException(404, "Produit introuvable")
    return supplier.prepare_supplier_request(s, p, body.supplier_name, body.kind)


# ---------- Connecteurs ----------
@app.get("/api/connectors")
def connectors():
    return registry.statuses()


@app.post("/api/connectors/{key}/test")
def test_connector(key: str, s: Session = Depends(db.get_session)):
    try:
        conn = registry.get(key)
    except KeyError:
        raise HTTPException(404, "Connecteur inconnu") from None
    try:
        res = conn.test_connection()
        log_action(s, "systeme", "read_connector", "execute", f"Test {key} réussi", level="A")
        return {"key": key, "status": "connecté", "result": res}
    except NotConnectedError as e:
        log_action(s, "systeme", "read_connector", "non_connecte", str(e), level="A")
        return {"key": key, "status": "non connecté", "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        log_action(s, "systeme", "read_connector", "erreur", f"{key}: {str(e)[:200]}", level="A")
        return {"key": key, "status": "erreur", "detail": str(e)[:300]}


# ---------- Brouillons / boutiques ----------
@app.get("/api/drafts")
def list_drafts(s: Session = Depends(db.get_session)):
    return [ser(d) for d in s.query(ProductDraft).order_by(ProductDraft.id.desc()).all()]


@app.post("/api/products/{pid}/draft", status_code=201)
def create_draft(pid: int, s: Session = Depends(db.get_session)):
    p = s.get(Product, pid)
    if not p:
        raise HTTPException(404, "Produit introuvable")
    d = permissions.authorize(s, "create_draft", agent="store_builder")
    if not d.allowed:
        raise HTTPException(423, d.reason)
    return ser(store_builder.build_draft(s, p))


@app.post("/api/drafts/{did}/publish")
def publish_draft(did: int, s: Session = Depends(db.get_session)):
    d = s.get(ProductDraft, did)
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    return store_builder.publish_draft_to_shopify(s, d)


@app.get("/api/stores")
def list_stores(s: Session = Depends(db.get_session)):
    return [ser(x) for x in s.query(Store).all()]


@app.post("/api/stores/{sid}/launch")
def launch_store(sid: int, approval_id: int | None = None, s: Session = Depends(db.get_session)):
    """Lancement public initial = niveau C (approbation obligatoire)."""
    st = s.get(Store, sid)
    if not st:
        raise HTTPException(404, "Boutique introuvable")

    def _do():
        st.launched = True
        st.status = "lance (à retirer manuellement le mot de passe Shopify)"
    d, _ = permissions.run_guarded(s, "first_public_launch", _do, agent="proprietaire",
                                   payload={"store_id": sid, "name": st.name}, approval_id=approval_id)
    return d.to_dict()


class StoreIn(BaseModel):
    name: str
    platform: str = "shopify"
    domain: str | None = None


@app.post("/api/stores", status_code=201)
def create_store(body: StoreIn, s: Session = Depends(db.get_session)):
    st = Store(name=body.name, platform=body.platform, domain=body.domain, connector_key=body.platform)
    s.add(st)
    s.flush()
    log_action(s, "store_builder", "prepare_store", "execute", f"Boutique « {st.name} » enregistrée", level="A")
    return ser(st)


# ---------- Approbations / autorisations ----------
@app.get("/api/approvals")
def list_approvals(status: str | None = None, s: Session = Depends(db.get_session)):
    q = s.query(Approval)
    if status:
        q = q.filter_by(status=status)
    return [ser(a) for a in q.order_by(Approval.id.desc()).all()]


class DecisionIn(BaseModel):
    note: str = ""


@app.post("/api/approvals/{aid}/approve")
def approve(aid: int, body: DecisionIn | None = None, s: Session = Depends(db.get_session)):
    try:
        return ser(permissions.approve(s, aid, (body or DecisionIn()).note))
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except (ValueError, PermissionError) as e:
        raise HTTPException(409, str(e)) from None


@app.post("/api/approvals/{aid}/reject")
def reject(aid: int, body: DecisionIn | None = None, s: Session = Depends(db.get_session)):
    try:
        return ser(permissions.reject(s, aid, (body or DecisionIn()).note))
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None


class ActionRequestIn(BaseModel):
    action: str
    payload: dict = {}
    amount_eur: float | None = None


@app.post("/api/actions/request")
def request_action(body: ActionRequestIn, s: Session = Depends(db.get_session)):
    """Demande d'autorisation générique (ex. ad_spend, supplier_purchase). N'exécute rien d'externe."""
    return permissions.authorize(s, body.action, agent="proprietaire", payload=body.payload,
                                 amount_eur=body.amount_eur).to_dict()


# ---------- Journal ----------
@app.get("/api/logs")
def logs(limit: int = 200, s: Session = Depends(db.get_session)):
    return [ser(l) for l in s.query(ActionLog).order_by(ActionLog.id.desc()).limit(min(limit, 1000)).all()]


# ---------- Finance ----------
class MarginIn(BaseModel):
    sale_price_ttc: float = Field(gt=0)
    supplier_cost: float = Field(ge=0)
    shipping_cost: float = Field(default=0, ge=0)
    vat_rate: float | None = Field(default=None, ge=0, le=1)
    payment_fee_pct: float | None = Field(default=None, ge=0, le=1)
    payment_fee_fixed: float | None = Field(default=None, ge=0)
    ads_cost_per_order: float = Field(default=0, ge=0)
    variable_fees: float = Field(default=0, ge=0)
    returns_rate: float = Field(default=0.05, ge=0, le=1)


@app.post("/api/finance/calc")
def finance_calc(body: MarginIn, s: Session = Depends(db.get_session)):
    data = body.model_dump()
    for k in ("vat_rate", "payment_fee_pct", "payment_fee_fixed"):
        if data[k] is None:
            data[k] = float(get_setting(s, k))
    try:
        return finance.compute_margin(finance.MarginInput(**data))
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


# ---------- Paramètres ----------
@app.get("/api/settings")
def get_settings(s: Session = Depends(db.get_session)):
    return all_settings(s)


@app.post("/api/settings")
def update_settings(body: dict, s: Session = Depends(db.get_session)):
    unknown = [k for k in body if k not in DEFAULT_SETTINGS]
    if unknown:
        raise HTTPException(422, f"Paramètres inconnus : {unknown}")
    if "emergency_stop" in body:
        raise HTTPException(422, "Utilisez les commandes STOP ALL / reprise pour l'arrêt d'urgence")
    for k, v in body.items():
        set_setting(s, k, v)
    log_action(s, "proprietaire", "settings", "info", f"Paramètres modifiés : {list(body)}")
    return all_settings(s)


# ---------- Commandes du tableau de bord ----------
class CommandIn(BaseModel):
    enable: bool | None = None
    use_trends: bool = True


@app.post("/api/commands/{name}")
def command(name: str, body: CommandIn | None = None, s: Session = Depends(db.get_session)):
    body = body or CommandIn()
    if name == "stop-all":
        set_setting(s, "emergency_stop", True)
        set_setting(s, "auto_mode", False)
        n = s.query(Task).filter(Task.status.in_(["en_attente", "en_cours"])).update({"status": "bloque"})
        log_action(s, "proprietaire", "stop_all", "execute",
                   f"STOP ALL activé : automatisations arrêtées, {n} tâche(s) suspendue(s)")
        return {"emergency_stop": True, "auto_mode": False, "tasks_suspended": n}
    if name == "resume":
        set_setting(s, "emergency_stop", False)
        log_action(s, "proprietaire", "resume", "execute", "Arrêt d'urgence levé (AUTO MODE reste désactivé)")
        return {"emergency_stop": False}
    if name == "auto-mode":
        enable = True if body.enable is None else body.enable
        if enable and get_setting(s, "emergency_stop"):
            raise HTTPException(423, "STOP ALL actif : levez l'arrêt d'urgence avant d'activer AUTO MODE")
        set_setting(s, "auto_mode", enable)
        log_action(s, "proprietaire", "auto_mode", "execute",
                   f"AUTO MODE {'activé' if enable else 'désactivé'} (seules les actions de niveau A/B autorisées)")
        return {"auto_mode": enable, "scheduler": scheduler.status()}

    action_map = {"scan-market": "research", "find-winners": "score_products", "connect-supplier": "read_connector",
                  "build-store": "prepare_store", "create-ads": "prepare_ad_campaign",
                  "optimize-sales": "analyze", "financial-report": "report", "run-pipeline": "report"}
    if name not in action_map:
        raise HTTPException(404, "Commande inconnue")
    d = permissions.authorize(s, action_map[name], agent="director")
    if not d.allowed:
        raise HTTPException(423, d.reason)
    if name == "scan-market":
        return scout.scan_market(s, use_trends=body.use_trends)
    if name == "find-winners":
        return scout.find_winners(s)
    if name == "connect-supplier":
        return supplier.connect_supplier(s)
    if name == "build-store":
        return store_builder.build_store(s)
    if name == "financial-report":
        return finance.financial_report(s)
    if name == "run-pipeline":
        return director.run_daily_pipeline(s, trigger="manuel", use_trends=body.use_trends)
    if name == "create-ads":
        ads = [c.status() for k, c in registry.all_connectors().items() if c.category == "publicite"]
        log_action(s, "creative_studio", "prepare_ad_campaign", "non_connecte",
                   "Aucune régie publicitaire connectée ; aucune campagne créée", level="A")
        return {"status": "non connecté", "ad_platforms": ads,
                "detail": "Aucune régie publicitaire n'est connectée. Rien n'a été créé ni dépensé. "
                          "Toute dépense publicitaire exigera une approbation (niveau C) et un budget > 0 €."}
    if name == "optimize-sales":
        shop = registry.get("shopify")
        if not shop.is_configured():
            log_action(s, "growth", "analyze", "non_connecte", "Shopify non connecté : pas de données de conversion", level="A")
            return {"status": "non connecté",
                    "detail": "Aucune donnée de ventes/conversion disponible : connectez Shopify (SHOPIFY_STORE_DOMAIN, "
                              "SHOPIFY_ADMIN_TOKEN). Aucun chiffre n'est simulé."}
        try:
            r = shop.orders_summary()
        except Exception as e:  # noqa: BLE001
            return {"status": "erreur", "detail": str(e)[:300]}
        log_action(s, "growth", "analyze", "execute", "Lecture des commandes Shopify", level="A")
        return {"status": "connecté", **r, "detail": "Analyse de conversion détaillée : prochaine itération."}


@app.get("/api/reports/latest")
def report_latest(s: Session = Depends(db.get_session)):
    return director.latest_report(s) or {"detail": "Aucun rapport pour le moment"}


@app.get("/api/tasks")
def tasks(s: Session = Depends(db.get_session)):
    return [ser(t, exclude=("result",)) for t in s.query(Task).order_by(Task.id.desc()).limit(50).all()]


# ---------- Tableau de bord ----------
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
