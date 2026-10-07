APP_GUIDE_PROMPTS: dict[str, str] = {
    "app.language.screen": (
        "Bienvenue. Touche une des trois langues pour l'écouter. Choisis celle que tu "
        "comprends le mieux, puis touche le bouton jaune en bas."
    ),
    "app.language.picked": (
        "Tu as choisi cette langue. Je te parlerai dans cette langue. Touche « Continuer »."
    ),
    "app.language.soon": "Le sérère arrive bientôt. Pour l'instant, choisis le wolof ou le pulaar.",
    "app.home.screen": (
        "Bienvenue sur Leeral. Pour comprendre un document, touche le grand bouton jaune et "
        "prends-le en photo. Je te l'explique ensuite à voix haute."
    ),
    "app.home.language": (
        "Ici, tu changes la langue dans laquelle je te parle : wolof, pulaar ou sérère."
    ),
    "app.home.photo": (
        "Touche le bouton jaune pour prendre ton document en photo. Ensuite, je te dis ce qu'il "
        "contient et ce que tu dois faire."
    ),
    "app.home.file": (
        "Touche ici si ton document est un fichier PDF ou Word déjà dans ton téléphone."
    ),
    "app.home.gallery": "Touche ici pour choisir une photo que tu as déjà prise.",
    "app.home.write": (
        "Tu me parles, et j'écris pour toi un CV, une lettre ou une demande en français."
    ),
    "app.home.learn": "Ici, tu apprends en écoutant les mots français de tes documents.",
    "app.home.documents": (
        "Voici tes derniers documents. Touche le bouton rond pour réécouter l'explication."
    ),
    "app.home.guest": (
        "Sans compte, tout marche, mais tes documents disparaissent. Avec ton numéro de "
        "téléphone, je les garde pour toi."
    ),
    "app.phone.screen": (
        "Tape ton numéro de téléphone avec les grosses touches. Je t'envoie ensuite un code sur "
        "WhatsApp. Pas besoin de mot de passe."
    ),
    "app.phone.field": (
        "Ton numéro s'affiche ici. Pour effacer un chiffre, touche la flèche en bas à droite."
    ),
    "app.phone.go": (
        "Quand ton numéro est complet, touche ce bouton. Tu recevras un code sur WhatsApp."
    ),
    "app.code.screen": (
        "Ouvre WhatsApp : tu as reçu un message de Leeral avec un code. Tape ces chiffres ici."
    ),
    "app.code.resend": (
        "Si tu n'as rien reçu, attends la fin du compte à rebours, puis touche ici pour recevoir "
        "un nouveau code."
    ),
    "app.name.screen": (
        "C'est la dernière étape. Dis ton prénom pour que je puisse t'appeler par ton nom."
    ),
    "app.name.micro": (
        "Touche le grand bouton jaune, dis ton prénom, puis touche-le encore. Je l'écris en "
        "dessous."
    ),
    "app.name.go": (
        "Si le prénom écrit est le bon, touche ici. Ton compte est prêt et tes documents seront "
        "gardés."
    ),
    "app.camera.screen": (
        "Mets tout le document dans le cadre jaune, puis touche le grand bouton rond. S'il y a "
        "plusieurs pages, prends-les une par une. Quand tu as fini, touche « Terminé »."
    ),
    "app.camera.tip_first": "Pose le document à plat, dans un endroit éclairé.",
    "app.camera.tip_next": "Page prise. Une autre page ? Prends-la aussi.",
    "app.reading.screen": (
        "Je suis en train de lire ton document. Attends un peu : je vais te l'expliquer à voix "
        "haute. Pour annuler, touche la croix en haut à gauche."
    ),
    "app.reading.blurry": (
        "Je n'arrive pas à bien lire ta photo. Mets-toi près d'une fenêtre ou d'une lampe, pose "
        "le document bien à plat, et touche le bouton jaune pour reprendre la photo."
    ),
    "app.explanation.screen": (
        "Voici l'explication de ton document. Le grand bouton jaune lance ou arrête l'écoute. "
        "En bas, tu peux me poser une question."
    ),
    "app.explanation.repeat": "Touche ici pour réécouter l'explication depuis le début.",
    "app.explanation.slower": "Touche ici si je parle trop vite. Je répète plus lentement.",
    "app.explanation.simpler": (
        "Tu n'as pas tout compris ? Touche ici, je t'explique encore plus simplement, avec "
        "d'autres mots."
    ),
    "app.explanation.todo": (
        "Ce sont les choses importantes à faire. Touche le haut-parleur d'une ligne pour "
        "l'écouter seule."
    ),
    "app.explanation.question": (
        "Touche ce bouton et pose ta question à voix haute, dans ta langue. Je te réponds avec "
        "ce qui est écrit sur le document."
    ),
    "app.conversation.screen": (
        "Ici, tu continues la discussion sur ton document. Pose toutes les questions que tu "
        "veux, je réponds avec ce qui est écrit dessus."
    ),
    "app.conversation.suggestions": (
        "Ce sont des questions que les gens posent souvent. Touche-en une pour l'envoyer sans "
        "parler."
    ),
    "app.conversation.micro": (
        "Touche le grand bouton jaune et parle. Quand tu as fini, touche-le encore pour envoyer "
        "ta question."
    ),
    "app.keep.screen": (
        "Tu n'as pas de compte. Si tu veux, je garde ce document pour que tu puisses le "
        "réécouter plus tard."
    ),
    "app.keep.yes": (
        "Touche ici pour garder le document. Je te demande juste ton numéro de téléphone."
    ),
    "app.keep.no": (
        "Touche ici si tu ne veux pas le garder. Tu peux continuer à l'écouter maintenant."
    ),
    "app.documents.screen": (
        "Voici tous les documents que je garde pour toi. Touche un document pour réécouter son "
        "explication. Les couleurs t'aident à trier : rouge pour la santé, jaune pour l'argent, "
        "vert pour l'école. Pour chercher, touche le micro et dis ce que tu cherches."
    ),
    "app.documents.search": (
        "Touche le micro et dis ce que tu cherches, par exemple : la facture d'électricité."
    ),
    "app.documents.all": "Tu vois tous tes documents.",
    "app.documents.health": (
        "Tu vois seulement les documents de santé : ordonnances, résultats, notices."
    ),
    "app.documents.money": (
        "Tu vois seulement les documents d'argent : factures, contrats, banque."
    ),
    "app.documents.school": ("Tu vois seulement les documents d'école : bulletins, convocations."),
    "app.documents.admin": (
        "Tu vois seulement les papiers administratifs et les documents écrits par Leeral."
    ),
    "app.write.screen": (
        "Ici, je t'aide à écrire un document en français. Choisis le type de document. Ensuite, "
        "je te pose des questions et tu réponds à voix haute."
    ),
    "app.write.resume": (
        "Tu as commencé ce document. Touche ici pour continuer là où tu t'es arrêté."
    ),
    "app.write.cv_cover_letter": (
        "Je t'aide à faire ton CV et ta lettre de motivation pour postuler à un emploi."
    ),
    "app.write.request_letter": (
        "Je t'aide à écrire une demande : un papier à la mairie, une absence à l'école, une "
        "autorisation."
    ),
    "app.write.bank_letter": (
        "Je t'aide à écrire à ta banque : demander un délai, contester un prélèvement."
    ),
    "app.write.other": (
        "Pour tout autre courrier : dis-moi ce que tu veux dire et à qui, je l'écris en français."
    ),
    "app.writing.screen": (
        "Je te pose des questions, une par une, pour préparer ton document en français. Réponds "
        "simplement, à voix haute, dans ta langue."
    ),
    "app.writing.understood": (
        "Voici ce que j'ai compris de ta réponse. Si c'est juste, touche le bouton vert. Sinon, "
        "touche « Corriger » et redis-le."
    ),
    "app.writing.noted": (
        "Ce sont les informations que tu m'as déjà données. Je n'écris rien d'autre que ce que "
        "tu m'as dit."
    ),
    "app.writing.micro": (
        "Touche le grand bouton jaune, réponds à la question, puis touche-le encore quand tu as "
        "fini."
    ),
    "app.writing.not_understood": "Je n'ai pas bien compris. Redis ta réponse, s'il te plaît.",
    "app.writing_ready.screen": (
        "Ton document est prêt, en français. Avant de l'envoyer, écoute ce que j'ai écrit pour "
        "vérifier que tout est juste."
    ),
    "app.writing_ready.listen": (
        "Touche ici : je te lis le document dans ta langue, pour que tu vérifies."
    ),
    "app.writing_ready.send": ("Touche ici pour envoyer le document sur WhatsApp ou par e-mail."),
    "app.writing_ready.download": (
        "Touche ici pour enregistrer le document en PDF dans ton téléphone, pour l'imprimer."
    ),
    "app.writing_ready.edit": ("Touche ici pour refaire le document. Je te repose les questions."),
    "app.learn.screen": (
        "Ici, tu apprends les mots français qu'on trouve sur les documents. Écoute le mot, puis "
        "choisis ce qu'il veut dire. Les mots que tu rates reviennent plus tard."
    ),
    "app.learn.tabs": (
        "Mots essentiels : les mots qu'on voit partout. Mes documents : les mots trouvés dans "
        "tes propres documents."
    ),
    "app.learn.choices": (
        "Touche la réponse que tu crois juste. Chaque réponse se lit à voix haute dans ta langue."
    ),
    "app.learn.right": "Bravo ! C'est la bonne réponse.",
    "app.learn.wrong": (
        "Ce n'est pas ça. Regarde la bonne réponse en vert. Ce mot reviendra plus tard."
    ),
    "app.learn.done": "Bravo, tu as fini cette séance. Reviens demain pour réviser.",
    "app.profile.screen": (
        "C'est ton compte. Tu peux changer ta langue, la vitesse de ma voix, voir tes documents "
        "ou demander de l'aide."
    ),
    "app.profile.plan": (
        "Comprendre tes documents est toujours gratuit. Leeral plus te donne plus de documents "
        "écrits pour toi et plus d'exercices de français."
    ),
    "app.profile.erase": (
        "Touche ici pour effacer tous tes documents de Leeral. Je te demanderai de confirmer avant."
    ),
    "app.profile.logout": (
        "Touche ici pour te déconnecter. Tes documents restent gardés, tu les retrouveras avec "
        "ton numéro."
    ),
    "app.profile.language": "Touche ici pour changer la langue dans laquelle je te parle.",
    "app.profile.speed": "Touche ici si je parle trop vite ou trop lentement.",
    "app.profile.documents": "Touche ici pour voir tous les documents que je garde pour toi.",
    "app.profile.help": "Touche ici pour écrire à l'équipe Leeral sur WhatsApp.",
    "app.plus.screen": (
        "Leeral plus coûte 500 francs par mois. Comprendre tes documents reste gratuit pour "
        "toujours. Leeral plus te donne plus de documents écrits pour toi et plus d'exercices "
        "de français."
    ),
    "app.plus.table": (
        "À gauche, ce que tu as gratuitement. À droite, en jaune, ce que tu as avec Leeral plus."
    ),
    "app.plus.pay": "Touche ici pour payer 500 francs avec Wave.",
    "app.plus.relative": (
        "Touche ici pour envoyer un message à un enfant ou à un proche, pour qu'il paie pour toi."
    ),
    "app.plus.done": "Merci ! Leeral plus est activé pour 30 jours.",
}
