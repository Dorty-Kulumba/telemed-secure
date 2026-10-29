<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telemed Secure - Connexion</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f7f6;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .login-card {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
        }
        .logo-container {
            text-align: center;
            margin-bottom: 20px;
        }
        .logo-badge {
            background-color: #0b6623;
            color: white;
            font-size: 24px;
            font-weight: bold;
            display: inline-block;
            padding: 10px 15px;
            border-radius: 8px;
        }
        h2 {
            text-align: center;
            color: #333;
            margin-bottom: 5px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 25px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ccc;
            border-radius: 6px;
            font-size: 14px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 12px;
            background-color: #0b6623;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }
        button:hover {
            background-color: #084e1b;
        }
        .footer-links {
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
            font-size: 13px;
        }
        .footer-links a {
            color: #0b6623;
            text-decoration: none;
        }
        .footer-links a:hover {
            text-decoration: underline;
        }
        .hidden {
            display: none;
        }
    </style>
</head>
<body>

    <div class="login-card">
        <div class="logo-container">
            <div class="logo-badge">+</div>
        </div>
        <h2>Telemed Secure</h2>
        <div class="subtitle">Bienvenue sur la plateforme</div>

        <!-- Formulaire de Connexion -->
        <div id="login-section">
            <form id="form-login">
                <div class="form-group">
                    <label for="email">Adresse e-mail ou numéro de téléphone</label>
                    <input type="text" id="email" required placeholder="exemple@gmail.com">
                </div>
                <div class="form-group">
                    <label for="password">Mot de passe</label>
                    <input type="password" id="password" required placeholder="••••••••">
                </div>
                <button type="submit">Se connecter</button>
            </form>

            <div class="footer-links">
                <a href="#" onclick="alert('Fonctionnalité de récupération de mot de passe sécurisée.')">Mot de passe oublié ?</a>
                <a href="#" onclick="toggleView('register-section')">Créer un compte</a>
            </div>
        </div>

        <!-- Formulaire d'Inscription (Accessible via le lien) -->
        <div id="register-section" class="hidden">
            <form id="form-register">
                <div class="form-group">
                    <label>Nom</label>
                    <input type="text" id="reg-nom" required>
                </div>
                <div class="form-group">
                    <label>Prénom</label>
                    <input type="text" id="reg-prenom" required>
                </div>
                <div class="form-group">
                    <label>Adresse e-mail</label>
                    <input type="email" id="reg-email" required>
                </div>
                <div class="form-group">
                    <label>Téléphone</label>
                    <input type="text" id="reg-tel" required>
                </div>
                <div class="form-group">
                    <label>Mot de passe</label>
                    <input type="password" id="reg-password" required>
                </div>
                <div class="form-group">
                    <label>Rôle</label>
                    <input type="text" id="reg-role" value="Patient" readonly>
                </div>
                <button type="submit">S'inscrire</button>
            </form>
            <div class="footer-links" style="justify-content: center;">
                <a href="#" onclick="toggleView('login-section')">← Retour à la connexion</a>
            </div>
        </div>

        <!-- Section MFA / Vérification du code -->
        <div id="mfa-section" class="hidden">
            <div class="subtitle" style="color: #d9534f; font-weight: bold;">Vérification de sécurité (MFA)</div>
            <form id="form-mfa">
                <div class="form-group">
                    <label for="mfa-code">Code de vérification (TOTP)</label>
                    <input type="text" id="mfa-code" maxlength="6" required placeholder="000000" style="text-align: center; font-size: 20px; letter-spacing: 5px;">
                </div>
                <button type="submit">Vérifier le code</button>
            </form>
            <div class="footer-links" style="justify-content: center; margin-top: 15px;">
                <a href="#" onclick="toggleView('login-section')">← Retour à la connexion</a>
            </div>
        </div>
    </div>

    <script>
        let currentUserEmail = "";

        function toggleView(sectionId) {
            document.getElementById('login-section').classList.add('hidden');
            document.getElementById('register-section').classList.add('hidden');
            document.getElementById('mfa-section').classList.add('hidden');
            document.getElementById(sectionId).classList.remove('hidden');
        }

        // Gestion de la connexion (Étape 1)
        document.getElementById('form-login').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const mot_de_passe = document.getElementById('password').value;

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, mot_de_passe })
                });
                const data = await response.json();
                if (response.ok) {
                    currentUserEmail = email;
                    alert("Identifiants valides ! Veuillez saisir votre code MFA.");
                    toggleView('mfa-section');
                } else {
                    alert("Erreur : " + (data.detail || "Identifiants incorrects"));
                }
            } catch (err) {
                alert("Erreur de connexion au serveur.");
            }
        });

        // Gestion de la validation MFA (Étape 2)
        document.getElementById('form-mfa').addEventListener('submit', async (e) => {
            e.preventDefault();
            const code_totp = document.getElementById('mfa-code').value;

            try {
                const response = await fetch('/api/mfa/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: currentUserEmail, code_totp })
                });
                const data = await response.json();
                if (response.ok) {
                    localStorage.setItem('token', data.access_token);
                    alert("Connexion réussie ! Bienvenue " + data.nom);
                    // Redirection ou affichage du tableau de bord selon le rôle
                } else {
                    alert("Code MFA invalide : " + (data.detail || "Vérifiez votre application d'authentification"));
                }
            } catch (err) {
                alert("Erreur lors de la vérification MFA.");
            }
        });

        // Gestion de l'inscription
        document.getElementById('form-register').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                nom: document.getElementById('reg-nom').value,
                prenom: document.getElementById('reg-prenom').value,
                email: document.getElementById('reg-email').value,
                telephone: document.getElementById('reg-tel').value,
                mot_de_passe: document.getElementById('reg-password').value,
                role: document.getElementById('reg-role').value
            };

            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (response.ok) {
                    alert("Compte créé avec succès ! Vous pouvez vous connecter.");
                    toggleView('login-section');
                } else {
                    alert("Erreur : " + (data.detail || "Échec de l'inscription"));
                }
            } catch (err) {
                alert("Erreur réseau lors de l'inscription.");
            }
        });
    </script>
</body>
</html>