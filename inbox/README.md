# Leeral Messages

Application web pour lire les messages reçus sur le WhatsApp de Leeral et y répondre, comme dans WhatsApp. Elle est réservée à l'équipe : connexion par e-mail et mot de passe, comptes créés sur le serveur.

L'application ne parle jamais directement à WhatsApp. Elle passe par les routes `/v1/admin/...` de l'API Leeral, qui garde seule le jeton Meta.

## Ce qu'elle fait

- Liste des conversations, triée par dernier message, avec les non lus, la recherche par nom ou numéro et des filtres (non lues, fenêtre ouverte, bot en pause).
- **Fenêtre de 24 h** : l'anneau autour de chaque contact se vide à mesure que le temps passe, et la barre en haut de la conversation affiche le temps restant. Une fois la fenêtre fermée, WhatsApp n'accepte plus que le modèle de relance (`WHATSAPP_REMINDER_TEMPLATE`), que l'application propose d'envoyer.
- **Réception** : texte, photo, vidéo, audio et message vocal, document, sticker, position, contact, réponses aux boutons, réactions (affichées sur le message visé) et messages cités.
- **Envoi** : texte, photo avec légende (convertie en JPEG et compressée si besoin), vidéo MP4, document, fichier audio, message vocal enregistré dans le navigateur (converti au format des notes vocales WhatsApp), carte de contact, réponse en citant un message. Une photo se colle ou se dépose directement dans la conversation.
- **Statuts** : envoyé, reçu, lu, et la raison donnée par WhatsApp quand un message n'est pas distribué.
- **Pause du bot** : dès qu'un membre de l'équipe répond, Leeral cesse de répondre automatiquement à ce contact pendant `INBOX_BOT_PAUSE_MINUTES` (60 par défaut). L'interrupteur en haut de la conversation met Leeral en pause sans limite de durée, ou le relance.
- Fiche du contact : langue, formule, documents expliqués, compte dans l'application, premier message, dernière activité.
- Notifications du navigateur à l'arrivée d'un message, et nombre de conversations non lues dans le titre de l'onglet.
- Lecture : ouvrir une conversation la marque comme lue et envoie l'accusé de lecture au contact.

## Mise en route

### 1. Sur le serveur

Les nouvelles tables arrivent avec la migration `0006`, appliquée au démarrage de l'API.

Créer un compte (le mot de passe est demandé deux fois et doit faire au moins 12 caractères) :

```bash
docker compose exec api leeral admin-create --email bachir@exemple.sn --name Bachir
```

Autres commandes : `leeral admin-list`, `leeral admin-password --email …` (ferme aussi toutes les sessions du compte), `leeral admin-disable --email …`, `leeral admin-enable --email …`.

Autoriser l'adresse de l'application dans le `.env` de l'API, en gardant les adresses déjà présentes, puis redémarrer l'API :

```
CORS_ORIGINS=["https://leeral-messages.vercel.app"]
```

```bash
docker compose up -d api
```

### 2. Sur Vercel

1. **Add New → Project**, puis importer le dépôt GitHub `new_leeral`.
2. **Root Directory** : `inbox`. Vercel détecte Vite tout seul.
3. **Environment Variables** : `VITE_API_URL` = l'adresse publique de l'API, sans `/` final (par exemple `https://ton-domaine.ngrok-free.app`).
4. **Deploy**. Chaque push sur `main` redéploie l'application.

`vercel.json` ajoute les en-têtes de sécurité (CSP, interdiction d'affichage dans une iframe, pas d'indexation) et renvoie toutes les adresses vers l'application.

## Développement

```powershell
cd inbox
npm install
copy .env.example .env.local
npm run dev
```

Dans `.env.local`, `VITE_API_URL` pointe vers l'API (par exemple `http://localhost:8000`), et `CORS_ORIGINS` de l'API doit contenir `http://localhost:5173`.

```powershell
npm run typecheck
npx prettier --check "src/**/*.{ts,tsx,css}"
npm run build
```

## Sécurité

- Les jetons d'accès durent 15 minutes et ne sont gardés qu'en mémoire. Le jeton de renouvellement (7 jours, renouvelé à chaque usage) est dans le navigateur. Se déconnecter le révoque sur le serveur.
- Un compte est bloqué 15 minutes après 5 mots de passe faux.
- Les jetons de l'application mobile ne donnent pas accès à ces routes, et inversement.
- Les photos et documents sont servis par des liens signés qui expirent.
- Les médias reçus sont archivés dans le stockage de l'utilisateur (`users/<id>/whatsapp/`), car WhatsApp les supprime au bout de 30 jours. Ils sont effacés avec le compte.
