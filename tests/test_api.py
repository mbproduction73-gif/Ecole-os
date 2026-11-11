from .conftest import OFFERS_CSV, PRODUCTS_CSV


def test_health_and_dashboard(client):
    h = client.get("/api/health").json()
    assert h["ok"] is True and h["database"] == "sqlite"
    d = client.get("/api/dashboard").json()
    assert d["products"] == 0 and d["settings"]["emergency_stop"] is False and d["spend_eur"] == 0


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "STOP ALL" in r.text and "SCAN MARKET" in r.text


def test_import_score_draft_flow(client):
    r = client.post("/api/import/products", files={"file": ("p.csv", PRODUCTS_CSV, "text/csv")})
    assert r.json()["created"] == 2
    r = client.post("/api/import/offers", files={"file": ("o.csv", OFFERS_CSV, "text/csv")})
    assert r.json()["created"] == 2
    w = client.post("/api/commands/find-winners").json()
    assert len(w["ranked"]) == 1
    b = client.post("/api/commands/build-store").json()
    assert len(b["drafts_created"]) == 1
    drafts = client.get("/api/drafts").json()
    assert len(drafts) == 1
    pub = client.post(f"/api/drafts/{drafts[0]['id']}/publish").json()
    assert pub["status"] == "non connecté"


def test_commands_not_connected_say_so(client):
    assert client.post("/api/commands/create-ads").json()["status"] == "non connecté"
    assert client.post("/api/commands/optimize-sales").json()["status"] == "non connecté"
    fr = client.post("/api/commands/financial-report").json()
    assert fr["sources"]["shopify"]["status"] == "non connecté"
    assert fr["sources"]["stripe"]["status"] == "non connecté"
    t = client.post("/api/connectors/cjdropshipping/test").json()
    assert t["status"] == "non connecté"
    sm = client.post("/api/commands/scan-market", json={"use_trends": True}).json()
    assert sm["google_trends"]["status"] == "non connecté"  # désactivé dans les tests


def test_stop_all_and_auto_mode(client):
    assert client.post("/api/commands/auto-mode", json={"enable": True}).json()["auto_mode"] is True
    r = client.post("/api/commands/stop-all").json()
    assert r["emergency_stop"] is True and r["auto_mode"] is False
    assert client.post("/api/commands/find-winners").status_code == 423
    assert client.post("/api/commands/auto-mode", json={"enable": True}).status_code == 423
    a = client.post("/api/actions/request", json={"action": "ad_spend", "amount_eur": 10}).json()
    assert a["status"] == "bloque_stop"
    client.post("/api/commands/resume")
    assert client.post("/api/commands/find-winners").status_code == 200


def test_approval_endpoints(client):
    a = client.post("/api/actions/request", json={"action": "ad_spend", "amount_eur": 10,
                                                  "payload": {"reason": "test"}}).json()
    assert a["status"] == "approbation_requise"
    pend = client.get("/api/approvals?status=en_attente").json()
    assert len(pend) == 1
    r = client.post(f"/api/approvals/{a['approval_id']}/approve", json={"note": ""})
    assert r.status_code == 409  # budget pub = 0 €
    client.post("/api/settings", json={"budget_ads_eur": 15})
    assert client.post(f"/api/approvals/{a['approval_id']}/approve").json()["status"] == "approuve"


def test_delete_requires_approval(client):
    p = client.post("/api/products", json={"name": "X"}).json()
    r = client.delete(f"/api/products/{p['id']}").json()
    assert r["status"] == "approbation_requise"
    assert client.get(f"/api/products/{p['id']}").status_code == 200
    client.post(f"/api/approvals/{r['approval_id']}/approve")
    r2 = client.delete(f"/api/products/{p['id']}?approval_id={r['approval_id']}").json()
    assert r2["allowed"] is True
    assert client.get(f"/api/products/{p['id']}").status_code == 404


def test_finance_endpoint(client):
    r = client.post("/api/finance/calc", json={"sale_price_ttc": 30.25, "supplier_cost": 8, "shipping_cost": 4,
                                               "vat_rate": 0.21}).json()
    assert r["price_ht"] == 25.0
    assert client.post("/api/finance/calc", json={"sale_price_ttc": 0, "supplier_cost": 1}).status_code == 422


def test_settings_guard(client):
    assert client.post("/api/settings", json={"emergency_stop": False}).status_code == 422
    assert client.post("/api/settings", json={"inconnu": 1}).status_code == 422


def test_pipeline_report_separates_sections(client):
    client.post("/api/import/products", files={"file": ("p.csv", PRODUCTS_CSV, "text/csv")})
    client.post("/api/import/offers", files={"file": ("o.csv", OFFERS_CSV, "text/csv")})
    r = client.post("/api/commands/run-pipeline", json={"use_trends": False}).json()
    for k in ["executed", "prepared", "needs_approval", "not_connected", "errors", "spend_eur", "next_priorities"]:
        assert k in r
    assert r["spend_eur"] == 0 and r["errors"] == []
    assert any("Studio" in x for x in r["not_connected"])
    assert client.get("/api/reports/latest").json()["task_id"] == r["task_id"]


def test_token_guard(client, monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret")
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers={"x-token": "secret"}).status_code == 200
    assert client.get("/api/health").status_code == 200
