# Leeral — application mobile

Application Expo (SDK 57, Expo Router) qui reprend les 20 écrans du design « Leeral — Design » : choix de la langue, compte par numéro WhatsApp, photo guidée sur plusieurs pages, explication vocale, questions à voix haute, « Écrire pour moi », « Apprendre le français », mon compte et Leeral+.

Chaque bouton haut-parleur joue la consigne dans la langue choisie (consignes `app.*` générées par l'API), et la bulle « Leeral te dit » affiche le texte.

## Structure

```
mobile/
├── app.json             nom, icônes, permissions caméra et micro
├── app.config.js        lit LEERAL_API_URL dans le .env de la racine du dépôt
├── assets/              icône et écran de démarrage Leeral
└── src/
    ├── app/             un fichier par écran (Expo Router)
    │   ├── langue.tsx, numero.tsx, code.tsx, prenom.tsx
    │   ├── accueil.tsx, documents.tsx, ecrire.tsx, apprendre.tsx
    │   ├── camera.tsx, lecture.tsx, explication/[id].tsx, conversation/[id].tsx
    │   ├── ecrit/[id].tsx, ecrit-pret/[id].tsx, profil.tsx, plus.tsx
    ├── components/      boutons, halo, bulle vocale, micro, barre de navigation
    └── lib/             client API, session, voix, enregistrement, thème
```

## Lancer sur ton téléphone avec Expo Go

### 1. Une seule fois

- **Node.js 22 LTS** sur le PC (`node -v` doit afficher v22.13 ou plus).
- **Expo Go à jour** sur le téléphone (Play Store ou App Store). Dans Expo Go, l'onglet profil ou réglages affiche les SDK pris en charge : il doit contenir **57**.
- Installer les dépendances :

```powershell
cd new_leeral\mobile
npm install
```

### 2. Dire à l'app où est l'API

Dans `new_leeral\.env` (le même fichier que l'API), ajoute :

```
LEERAL_API_URL=https://<ton-domaine>.ngrok-free.app
OTP_LENGTH=4
```

- Le téléphone passe par ton tunnel ngrok, celui de WhatsApp : il marche en Wi-Fi comme en 4G.
- `OTP_LENGTH=4` donne un code à 4 chiffres, comme dans le design. L'app s'adapte de toute façon à la longueur renvoyée par l'API.

Après cette modification, relance l'API et le worker, puis génère les nouvelles consignes vocales des écrans :

```powershell
cd new_leeral\api
leeral sync-prompts
```

Avec l'IA réelle, compte 15 à 20 minutes pour le wolof et le pulaar. L'app marche pendant ce temps : la bulle affiche le texte, et le son arrive dès que la consigne est prête.

### 3. Démarrer

Quatre terminaux : Redis, API, worker, ngrok (comme pour WhatsApp). Puis un cinquième :

```powershell
cd new_leeral\mobile
npx expo start
```

- **Android :** ouvre Expo Go et touche « Scan QR code ».
- **iPhone :** scanne le QR code avec l'appareil photo, puis ouvre le lien dans Expo Go. Sur un iPhone, Expo Go doit être connecté au même compte Expo que `npx expo start` (`npx expo whoami` pour le vérifier).

Le téléphone et le PC doivent être sur le **même Wi-Fi**.

### Si le QR code ne s'ouvre pas

Essaie dans cet ordre :

1. **Pare-feu Windows.** Au premier lancement, Windows demande d'autoriser Node.js : coche « Réseaux privés ». Si tu as fermé la fenêtre, dans PowerShell en administrateur :
   ```powershell
   New-NetFirewallRule -DisplayName "Expo 8081" -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow
   ```
2. **Réseau en « Privé ».** Paramètres Windows → Réseau → ton Wi-Fi → Profil réseau : Privé.
3. **Mauvaise adresse dans le QR** (VPN, VirtualBox, WSL). Regarde ton adresse Wi-Fi avec `ipconfig` (ligne IPv4 de la carte Wi-Fi), puis :
   ```powershell
   $env:REACT_NATIVE_PACKAGER_HOSTNAME="192.168.1.23"
   npx expo start
   ```
4. **Partage de connexion.** Active le point d'accès du téléphone et connecte le PC dessus : PC et téléphone sont alors forcément sur le même réseau.
5. **Tunnel Expo**, en dernier recours (plus lent) : `npx expo start --tunnel`.

Dans Expo Go, tu peux aussi taper l'adresse à la main : `exp://<IP-du-PC>:8081`.

### Si Expo Go dit « incompatible »

Expo Go a été mis à jour vers un SDK plus récent. Mets le projet au même niveau :

```powershell
npx expo install expo@latest
npx expo install --fix
```

## Vérifier

```powershell
npm run typecheck
npx prettier --check "src/**/*.{ts,tsx}"
npx expo-doctor
```

## Écrans et petits téléphones

Chaque écran doit rester utilisable sur un téléphone de 320 px de large et avec une grande taille de texte dans les réglages Android :

- `Screen` (dans `components/ui.tsx`) : le contenu défile toujours, et le bouton principal peut rester fixé en bas (`footer`).
- `useLayout()` : `fit(taille)` réduit les grandes tailles (titres, micro, halo) sur les petits écrans ; `narrow` et `short` signalent un écran étroit ou bas.
- `T` limite l'agrandissement du texte par le système à `MAX_FONT_SCALE` (1,2).
- Les petits haut-parleurs posés sur un bouton ne doivent jamais recouvrir son texte : réserver leur place avec un `paddingRight` sur le bouton.

## Publier une nouvelle version

| Quoi | Comment |
|---|---|
| Code de l'app (écrans, logique) | GitHub Actions → **Publier l'app** : envoie une mise à jour EAS sur le canal `preview` et republie [leeral.expo.app](https://leeral.expo.app). L'APK installé la télécharge à l'ouverture et l'applique au lancement suivant |
| Nouvelle dépendance native, icône, permissions, version d'Expo | Nouvel APK : `npx eas-cli build -p android --profile preview`, puis partager le nouveau lien |

Pour savoir si un nouvel APK est nécessaire, compare l'empreinte native du projet avec celle du build installé :

```powershell
npx eas-cli fingerprint:compare --build-id <id-du-build> --environment preview
```

L'APK ne s'installe que sur Android. Sur iPhone, utiliser la version web ou WhatsApp.

## Ce que l'app utilise côté API

| Écran | Routes |
|---|---|
| Langue, compte | `POST /auth/guest`, `/auth/otp/request`, `/auth/otp/verify`, `/auth/refresh`, `/auth/logout`, `GET/PATCH /me` |
| Prénom, recherche vocale | `POST /speech/transcriptions` |
| Photo, lecture, explication | `POST /documents`, `GET /documents/{id}`, `POST /documents/{id}/retry`, `POST /documents/{id}/explanations` |
| Questions | `POST /documents/{id}/conversation`, `GET/POST /conversations/{id}/messages` |
| Écrire pour moi | `GET/POST /writings`, `POST /writings/{id}/answers`, `/confirm`, `/skip` |
| Apprendre | `GET /learning/overview`, `GET /learning/words`, `POST /learning/sessions`, `/answers`, `/finish` |
| Leeral+ | `GET /billing/plans`, `POST /billing/checkout`, `POST /billing/payments/{token}/simulate` |
| Consignes vocales | `GET /prompts?language=wo` |

Un invité qui garde ses documents (« Oui, garder ») vérifie son numéro avec son jeton d'invité : ses documents passent sur son compte.
