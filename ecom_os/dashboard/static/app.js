const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const token = () => localStorage.getItem("ecomos_token") || "";
async function api(path, opts = {}) {
  opts.headers = Object.assign({"x-token": token()}, opts.headers || {});
  if (opts.json !== undefined) { opts.body = JSON.stringify(opts.json); opts.headers["Content-Type"] = "application/json"; delete opts.json; }
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : r.statusText);
  return data;
}
const show = (x) => { $("#output").textContent = typeof x === "string" ? x : JSON.stringify(x, null, 2); };
function table(rows, cols) {
  if (!rows || !rows.length) return "<p class='muted'>Aucune donnée.</p>";
  return "<table><thead><tr>" + cols.map(c => `<th>${esc(c[1])}</th>`).join("") + "</tr></thead><tbody>" +
    rows.map(r => "<tr>" + cols.map(c => `<td>${c[2] ? c[2](r) : esc(r[c[0]] ?? "—")}</td>`).join("") + "</tr>").join("") + "</tbody></table>";
}

async function loadOverview() {
  const d = await api("/api/dashboard");
  $("#stopBadge").classList.toggle("hidden", !d.settings.emergency_stop);
  $("#autoBadge").classList.toggle("hidden", !d.settings.auto_mode);
  const cards = [["Produits analysés", d.products], ["Shortlist", d.shortlist], ["Fournisseurs", d.suppliers], ["Offres", d.offers],
    ["Brouillons", d.drafts], ["Publiés (brouillon Shopify)", d.published_drafts], ["Validations requises", d.approvals_pending],
    ["Tâches en attente", d.tasks_pending], ["Dépenses enregistrées", d.spend_eur + " €"],
    ["Connecteurs actifs", d.connected.length ? d.connected.join(", ") : "aucun"],
    ["Commandes / CA / Pubs", d.connected.includes("shopify") ? "voir FINANCIAL REPORT" : "non connecté"],
    ["Prochain pipeline", d.scheduler.running && d.settings.auto_mode ? (d.scheduler.next_run || "—") : "AUTO MODE inactif"]];
  $("#cards").innerHTML = cards.map(([k, v]) => `<div class="card">${esc(k)}<b>${esc(v)}</b></div>`).join("");
  const rep = await api("/api/reports/latest");
  if (!rep.task_id) { $("#report").innerHTML = "<p class='muted'>Aucun rapport. Lancez « PIPELINE DU JOUR ».</p>"; return; }
  const list = (t, a) => `<h4>${esc(t)} (${a.length})</h4><ul>` + a.map(x => `<li>${esc(typeof x === "string" ? x : JSON.stringify(x))}</li>`).join("") + "</ul>";
  $("#report").innerHTML = `<p class="muted">Rapport #${rep.task_id} – ${esc(rep.date)} – dépenses : ${rep.spend_eur} €</p>` +
    list("Exécuté", rep.executed) + list("Préparé", rep.prepared) + list("Validation requise", rep.needs_approval) +
    list("Non connecté", rep.not_connected) + list("Bloqué", rep.blocked || []) + list("Erreurs", rep.errors) + list("Prochaines priorités", rep.next_priorities);
}
async function loadProducts() {
  const rows = await api("/api/products");
  $("#productsTable").innerHTML = table(rows, [["name","Produit"],["status","Statut"],["score_total","Score /100",r => r.data_sufficient ? esc(r.score_total) : "<span class='st-non'>données insuffisantes</span>"],
    ["score_demand","Demande"],["score_margin","Marge"],["score_competition","Concurrence"],["score_supplier","Fournisseur"],["score_logistics","Logistique"],["score_marketing","Marketing"],
    ["est_sale_price","Prix TTC"],["offers_count","Offres"],["id","Actions",r => `<button class="secondary" onclick="mkDraft(${r.id})">Brouillon</button> <button class="secondary" onclick="rejectP(${r.id})">Écarter</button>`]]);
}
window.mkDraft = async (id) => { try { show(await api(`/api/products/${id}/draft`, {method:"POST"})); refresh(); } catch (e) { show("Erreur : " + e.message); } };
window.rejectP = async (id) => { await api(`/api/products/${id}/reject`, {method:"POST"}); refresh(); };
async function loadSuppliers() {
  $("#suppliersTable").innerHTML = table(await api("/api/suppliers"), [["name","Fournisseur"],["platform","Plateforme"],["country","Pays"],["eu_warehouse","Entrepôt UE",r=>r.eu_warehouse?"oui":"non"],["rating","Note /5"],["reviews_count","Avis"],["offers_count","Offres"]]);
  const cmp = await api("/api/offers/compare");
  $("#compare").innerHTML = cmp.map(p => `<h4>${esc(p.product)}</h4>` + table(p.offers, [["supplier","Fournisseur"],["landed_cost","Coût rendu €"],["days_max","Délai max (j)"],["eu_warehouse","UE",r=>r.eu_warehouse?"oui":"non"],["rating","Note"],["stock","Stock"],["score","Score offre"]])).join("");
}
async function loadConnectors() {
  $("#connectorsTable").innerHTML = table(await api("/api/connectors"), [["name","Intégration"],["category","Catégorie"],
    ["status","État",r => `<span class="${r.status === "connecté" ? "st-connecte" : "st-non"}">${esc(r.status)}</span>`],["detail","Détail"],["cost","Coût"],
    ["missing_env","Identifiants requis",r => esc((r.required_env||[]).join(", ") || "aucun")],["key","Test",r => `<button class="secondary" onclick="testConn('${r.key}')">Tester</button>`]]);
}
window.testConn = async (k) => { show("Test en cours…"); try { show(await api(`/api/connectors/${k}/test`, {method:"POST"})); } catch (e) { show("Erreur : " + e.message); } };
async function loadDrafts() {
  const rows = await api("/api/drafts");
  $("#draftsList").innerHTML = rows.length ? rows.map(d => `<div class="draft"><h3>#${d.id} ${esc(d.title)} <small>(${esc(d.status)})</small></h3>
    <p>${esc(d.subtitle)}</p><div class="desc">${d.description_html}</div>
    <h4>FAQ</h4><ul>${(d.faq||[]).map(f => `<li><b>${esc(f.q)}</b> ${esc(f.a)}</li>`).join("")}</ul>
    <h4>Marge estimée</h4><p>${d.finance ? `Marge contributive (sans pub) : ${d.finance.contribution_margin} € – CPA de rentabilité : ${d.finance.break_even_cpa ?? "—"} € – ROAS de rentabilité : ${d.finance.break_even_roas ?? "—"}` : "Données insuffisantes (prix ou offre manquant)"}</p>
    <h4>Conformité (risque ${esc(d.compliance?.risk)})</h4><ul>${(d.compliance?.items||[]).map(i => `<li>${esc(i.label)} – <i>${esc(i.status)}</i></li>`).join("")}</ul>
    <button onclick="publishDraft(${d.id})">Publier en brouillon Shopify (niveau B)</button></div>`).join("") : "<p class='muted'>Aucun brouillon. Utilisez FIND WINNERS puis BUILD STORE, ou le bouton « Brouillon » d'un produit.</p>";
}
window.publishDraft = async (id) => { try { show(await api(`/api/drafts/${id}/publish`, {method:"POST"})); refresh(); } catch (e) { show("Erreur : " + e.message); } };
async function loadApprovals() {
  const rows = await api("/api/approvals");
  $("#approvalsList").innerHTML = table(rows, [["id","#"],["action","Action"],["amount_eur","Montant €"],["status","Statut"],["requested_by","Demandé par"],["payload","Détails",r => esc(JSON.stringify(r.payload))],["created_at","Date"],
    ["id","Décision",r => r.status === "en_attente" ? `<button onclick="decide(${r.id},'approve')">Approuver</button> <button class="danger" onclick="decide(${r.id},'reject')">Refuser</button>` : "—"]]);
}
window.decide = async (id, what) => { try { show(await api(`/api/approvals/${id}/${what}`, {method:"POST", json:{note:""}})); } catch (e) { show("Refusé : " + e.message); } refresh(); };
async function loadLogs() {
  $("#logsTable").innerHTML = table(await api("/api/logs"), [["ts","Date"],["agent","Agent"],["action","Action"],["level","Niveau"],["outcome","Résultat"],["message","Message"],["spend_eur","Dépense €"]]);
}
async function loadSettings() {
  const s = await api("/api/settings");
  const keys = ["level_b_enabled","budget_ads_eur","budget_purchase_eur","sensitive_price_change_pct","vat_rate","payment_fee_pct","payment_fee_fixed","daily_pipeline_hour"];
  $("#settingsForm").innerHTML = keys.map(k => typeof s[k] === "boolean"
    ? `<label>${k}<select name="${k}"><option value="false" ${!s[k]?"selected":""}>non</option><option value="true" ${s[k]?"selected":""}>oui</option></select></label>`
    : `<label>${k}<input name="${k}" type="number" step="any" value="${esc(s[k])}"></label>`).join("") + "<button>Enregistrer</button>";
  $("#tokenInput").value = token();
}
$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault(); const body = {};
  for (const [k, v] of new FormData(e.target)) body[k] = v === "true" ? true : v === "false" ? false : Number(v);
  try { show(await api("/api/settings", {method:"POST", json: body})); } catch (err) { show("Erreur : " + err.message); }
});
$("#saveToken").onclick = () => { localStorage.setItem("ecomos_token", $("#tokenInput").value); refresh(); };
$("#financeForm").addEventListener("submit", async (e) => {
  e.preventDefault(); const body = {};
  for (const [k, v] of new FormData(e.target)) if (v !== "") body[k] = Number(v);
  try { const r = await api("/api/finance/calc", {method:"POST", json: body});
    $("#financeResult").innerHTML = table([r], [["price_ht","Prix HT"],["vat","TVA"],["payment_fees","Frais paiement"],["returns_provision","Provision retours"],["margin_before_ads","Marge avant pub"],["contribution_margin","Marge contributive"],["contribution_margin_pct","% du HT"],["break_even_cpa","CPA rentabilité"],["break_even_roas","ROAS rentabilité"],["profitable","Rentable",x=>x.profitable?"oui":"non"]]) + `<p class="muted">${esc(r.note)}</p>`;
  } catch (err) { $("#financeResult").textContent = "Erreur : " + err.message; }
});
async function upload(form, url) {
  const fd = new FormData(form);
  try { show(await api(url, {method:"POST", body: fd})); } catch (e) { show("Erreur : " + e.message); }
  refresh();
}
$("#importProducts").addEventListener("submit", e => { e.preventDefault(); upload(e.target, "/api/import/products"); });
$("#importOffers").addEventListener("submit", e => { e.preventDefault(); upload(e.target, "/api/import/offers"); });
$("#addProduct").addEventListener("submit", async (e) => {
  e.preventDefault(); const body = {};
  for (const [k, v] of new FormData(e.target)) if (v !== "") body[k] = e.target.elements[k].type === "number" ? Number(v) : v;
  try { show(await api("/api/products", {method:"POST", json: body})); e.target.reset(); } catch (err) { show("Erreur : " + err.message); }
  refresh();
});
document.querySelectorAll("[data-cmd]").forEach(b => b.onclick = async () => {
  show(`${b.textContent} en cours…`);
  try { show(await api(`/api/commands/${b.dataset.cmd}`, {method:"POST", json:{}})); } catch (e) { show(`${b.textContent} : ${e.message}`); }
  refresh();
});
$("#stopBtn").onclick = async () => {
  const stopped = !$("#stopBadge").classList.contains("hidden");
  if (stopped) { if (!confirm("Lever l'arrêt d'urgence ?")) return; show(await api("/api/commands/resume", {method:"POST"})); }
  else { show(await api("/api/commands/stop-all", {method:"POST"})); }
  refresh();
};
$("#autoBtn").onclick = async () => {
  const on = !$("#autoBadge").classList.contains("hidden");
  try { show(await api("/api/commands/auto-mode", {method:"POST", json:{enable: !on}})); } catch (e) { show("AUTO MODE : " + e.message); }
  refresh();
};
const loaders = {overview: loadOverview, products: loadProducts, suppliers: loadSuppliers, connectors: loadConnectors, drafts: loadDrafts, approvals: loadApprovals, logs: loadLogs, settings: loadSettings, finance: async () => {}};
let current = "overview";
document.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => {
  document.querySelectorAll("[data-tab]").forEach(x => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + b.dataset.tab));
  current = b.dataset.tab; refresh();
});
async function refresh() {
  try { await loadOverview(); if (current !== "overview") await loaders[current](); }
  catch (e) { show("Erreur de chargement : " + e.message); }
}
refresh();
