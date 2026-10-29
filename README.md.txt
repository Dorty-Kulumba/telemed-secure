# Telemed Secure

Application de démonstration pour explorer une connexion avec MFA, le consentement d'un patient, le chiffrement des dossiers médicaux et la journalisation des actions. Utilisez uniquement des données synthétiques : ce projet ne constitue pas un service médical prêt pour des données de santé réelles.

## Fonctionnalités présentes

- Création publique de comptes **Patient** avec validation des champs et détection des adresses e-mail déjà utilisées.
- Configuration manuelle d'un code TOTP avec une application d'authentification.
- Connexion en deux étapes : mot de passe, puis code TOTP associé à une demande temporaire.
- Sessions JWT de courte durée et vérification du compte auprès de l'API lors du chargement du tableau de bord.
- API de consentement réservée au patient ; création d'un dossier réservée à un praticien actif ayant reçu le consentement du patient.
- Journal d'audit consultable par un compte administrateur.
- Interface et API servies depuis le même serveur. Les routes API sont déclarées avant les fichiers du site.

La création publique d'un compte médecin ou administrateur est volontairement désactivée. Le projet ne contient pas d'écran permettant de consulter les dossiers médicaux ni de gérer les consentements ; ces parcours restent à construire.

## Lancement local

Prérequis : Python 3.10 ou plus récent.

1. Copiez `.env.example` vers `.env` à la racine du projet.
2. Remplacez `SECRET_KEY` par une valeur aléatoire de plus de 32 octets. SQLite est configuré par défaut : `DATABASE_URL=sqlite:///./telemed_secure.db`.
3. Créez l'environnement et installez les dépendances :
   - `uv venv .venv`
   - `uv pip install -r backend/requirements.txt`
4. Créez les tables (l'application **ne** crée pas le schéma au démarrage, il faut appliquer les migrations Alembic) :
   - `.venv/Scripts/python.exe -m alembic upgrade head`
5. Lancez le serveur depuis la racine du dépôt :
   - `.venv/Scripts/python.exe -m uvicorn backend.main:app --reload`
6. Ouvrez `http://127.0.0.1:8000` et créez un compte patient. La clé MFA et le lien de configuration sont affichés immédiatement après l'inscription ; enregistrez-les dans votre application d'authentification.

## Comptes de démonstration (sans SMTP)

Aucun e-mail n'est envoyé par cette application : la clé TOTP est affichée à l'inscription, puis à chaque connexion en mode démonstration.

Avec `ENABLE_TEST_ACCOUNTS=true` dans `.env`, l'interface affiche un panneau **Accès de démonstration** et l'API expose `GET /api/dev/test-accounts`, qui renvoie pour chaque compte le mot de passe et le code TOTP courant. Trois comptes sont créés automatiquement :

| Rôle | E-mail | Mot de passe |
| --- | --- | --- |
| Patient | `demo.patient@example.com` | `DemoPatient2026!` |
| Médecin | `demo.medecin@example.com` | `DemoMedecin2026!` |
| Administrateur | `demo.admin@example.com` | `DemoAdmin2026!` |

Ces points d'entrée ne doivent jamais être activés en production : mettre `ENABLE_TEST_ACCOUNTS=false` (valeur par défaut dans `.env.example`).


Pour utiliser PostgreSQL, définissez `DATABASE_URL` dans `.env`. Pour conserver les dossiers chiffrés entre les redémarrages et les déploiements, définissez également `AES_ENCRYPTION_KEY` avec une clé AES de 32 octets encodée en base64 et conservez-la dans le gestionnaire de secrets de l'hébergeur. Ne changez pas cette clé après avoir chiffré des dossiers.

Si le frontend est hébergé sur un domaine séparé, renseignez `CORS_ORIGINS` avec la liste exacte de ses origines, séparées par des virgules. La configuration du déploiement Render attend `DATABASE_URL`, `SECRET_KEY` et, en production, `AES_ENCRYPTION_KEY`.

## Limites à connaître

- Les comptes Patient sont les seuls créables depuis l'interface. Aucun flux d'administration initiale des médecins et administrateurs n'est fourni.
- Le tableau de bord présente encore une partie des fonctions comme information : l'interface patient de consentement, la consultation des dossiers et le flux praticien doivent être réalisés.
- La rotation des clés, la récupération de compte, les limites contre les tentatives répétées, les migrations de base de données, la sauvegarde/restauration et la supervision de production ne sont pas encore configurées.
- N'utilisez aucune donnée personnelle ou médicale réelle dans cette version de démonstration.
