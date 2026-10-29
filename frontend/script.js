const API_BASE_URL = "";

async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }
    if (options.token) {
        headers.set("Authorization", `Bearer ${options.token}`);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
    });
    const data = await response.json().catch(() => ({}));
    return { response, data };
}

function errorText(detail, fallback) {
    if (Array.isArray(detail)) {
        return detail.map((item) => item.msg || "Donnée invalide.").join(" ");
    }
    return typeof detail === "string" && detail ? detail : fallback;
}

function setMessage(elementId, message, kind = "error") {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.textContent = message;
    element.classList.toggle("success", kind === "success");
}

function showSection(sectionId) {
    ["login-section", "register-section", "enrollment-section", "mfa-section"].forEach((id) => {
        document.getElementById(id)?.classList.toggle("hidden", id !== sectionId);
    });
}

function setBusy(form, busy) {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    button.disabled = busy;
    button.dataset.originalText ||= button.textContent;
    button.textContent = busy ? "Veuillez patienter…" : button.dataset.originalText;
}

function initializeAuthentication() {
    document.querySelectorAll("[data-view]").forEach((button) => {
        button.addEventListener("click", () => {
            if (button.dataset.view === "login-section" && document.getElementById("mfa-section") && !document.getElementById("mfa-section").classList.contains("hidden")) {
                sessionStorage.removeItem("pending_mfa_token");
            }
            showSection(button.dataset.view);
        });
    });

    const loginForm = document.getElementById("form-login");
    loginForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        setMessage("login-message", "");
        if (!loginForm.reportValidity()) return;

        const email = document.getElementById("email").value.trim().toLowerCase();
        const mot_de_passe = document.getElementById("password").value;
        setBusy(loginForm, true);
        try {
            const { response, data } = await apiRequest("/api/login", {
                method: "POST",
                body: JSON.stringify({ email, mot_de_passe }),
            });
            if (!response.ok) {
                setMessage("login-message", errorText(data.detail, "Connexion impossible."));
                return;
            }
            sessionStorage.setItem("pending_mfa_token", data.challenge_token);
            sessionStorage.removeItem("jwt_token");
            document.getElementById("mfa-code").value = "";
            setMessage("mfa-message", "");
            showSection("mfa-section");
            document.getElementById("mfa-code").focus();
        } catch {
            setMessage("login-message", "Impossible de joindre le serveur. Réessayez dans un instant.");
        } finally {
            setBusy(loginForm, false);
        }
    });

    const registerForm = document.getElementById("form-register");
    registerForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        setMessage("register-message", "");
        if (!registerForm.reportValidity()) return;

        const telephone = document.getElementById("reg-tel").value.trim();
        const payload = {
            nom: document.getElementById("reg-nom").value.trim(),
            prenom: document.getElementById("reg-prenom").value.trim(),
            email: document.getElementById("reg-email").value.trim().toLowerCase(),
            telephone: telephone || null,
            mot_de_passe: document.getElementById("reg-password").value,
        };

        setBusy(registerForm, true);
        try {
            const { response, data } = await apiRequest("/api/register", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                setMessage("register-message", errorText(data.detail, "La création du compte a échoué."));
                return;
            }

            document.getElementById("mfa-secret").textContent = data.mfa.secret;
            const mfaLink = document.getElementById("mfa-uri-link");
            mfaLink.href = data.mfa.provisioning_uri;
            mfaLink.setAttribute("aria-label", "Ajouter Telemed Secure à votre application d'authentification");
            const recoveryCodes = document.getElementById("registration-recovery-codes");
            if (recoveryCodes) {
                recoveryCodes.textContent = (data.codes_de_secours || []).join("\n");
            }
            document.getElementById("continue-login").dataset.email = payload.email;
            setMessage("enrollment-message", data.message, "success");
            showSection("enrollment-section");
        } catch {
            setMessage("register-message", "Impossible de joindre le serveur. Vérifiez votre connexion puis réessayez.");
        } finally {
            setBusy(registerForm, false);
        }
    });

    document.getElementById("continue-login")?.addEventListener("click", (event) => {
        const email = event.currentTarget.dataset.email || "";
        showSection("login-section");
        document.getElementById("email").value = email;
        document.getElementById("password").focus();
    });

    const mfaForm = document.getElementById("form-mfa");
    mfaForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        setMessage("mfa-message", "");
        if (!mfaForm.reportValidity()) return;

        const challenge_token = sessionStorage.getItem("pending_mfa_token");
        if (!challenge_token) {
            setMessage("mfa-message", "Votre demande a expiré. Recommencez la connexion.");
            showSection("login-section");
            return;
        }

        const code_totp = document.getElementById("mfa-code").value.trim();
        setBusy(mfaForm, true);
        try {
            const { response, data } = await apiRequest("/api/mfa/verify", {
                method: "POST",
                body: JSON.stringify({ challenge_token, code_totp }),
            });
            if (!response.ok) {
                setMessage("mfa-message", errorText(data.detail, "Code invalide. Vérifiez-le et réessayez."));
                return;
            }

            sessionStorage.removeItem("pending_mfa_token");
            sessionStorage.setItem("jwt_token", data.access_token);
            window.location.assign("dashboard.html");
        } catch {
            setMessage("mfa-message", "Impossible de vérifier le code. Réessayez dans un instant.");
        } finally {
            setBusy(mfaForm, false);
        }
    });
}

function addTextCard(container, title, description) {
    const card = document.createElement("article");
    card.className = "card";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const paragraph = document.createElement("p");
    paragraph.textContent = description;
    card.append(heading, paragraph);
    container.append(card);
}

async function initDashboard() {
    const token = sessionStorage.getItem("jwt_token");
    if (!token) {
        window.location.replace("index.html");
        return;
    }

    try {
        const { response, data } = await apiRequest("/api/me", { token });
        if (!response.ok) {
            sessionStorage.removeItem("jwt_token");
            window.location.replace("index.html");
            return;
        }

        const userDisplay = document.getElementById("user-display");
        const name = document.createElement("strong");
        name.textContent = `${data.prenom} ${data.nom}`;
        const role = document.createElement("span");
        role.className = "badge";
        role.textContent = data.role;
        userDisplay.replaceChildren(name, role);

        const roleContent = document.getElementById("role-content");
        roleContent.replaceChildren();
        if (data.role === "Patient") {
            addTextCard(roleContent, "Votre compte est prêt", "Votre espace patient est sécurisé par un mot de passe et un code d'authentification.");
            addTextCard(roleContent, "Données médicales", "Les dossiers sont chiffrés lors de leur enregistrement. Les fonctions de consultation et de partage seront ajoutées dans une prochaine version.");
        } else if (data.role === "Médecin" || data.role === "Spécialiste") {
            addTextCard(roleContent, "Espace praticien", "La création d'un dossier médical exige le consentement explicite du patient.");
        } else if (data.role === "Administrateur") {
            const card = document.createElement("article");
            card.className = "card";
            const heading = document.createElement("h3");
            heading.textContent = "Journal d'audit";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn";
            button.textContent = "Charger le journal";
            const logs = document.createElement("pre");
            logs.className = "audit-output";
            button.addEventListener("click", () => fetchAuditLogs(logs, button));
            card.append(heading, button, logs);
            roleContent.append(card);
        } else {
            sessionStorage.removeItem("jwt_token");
            window.location.replace("index.html");
        }
    } catch {
        const status = document.getElementById("dashboard-message");
        if (status) status.textContent = "Impossible de charger votre espace. Vérifiez votre connexion.";
    }
}

async function fetchAuditLogs(logsElement, button) {
    const token = sessionStorage.getItem("jwt_token");
    button.disabled = true;
    logsElement.textContent = "Chargement…";
    try {
        const { response, data } = await apiRequest("/api/audit", { token });
        if (!response.ok) {
            logsElement.textContent = errorText(data.detail, "Journal indisponible.");
            return;
        }
        logsElement.textContent = JSON.stringify(data, null, 2);
    } catch {
        logsElement.textContent = "Impossible de charger le journal.";
    } finally {
        button.disabled = false;
    }
}

function logout() {
    sessionStorage.removeItem("jwt_token");
    sessionStorage.removeItem("pending_mfa_token");
    window.location.replace("index.html");
}

/* --- Mode démonstration locale (sans SMTP) --- */

const demoCodeNodes = new Map();

function prefillLogin(email, motDePasse) {
    showSection("login-section");
    setMessage("login-message", "");
    document.getElementById("email").value = email;
    document.getElementById("password").value = motDePasse;
    document.getElementById("password").focus();
}

function useDemoTotp(code) {
    const input = document.getElementById("mfa-code");
    if (!input) return;
    input.value = code;
    input.focus();
}

function renderDemoAccounts(accounts) {
    const container = document.getElementById("demo-accounts");
    const list = document.getElementById("demo-account-list");
    if (!container || !list) return;

    if (list.dataset.ready !== "1") {
        list.replaceChildren();
        accounts.forEach((account) => {
            const row = document.createElement("article");
            row.className = "demo-row";

            const head = document.createElement("p");
            head.className = "demo-head";
            const badge = document.createElement("span");
            badge.className = "badge";
            badge.textContent = account.role;
            const email = document.createElement("code");
            email.textContent = account.email;
            head.append(badge, email);

            const credentials = document.createElement("p");
            credentials.className = "demo-credentials";
            credentials.textContent = `Mot de passe : ${account.mot_de_passe}`;

            const codeLine = document.createElement("p");
            codeLine.className = "demo-code-line";
            const code = document.createElement("strong");
            code.className = "demo-code";
            code.textContent = account.code_totp;
            const timer = document.createElement("span");
            timer.className = "demo-timer";
            timer.textContent = `${account.expire_dans}s`;
            codeLine.append(document.createTextNode("Code MFA : "), code, document.createTextNode(" "), timer);

            const actions = document.createElement("div");
            actions.className = "demo-actions";
            const loginButton = document.createElement("button");
            loginButton.type = "button";
            loginButton.className = "btn btn-small";
            loginButton.textContent = "Pré-remplir la connexion";
            loginButton.addEventListener("click", () => prefillLogin(account.email, account.mot_de_passe));
            const codeButton = document.createElement("button");
            codeButton.type = "button";
            codeButton.className = "link-button";
            codeButton.textContent = "Utiliser le code MFA";
            codeButton.addEventListener("click", () => useDemoTotp(code.textContent));
            actions.append(loginButton, codeButton);

            row.append(head, credentials, codeLine, actions);
            list.append(row);
            demoCodeNodes.set(account.email, { code, timer });
        });
        list.dataset.ready = "1";
        container.classList.remove("hidden");
        return;
    }

    accounts.forEach((account) => {
        const node = demoCodeNodes.get(account.email);
        if (!node) return;
        node.code.textContent = account.code_totp;
        node.timer.textContent = `${account.expire_dans}s`;
    });
}

async function initDemoAccounts() {
    const container = document.getElementById("demo-accounts");
    if (!container) return;

    const refresh = async () => {
        try {
            const { response, data } = await apiRequest("/api/dev/test-accounts");
            if (response.ok && Array.isArray(data)) renderDemoAccounts(data);
        } catch {
            /* Le panneau reste masqué si le mode démonstration est désactivé. */
        }
    };

    await refresh();
    window.setInterval(refresh, 5000);
}

document.addEventListener("DOMContentLoaded", () => {
    initializeAuthentication();
    initDemoAccounts();
    document.getElementById("logout-button")?.addEventListener("click", logout);
    if (document.getElementById("dashboard-page")) {
        initDashboard();
    }
});
