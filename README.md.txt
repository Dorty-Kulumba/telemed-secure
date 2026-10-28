# Telemed Secure - Plateforme de Télémédecine Simulée et Sécurisée

**Projet M1 - Protocole de Sécurité Réseau & Cryptographie Appliquée**  
**Groupe 22 (Gouvernance de Sécurité)**[cite: 7]

## 👥 Membres du Groupe
* KULUMBA DORTY DON DE DIEU[cite: 7]
* MUKENGA BAFUILA ANDRE[cite: 7]
* NGOLO MPIDI DONEL[cite: 7]
* LAKU ISHAKO ABEDNEGO[cite: 7]

---

## 🎯 Objectif du Projet
Développement et déploiement d'une application web de télémédecine sécurisée permettant la consultation, la gestion des dossiers médicaux chiffrés et le suivi d'audit des accès[cite: 2, 7]. L'application garantit le respect de la vie privée, le contrôle d'accès strict et l'intégrité des données à l'aide de mécanismes cryptographiques modernes et de données de test entièrement synthétiques[cite: 2, 7].

---

## 🔒 Mécanismes de Sécurité et Cryptographie
Conformément aux exigences minimales, la plateforme intègre :

1. **HTTPS / TLS** : Communication chiffrée de bout en bout entre le client et le serveur backend hébergé sur Render[cite: 2, 7].
2. **Authentification Forte (MFA / TOTP)** : Connexion sécurisée combinant mot de passe (haché via Argon2/Bcrypt) et validation par jeton TOTP à 6 chiffres[cite: 7].
3. **Contrôle d'Accès basé sur les Rôles (RBAC)** : Gestion personnalisée des permissions pour les rôles **Patient**, **Médecin / Praticien** et **Administrateur**[cite: 7].
4. **Chiffrement Authentifié (AES-256-GCM)** : Chiffrement symétrique des données sensibles des dossiers médicaux au repos dans la base de données PostgreSQL[cite: 7].
5. **Journal d'Audit et Traçabilité Immuable** : Enregistrement de chaque tentative d'accès, modification ou consultation avec horodatage et rôle de l'utilisateur[cite: 7].
6. **Sécurisation des Sessions & API** : Utilisation de jetons **JWT (JSON Web Tokens)** signés à courte durée de vie.

---

## 🏗️ Architecture du Système
* **Backend** : FastAPI (Python) - Gestion des API RESTful, authentification JWT, hachage, chiffrement et ORM[cite: 1].
* **Frontend** : HTML5, CSS3, JavaScript (Vanilla ES6) - Interface dynamique connectée à l'API[cite: 1].
* **Base de données** : PostgreSQL hébergée sur Render - Persistance sécurisée des données de test[cite: 1].
* **Déploiement Cloud** : Render Web Service[cite: 1, 2].

---

## 🔑 Identifiants de Démonstration (Soutenance)

| Rôle | E-mail | Mot de Passe | Code MFA (TOTP) |
| :--- | :--- | :--- | :--- |
| **Patient** | `patient@telemed.test` | `Patient123!` | Généré via app TOTP / Config de test |
| **Médecin** | `medecin@telemed.test` | `Medecin123!` | Généré via app TOTP / Config de test |
| **Admin** | `admin@telemed.test` | `Admin123!` | Généré via app TOTP / Config de test |

---

## 🚀 Installation et Lancement Local

### Prérequis
* Python 3.10+
* PostgreSQL local ou connexion distante
* Pipenv / Virtualenv

### Étapes
1. **Cloner le dépôt :**
   ```bash
   git clone https://github.com/Dorty-Kulumba/telemed-secure.git
cd telemed-secure