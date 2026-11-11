"""Import manuel CSV (produits candidats et offres fournisseurs).

Rend le système utile immédiatement sans aucune API. Séparateur , ou ; détecté automatiquement.
Les lignes invalides sont rejetées avec un message ; rien n'est inventé.
"""
import csv
import io

from sqlalchemy.orm import Session

from ..core.logs import log_action
from ..models import Offer, Product, Supplier

PRODUCT_COLUMNS = ["name", "keyword", "niche", "problem_solved", "target_customer", "est_sale_price",
                   "demand_index", "trend_growth_pct", "competition_level", "marketing_potential",
                   "return_risk", "source", "notes"]
OFFER_COLUMNS = ["product_name", "supplier_name", "platform", "supplier_country", "eu_warehouse",
                 "supplier_rating", "reviews_count", "unit_cost", "shipping_cost", "shipping_days_min",
                 "shipping_days_max", "stock", "ships_from", "customization", "api_integration",
                 "return_policy", "url"]


def _f(v, field, lo=None, hi=None):
    if v is None or str(v).strip() == "":
        return None
    try:
        x = float(str(v).replace(",", ".").replace("€", "").strip())
    except ValueError as e:
        raise ValueError(f"{field} : nombre invalide « {v} »") from e
    if lo is not None and x < lo or hi is not None and x > hi:
        raise ValueError(f"{field} : {x} hors limites [{lo}, {hi}]")
    return x


def _i(v, field):
    x = _f(v, field, lo=0)
    return None if x is None else int(x)


def _b(v):
    return str(v or "").strip().lower() in {"1", "oui", "yes", "true", "vrai", "x"}


def _s(v):
    v = (v or "").strip()
    return v or None


def _reader(content: str | bytes):
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    content = content.lstrip("\ufeff")
    sample = content[:2048]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    return csv.DictReader(io.StringIO(content), delimiter=delim)


def import_products(session: Session, content: str | bytes) -> dict:
    created, updated, errors = 0, 0, []
    reader = _reader(content)
    if not reader.fieldnames or "name" not in [f.strip() for f in reader.fieldnames]:
        return {"created": 0, "updated": 0, "errors": [{"line": 1, "error": "Colonne obligatoire « name » absente"}]}
    for n, raw in enumerate(reader, start=2):
        row = {(k or "").strip(): v for k, v in raw.items()}
        try:
            name = _s(row.get("name"))
            if not name:
                raise ValueError("name vide")
            values = dict(
                keyword=_s(row.get("keyword")) or name, niche=_s(row.get("niche")),
                problem_solved=_s(row.get("problem_solved")), target_customer=_s(row.get("target_customer")),
                est_sale_price=_f(row.get("est_sale_price"), "est_sale_price", lo=0),
                demand_index=_f(row.get("demand_index"), "demand_index", 0, 100),
                trend_growth_pct=_f(row.get("trend_growth_pct"), "trend_growth_pct", -100, 10000),
                competition_level=_f(row.get("competition_level"), "competition_level", 0, 100),
                marketing_potential=_f(row.get("marketing_potential"), "marketing_potential", 0, 100),
                return_risk=_s(row.get("return_risk")), source=_s(row.get("source")) or "csv",
                notes=_s(row.get("notes")),
            )
            p = session.query(Product).filter_by(name=name).one_or_none()
            if p is None:
                session.add(Product(name=name, **values))
                created += 1
            else:
                for k, v in values.items():
                    if v is not None:
                        setattr(p, k, v)
                updated += 1
        except ValueError as e:
            errors.append({"line": n, "error": str(e)})
    session.flush()
    log_action(session, "import", "import_csv_products", "execute",
               f"{created} créés, {updated} mis à jour, {len(errors)} erreurs", level="A")
    return {"created": created, "updated": updated, "errors": errors}


def import_offers(session: Session, content: str | bytes) -> dict:
    created, errors = 0, []
    reader = _reader(content)
    needed = {"product_name", "supplier_name", "unit_cost"}
    if not reader.fieldnames or not needed.issubset({f.strip() for f in reader.fieldnames}):
        return {"created": 0, "errors": [{"line": 1, "error": f"Colonnes obligatoires : {sorted(needed)}"}]}
    for n, raw in enumerate(reader, start=2):
        row = {(k or "").strip(): v for k, v in raw.items()}
        try:
            pname, sname = _s(row.get("product_name")), _s(row.get("supplier_name"))
            if not pname or not sname:
                raise ValueError("product_name et supplier_name obligatoires")
            product = session.query(Product).filter_by(name=pname).one_or_none()
            if product is None:
                raise ValueError(f"produit « {pname} » inconnu : importez d'abord les produits")
            unit_cost = _f(row.get("unit_cost"), "unit_cost", lo=0)
            if unit_cost is None:
                raise ValueError("unit_cost obligatoire")
            sup = session.query(Supplier).filter_by(name=sname).one_or_none()
            if sup is None:
                sup = Supplier(name=sname)
                session.add(sup)
            sup.platform = _s(row.get("platform")) or sup.platform
            sup.country = _s(row.get("supplier_country")) or sup.country
            if row.get("eu_warehouse") not in (None, ""):
                sup.eu_warehouse = _b(row.get("eu_warehouse"))
            if row.get("api_integration") not in (None, ""):
                sup.api_integration = _b(row.get("api_integration"))
            r = _f(row.get("supplier_rating"), "supplier_rating", 0, 5)
            if r is not None:
                sup.rating = r
            rc = _i(row.get("reviews_count"), "reviews_count")
            if rc is not None:
                sup.reviews_count = rc
            sup.return_policy = _s(row.get("return_policy")) or sup.return_policy
            session.flush()
            dmin = _i(row.get("shipping_days_min"), "shipping_days_min")
            dmax = _i(row.get("shipping_days_max"), "shipping_days_max")
            if dmin is not None and dmax is not None and dmin > dmax:
                raise ValueError("shipping_days_min > shipping_days_max")
            session.add(Offer(product_id=product.id, supplier_id=sup.id, unit_cost=unit_cost,
                              shipping_cost=_f(row.get("shipping_cost"), "shipping_cost", lo=0) or 0.0,
                              shipping_days_min=dmin, shipping_days_max=dmax,
                              stock=_i(row.get("stock"), "stock"), ships_from=_s(row.get("ships_from")),
                              customization=_b(row.get("customization")), url=_s(row.get("url")), source="csv"))
            created += 1
        except ValueError as e:
            errors.append({"line": n, "error": str(e)})
    session.flush()
    log_action(session, "import", "import_csv_offers", "execute",
               f"{created} offres créées, {len(errors)} erreurs", level="A")
    return {"created": created, "errors": errors}


def template(kind: str) -> str:
    cols = PRODUCT_COLUMNS if kind == "products" else OFFER_COLUMNS
    return ",".join(cols) + "\n"
