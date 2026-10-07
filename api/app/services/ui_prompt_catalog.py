from app.core.errors import ERROR_CATALOG
from app.services.app_guide_prompts import APP_GUIDE_PROMPTS

SCREEN_PROMPTS: dict[str, str] = {
    "screen.language": "Choisis ta langue.",
    "screen.welcome": (
        "Bienvenue sur Leeral. Prends en photo un document en français, "
        "je te l'explique dans ta langue."
    ),
    "screen.phone": "Écris ton numéro WhatsApp. Tu vas recevoir un code.",
    "screen.code": "Écris le code que tu as reçu sur WhatsApp.",
    "screen.first_name": "Comment tu t'appelles ?",
    "screen.home": (
        "Que veux-tu faire ? Comprendre un document, écrire un document, ou apprendre le français."
    ),
    "screen.camera": "Mets toute la page dans le cadre, puis appuie sur le bouton.",
    "screen.reading": "Leeral lit ton document. Attends un petit moment.",
    "screen.explanation": ("Écoute l'explication. Pour poser une question, appuie sur le micro."),
    "screen.conversation": "Appuie sur le micro et pose ta question.",
    "screen.keep_document": (
        "Sans compte, ce document sera effacé demain. Crée ton compte pour le garder."
    ),
    "screen.my_documents": "Voici tes documents.",
    "screen.write_choose": "Quel document veux-tu écrire ?",
    "screen.write_ready": "Ton document est prêt. Tu peux le télécharger ou l'envoyer.",
    "screen.learn": "Écoute le mot dans ta langue, puis choisis le bon mot en français.",
    "screen.profile": "Ici, tu peux changer ta langue et ton prénom.",
    "screen.plus": (
        "Leeral plus coûte 500 francs par mois. Tu peux écrire 5 documents par mois "
        "et réviser sans limite."
    ),
    "whatsapp.welcome": (
        "Bonjour, je suis Leeral. Envoie-moi la photo d'un document en français, "
        "je te l'explique dans ta langue."
    ),
    "whatsapp.reading": "J'ai bien reçu ton document. Je le lis, attends un petit moment.",
    "whatsapp.ask_question": "Tu peux me poser une question sur ce document en vocal.",
    "whatsapp.unsupported": "Envoie-moi une photo, un PDF ou un message vocal.",
    "whatsapp.renew": "Pour renouveler Leeral plus, ouvre l'application Leeral.",
}


def prompt_catalog() -> dict[str, str]:
    errors = {
        f"error.{code.value.lower()}": spec.message
        for code, spec in ERROR_CATALOG.items()
        if spec.status_code < 500 or spec.retryable
    }
    return SCREEN_PROMPTS | APP_GUIDE_PROMPTS | errors
