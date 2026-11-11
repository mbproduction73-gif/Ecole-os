"""Agent Compliance : liste de contrôle Belgique / UE.

Ne remplace pas un avis professionnel (comptable, juriste). Les points « à vérifier »
doivent être validés par une personne compétente.
"""
from sqlalchemy.orm import Session

from ..core.logs import log_action
from ..models import Product

RISK_KEYWORDS = {
    "electrique": ["électrique", "electrique", "usb", "chargeur", "batterie", "lithium", "led", "220v", "sans fil"],
    "enfant_jouet": ["enfant", "bébé", "bebe", "jouet", "toy", "baby"],
    "cosmetique": ["crème", "creme", "sérum", "serum", "cosmétique", "cosmetique", "peau", "cheveux"],
    "alimentaire": ["complément", "complement", "alimentaire", "thé", "the minceur", "gélule"],
    "medical": ["médical", "medical", "soigne", "guérit", "guerit", "posture", "douleur", "orthopédique"],
    "laser_dangereux": ["laser", "arme", "taser", "couteau", "spray"],
}
BRAND_KEYWORDS = ["nike", "adidas", "disney", "apple", "airpods", "marvel", "pokemon", "chanel", "gucci",
                  "louis vuitton", "dyson", "stanley", "lego", "barbie"]


def check_product(product: Product, text: str = "") -> dict:
    blob = " ".join(filter(None, [product.name, product.niche, product.problem_solved, text])).lower()
    flags = [cat for cat, kws in RISK_KEYWORDS.items() if any(k in blob for k in kws)]
    ip = [b for b in BRAND_KEYWORDS if b in blob]
    items = [
        {"id": "tva", "label": "TVA : régime belge (franchise PME jusqu'à 25 000 €/an ou assujetti) ; "
         "ventes à distance UE > 10 000 €/an → TVA du pays client via guichet OSS", "status": "à vérifier"},
        {"id": "bce", "label": "Numéro d'entreprise (BCE) et mentions légales obligatoires sur le site "
         "(nom, adresse, e-mail, n° BCE/TVA)", "status": "à vérifier"},
        {"id": "retractation", "label": "Droit de rétractation de 14 jours + formulaire type ; "
         "remboursement sous 14 jours", "status": "inclus dans le brouillon"},
        {"id": "garantie", "label": "Garantie légale de conformité de 2 ans", "status": "inclus dans le brouillon"},
        {"id": "rgpd", "label": "RGPD : politique de confidentialité, bandeau cookies avec consentement, "
         "registre des traitements", "status": "à vérifier"},
        {"id": "gpsr", "label": "Sécurité des produits (règlement UE 2023/988 GPSR) : opérateur économique "
         "responsable dans l'UE, coordonnées du fabricant, avertissements en FR/NL/DE", "status": "à vérifier"},
        {"id": "prix", "label": "Prix TTC affichés ; pas de fausse promotion (prix de référence = prix le plus "
         "bas des 30 derniers jours)", "status": "à vérifier"},
        {"id": "avis", "label": "Pas de faux avis ; avis clients uniquement s'ils sont vérifiés", "status": "règle appliquée"},
        {"id": "langues", "label": "Informations produit dans la langue de la région de vente (FR/NL/DE)",
         "status": "à vérifier"},
    ]
    if "electrique" in flags:
        items.append({"id": "ce", "label": "Produit électrique : marquage CE, déclaration UE de conformité, "
                      "RoHS, DEEE (Recupel en Belgique), piles (Bebat)", "status": "obligatoire – à vérifier"})
    if "enfant_jouet" in flags:
        items.append({"id": "jouet", "label": "Jouet/enfant : directive sécurité des jouets, CE, tests EN 71",
                      "status": "obligatoire – risque élevé"})
    if "cosmetique" in flags:
        items.append({"id": "cosm", "label": "Cosmétique : règlement 1223/2009, personne responsable UE, "
                      "notification CPNP", "status": "obligatoire – risque élevé"})
    if "alimentaire" in flags:
        items.append({"id": "alim", "label": "Alimentaire/complément : notification AFSCA/SPF Santé",
                      "status": "obligatoire – risque élevé"})
    if "medical" in flags:
        items.append({"id": "med", "label": "Allégations santé/médicales interdites sans statut de dispositif "
                      "médical (règlement 2017/745)", "status": "risque élevé – reformuler"})
    if "laser_dangereux" in flags:
        items.append({"id": "danger", "label": "Produit potentiellement réglementé/interdit", "status": "à écarter"})
    if ip:
        items.append({"id": "pi", "label": f"Propriété intellectuelle : marque(s) détectée(s) {ip} – risque de "
                      "contrefaçon", "status": "à écarter sauf licence"})
    high = [i for i in items if "risque élevé" in i["status"] or "écarter" in i["status"]]
    return {"flags": flags, "ip_flags": ip, "items": items,
            "risk": "élevé" if high else ("moyen" if flags else "standard"),
            "disclaimer": "Liste indicative ; à faire valider par un comptable/juriste pour votre situation."}


def run(session: Session, product: Product, text: str = "") -> dict:
    res = check_product(product, text)
    log_action(session, "compliance", "analyze", "execute",
               f"Contrôle conformité « {product.name} » : risque {res['risk']}", level="A")
    return res
