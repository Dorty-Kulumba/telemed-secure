// URL de votre API déployée sur Render
const API_URL = "https://telemed-kulumba.onrender.com";

// --- GESTION DE LA CONNEXION (INDEX.HTML) ---
const loginForm = document.getElementById('login-form');
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('login-error');
        errorDiv.textContent = "";

        try {
            const response = await fetch(`${API_URL}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, mot_de_passe: password })
            });

            const data = await response.json();
            if (response.ok) {
                sessionStorage.setItem('pending_email', email);
                document.getElementById('login-section').style.display = 'none';
                document.getElementById('mfa-section').style.display = 'block';
            } else {
                errorDiv.textContent = data.detail || "Identifiants invalides.";
            }
        } catch (err) {
            errorDiv.textContent = "Erreur de communication avec le serveur API.";
        }
    });
}

// --- GESTION DU CODE MFA / TOTP (INDEX.HTML) ---
const mfaForm = document.getElementById('mfa-form');
if (mfaForm) {
    mfaForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = sessionStorage.getItem('pending_email');
        const codeTotp = document.getElementById('totp-code').value;
        const errorDiv = document.getElementById('mfa-error');
        errorDiv.textContent = "";

        try {
            const response = await fetch(`${API_URL}/api/mfa/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, code_totp: codeTotp })
            });

            const data = await response.json();
            if (response.ok) {
                // Sauvegarde de la session
                sessionStorage.setItem('jwt_token', data.access_token);
                sessionStorage.setItem('user_role', data.role);
                sessionStorage.setItem('user_name', data.nom);
                
                // Redirection vers le tableau de bord
                window.location.href = "dashboard.html";
            } else {
                errorDiv.textContent = data.detail || "Code MFA invalide.";
            }
        } catch (err) {
            errorDiv.textContent = "Erreur lors de la validation du code TOTP.";
        }
    });
}

// --- INITIALISATION DU DASHBOARD (DASHBOARD.HTML) ---
function initDashboard() {
    const token = sessionStorage.getItem('jwt_token');
    const role = sessionStorage.getItem('user_role');
    const name = sessionStorage.getItem('user_name');

    if (!token) {
        window.location.href = "index.html";
        return;
    }

    const userDisplay = document.getElementById('user-display');
    if (userDisplay) {
        userDisplay.innerHTML = `<strong>${name}</strong> <span class="badge">${role}</span>`;
    }

    const roleContent = document.getElementById('role-content');
    if (!roleContent) return;

    if (role === 'Patient') {
        roleContent.innerHTML = `
            <h3>Tableau de bord - Patient</h3>
            <p>Gestion de la confidentialité et consultation de vos données de santé.</p>
            <div class="card-grid">
                <div class="card">
                    <h4>🔒 Consentements</h4>
                    <p>Accorder ou révoquer l'accès aux praticiens.</p>
                </div>
                <div class="card">
                    <h4>📁 Dossier Médical</h4>
                    <p>Vos données sont chiffrées en AES-GCM au repos.</p>
                </div>
            </div>
        `;
    } else if (role === 'Médecin' || role === 'Spécialiste') {
        roleContent.innerHTML = `
            <h3>Tableau de bord - Praticien</h3>
            <p>Consultation et prise en charge sécurisée des patients.</p>
            <div class="card-grid">
                <div class="card">
                    <h4>📄 Consultation</h4>
                    <p>Accès sous réserve du consentement explicite du patient.</p>
                </div>
                <div class="card">
                    <h4>✍️ Nouveau Dossier</h4>
                    <p>Saisie et chiffrement automatique du dossier médical.</p>
                </div>
            </div>
        `;
    } else if (role === 'Administrateur') {
        roleContent.innerHTML = `
            <h3>Gouvernance & Audit Technique</h3>
            <p>Supervision et traçabilité infalsifiable du système.</p>
            <div class="card">
                <h4>📜 Journal d'Audit Centralisé</h4>
                <p>Consultez l'ensemble des requêtes et actions sécurisées.</p>
                <button onclick="fetchAuditLogs()" class="btn" style="width: auto;">Charger le journal d'audit</button>
                <div id="audit-logs" style="margin-top: 15px; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto;"></div>
            </div>
        `;
    }
}

async function fetchAuditLogs() {
    const token = sessionStorage.getItem('jwt_token');
    const logsDiv = document.getElementById('audit-logs');
    logsDiv.textContent = "Chargement des données d'audit...";

    try {
        const response = await fetch(`${API_URL}/api/audit`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        if (response.ok) {
            logsDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        } else {
            logsDiv.textContent = "Accès refusé ou erreur.";
        }
    } catch (e) {
        logsDiv.textContent = "Erreur de chargement de l'audit.";
    }
}

function logout() {
    sessionStorage.clear();
    window.location.href = "index.html";
}