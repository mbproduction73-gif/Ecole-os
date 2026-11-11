# Ecom-OS — MVP

Système e-commerce automatisé et **supervisé** : recherche de produits, sourcing, fiches produits,
gestion de boutique. Aucune donnée simulée : toute intégration absente est affichée **« non connecté »**.
Aucune dépense n'est possible sans votre validation (budgets à **0 €** par défaut).

Voir [ARCHITECTURE.md](ARCHITECTURE.md) pour le schéma et les règles.

## Ce que fait le MVP

- **Produits** : import CSV ou saisie, notation /100 (6 critères), « données insuffisantes » si les données manquent.
- **Fournisseurs** : import CSV d'offres, comparaison (coût rendu, délai, note, entrepôt UE, stock), brouillon de demande d'échantillon/devis (non envoyé).
- **Fiches produits** : brouillons en français (titre, description orientée bénéfices avec « À COMPLÉTER » là où une donnée vérifiée manque, FAQ, livraison, rétractation 14 jours, garantie 2 ans), marge estimée, contrôle de conformité BE/UE.
- **Finance** : calculateur de marge contributive, CPA et ROAS de rentabilité ; rapport financier uniquement à partir de Shopify/Stripe connectés.
- **Autorisations** : niveaux A/B/C, approbations, STOP ALL, journal complet.
- **Planificateur** : pipeline quotidien (7h, Europe/Brussels) quand AUTO MODE est actif.
- **Tableau de bord** web utilisable sur téléphone Android et PC Windows (installable comme application web).

## Lancer en local

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # puis remplissez ce qui est disponible
uvicorn ecom_os.api.main:app --reload --port 8000
```

Ouvrez http://localhost:8000 . Tests : `pytest -q`.

Avec Docker : `cp .env.example .env && docker compose up --build`.

### Démarrer sans aucune API

1. Onglet **Produits** → téléchargez le *modèle CSV* (`templates/modele_produits.csv`), remplissez-le avec des
   données que vous avez vérifiées (ex. indice Google Trends, prix observés), importez-le.
2. Onglet **Fournisseurs** → importez vos offres (`templates/modele_offres.csv`) relevées sur CJdropshipping, BigBuy, etc.
3. **FIND WINNERS** → classement ; **BUILD STORE** → brouillons pour la shortlist.
4. Relisez les brouillons, complétez les « À COMPLÉTER », vérifiez la liste de conformité.

Colonnes produits : `name` (obligatoire), `keyword`, `niche`, `problem_solved`, `target_customer`, `est_sale_price`
(TTC), `demand_index` (0-100), `trend_growth_pct`, `competition_level` (0-100, 100 = saturé), `marketing_potential`
(0-100), `return_risk` (faible/moyen/eleve), `source`, `notes`.
Colonnes offres : `product_name`, `supplier_name`, `unit_cost` (obligatoires), `platform`, `supplier_country`,
`eu_warehouse` (oui/non), `supplier_rating` (0-5), `reviews_count`, `shipping_cost`, `shipping_days_min`,
`shipping_days_max`, `stock`, `ships_from`, `customization`, `api_integration`, `return_policy`, `url`.
Séparateur `,` ou `;`, décimales `.` ou `,`.

## Connecter les comptes

| Intégration | Variables | Coût |
|---|---|---|
| Shopify | `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_ADMIN_TOKEN` (Admin Shopify → Paramètres → Apps et canaux de vente → Développer des apps → créer une app, scopes `read_products, write_products, read_orders, read_inventory`) | Inclus dans l'abonnement |
| Stripe | `STRIPE_API_KEY` : **clé restreinte en lecture seule** (Dashboard → Développeurs → Clés API → Créer une clé restreinte) | Gratuit (commission par transaction) |
| Google Trends | aucune (pytrends, non officiel, peut être limité) | Gratuit |
| CJdropshipping | `CJ_API_EMAIL`, `CJ_API_KEY` | API gratuite — intégration à coder |
| AliExpress | `ALIEXPRESS_APP_KEY/SECRET/ACCESS_TOKEN` | Gratuit après validation — à coder |
| BigBuy | `BIGBUY_API_KEY` | **Payant** (abonnement) — à coder |
| Zendrop | `ZENDROP_API_KEY` | Pas d'API publique documentée |
| Meta Ad Library | `META_ADLIB_TOKEN` | Gratuit (vérification d'identité) — à coder |
| TikTok Creative Center | — | Pas d'API publique de tendances |
| Meta / TikTok / Google Ads | voir `.env.example` | API gratuites, **publicités payantes (niveau C)** — à coder |
| WooCommerce | `WOO_URL`, `WOO_CONSUMER_KEY/SECRET` | Hébergement payant — à coder |

Cliquez **Tester** dans l'onglet *Boutiques & connecteurs* pour vérifier une connexion réelle.

**Sécurité** : ne mettez jamais vos clés dans Git (`.env` est ignoré). En production, utilisez les
variables d'environnement / secrets de l'hébergeur et définissez `DASHBOARD_TOKEN` (sinon tout le monde
pourrait piloter votre système). Le jeton se saisit dans l'onglet *Paramètres*.

## Déploiement cloud (petit budget) — limites honnêtes

Les offres gratuites changent souvent : vérifiez les conditions actuelles avant de choisir.

- **Render (Web Service gratuit)** : déploiement depuis GitHub avec le `Dockerfile`. Limites : le service
  **s'endort après ~15 min sans trafic** (le planificateur interne ne tourne donc pas pendant le sommeil) et le
  disque est éphémère (la base SQLite est perdue au redéploiement). Contournements : base PostgreSQL externe
  (`DATABASE_URL`, ajouter `psycopg[binary]` à `requirements.txt`) et un cron externe gratuit (ex. cron-job.org)
  qui appelle `POST /api/commands/run-pipeline?token=VOTRE_JETON` chaque matin.
- **Railway** : pas d'offre gratuite permanente (crédit d'essai puis abonnement de quelques $/mois) ; tourne en continu, volumes persistants.
- **Fly.io** : facturation à l'usage (quelques $/mois pour une petite machine + volume) ; tourne en continu.
- **VM « Always Free »** (Oracle Cloud, Google Cloud e2-micro) : gratuites mais carte bancaire demandée pour
  la vérification ; `docker compose up -d` y fonctionne en continu.

Exemple Render : New → Web Service → dépôt GitHub → Runtime *Docker* → variables d'environnement
(`DASHBOARD_TOKEN`, `DATABASE_URL`, `SHOPIFY_*`, `STRIPE_API_KEY`) → Deploy.

## Limites actuelles du MVP

- Agents Creative Studio, Growth et Operations : non implémentés (affichés « non disponible »/« non connecté »).
- Les connecteurs fournisseurs et publicitaires sont des interfaces vides (aucune donnée simulée).
- Publication Shopify : crée uniquement des produits en **brouillon** (niveau B, invisible des clients).
  Le lancement public (retrait du mot de passe de la boutique) reste manuel et exige une approbation C.
- La conformité est une liste de contrôle indicative ; faites valider TVA/juridique par un professionnel.
- Aucune vente ni rentabilité n'est garantie.
