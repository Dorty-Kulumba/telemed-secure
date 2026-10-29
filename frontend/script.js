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
    const setMfaMode = (useRecoveryCode) => {
        const totpGroup = document.getElementById("mfa-totp-group");
        const recoveryGroup = document.getElementById("mfa-recovery-group");
        const totpInput = document.getElementById("mfa-code");
        const recoveryInput = document.getElementById("mfa-recovery-code");
        const toggle = document.getElementById("toggle-recovery-code");
        if (!totpGroup || !recoveryGroup || !totpInput || !recoveryInput || !toggle) return;

        totpGroup.classList.toggle("hidden", useRecoveryCode);
        recoveryGroup.classList.toggle("hidden", !useRecoveryCode);
        totpInput.required = !useRecoveryCode;
        recoveryInput.required = useRecoveryCode;
        totpInput.value = "";
        recoveryInput.value = "";
        toggle.textContent = useRecoveryCode ? "Utiliser un code MFA" : "Utiliser un code de secours";
        (useRecoveryCode ? recoveryInput : totpInput).focus();
    };

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
            setMfaMode(false);
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
    document.getElementById("toggle-recovery-code")?.addEventListener("click", () => {
        const usingRecoveryCode = !document.getElementById("mfa-recovery-group")?.classList.contains("hidden");
        setMfaMode(!usingRecoveryCode);
    });

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

        const usingRecoveryCode = !document.getElementById("mfa-recovery-group")?.classList.contains("hidden");
        const code = usingRecoveryCode
            ? { recovery_code: document.getElementById("mfa-recovery-code").value.trim() }
            : { code_totp: document.getElementById("mfa-code").value.trim() };
        setBusy(mfaForm, true);
        try {
            const { response, data } = await apiRequest("/api/mfa/verify", {
                method: "POST",
                body: JSON.stringify({ challenge_token, ...code }),
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
        if (data.mot_de_passe_a_changer) {
            renderForcedPasswordChange(roleContent, token);
            return;
        }

        try {
            if (data.role === "Patient") {
                await renderPatientDashboard(roleContent, token);
            } else if (data.role === "Médecin" || data.role === "Spécialiste") {
                await renderPractitionerDashboard(roleContent, token);
            } else if (data.role === "Administrateur") {
                await renderAdminDashboard(roleContent, token, data.id);
            } else {
                sessionStorage.removeItem("jwt_token");
                window.location.replace("index.html");
            }
            renderRecoveryCodeTools(roleContent, token);
        } catch (error) {
            addTextCard(roleContent, "Chargement impossible", error.message || "Réessayez dans un instant.");
        }
    } catch {
        const status = document.getElementById("dashboard-message");
        if (status) status.textContent = "Impossible de charger votre espace. Vérifiez votre connexion.";
    }
}

async function dashboardRequest(path, token, options = {}) {
    const { response, data } = await apiRequest(path, { ...options, token });
    if (!response.ok) {
        throw new Error(errorText(data.detail, "La demande a échoué."));
    }
    return data;
}

function createDashboardCard(title, description = "") {
    const card = document.createElement("article");
    card.className = "card";
    const heading = document.createElement("h3");
    heading.textContent = title;
    card.append(heading);
    if (description) {
        const paragraph = document.createElement("p");
        paragraph.textContent = description;
        card.append(paragraph);
    }
    return card;
}

function createFormField(parent, labelText, name, options = {}) {
    const group = document.createElement("div");
    group.className = "form-group";
    const label = document.createElement("label");
    const input = document.createElement(options.multiline ? "textarea" : options.select ? "select" : "input");
    const inputId = `field-${name}-${Math.random().toString(36).slice(2, 9)}`;
    input.id = inputId;
    input.name = name;
    label.htmlFor = inputId;
    label.textContent = labelText;
    if (options.type && input.tagName === "INPUT") input.type = options.type;
    if (options.required) input.required = true;
    if (options.maxLength) input.maxLength = options.maxLength;
    if (options.minLength) input.minLength = options.minLength;
    if (options.placeholder) input.placeholder = options.placeholder;
    if (options.autocomplete) input.autocomplete = options.autocomplete;
    if (options.select) {
        options.select.forEach(({ value, label: optionLabel }) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = optionLabel;
            input.append(option);
        });
    }
    group.append(label, input);
    parent.append(group);
    return input;
}

function showCardMessage(card, message, isSuccess = false) {
    let notice = card.querySelector(".status-message");
    if (!notice) {
        notice = document.createElement("p");
        notice.className = "status-message";
        notice.setAttribute("role", "status");
        notice.setAttribute("aria-live", "polite");
        card.append(notice);
    }
    notice.textContent = message;
    notice.classList.toggle("success", isSuccess);
}

function appendOneTimeCredentials(card, result) {
    const box = document.createElement("div");
    box.className = "one-time-result";
    const title = document.createElement("p");
    title.textContent = "Informations à transmettre au titulaire par un canal privé. Elles ne seront plus affichées après cette page.";
    const output = document.createElement("pre");
    output.className = "audit-output";
    output.textContent = JSON.stringify({
        compte: result.compte,
        mot_de_passe_temporaire: result.mot_de_passe_temporaire,
        mfa: result.mfa,
        codes_de_secours: result.codes_de_secours,
    }, null, 2);
    box.append(title, output);
    card.append(box);
}

function renderRecords(container, records, emptyMessage) {
    container.replaceChildren();
    if (!records.length) {
        const empty = document.createElement("p");
        empty.textContent = emptyMessage;
        container.append(empty);
        return;
    }
    records.forEach((record) => {
        const entry = document.createElement("article");
        entry.className = "record-entry";
        const date = document.createElement("strong");
        date.textContent = record.date_creation ? new Date(record.date_creation).toLocaleString("fr-FR") : "Date inconnue";
        const content = document.createElement("p");
        content.textContent = record.contenu;
        entry.append(date, content);
        container.append(entry);
    });
}

function renderForcedPasswordChange(container, token) {
    const card = createDashboardCard("Choisissez votre mot de passe", "Votre mot de passe temporaire doit être remplacé avant d'accéder au reste de l'espace.");
    card.classList.add("forced-password-card");
    const form = document.createElement("form");
    const current = createFormField(form, "Mot de passe temporaire", "mot_de_passe_actuel", { type: "password", required: true, maxLength: 72, autocomplete: "current-password" });
    const next = createFormField(form, "Nouveau mot de passe (12 caractères minimum)", "nouveau_mot_de_passe", { type: "password", required: true, minLength: 12, maxLength: 72, autocomplete: "new-password" });
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "btn";
    submit.textContent = "Mettre à jour le mot de passe";
    form.append(submit);
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        submit.disabled = true;
        try {
            const result = await dashboardRequest("/api/account/password", token, {
                method: "PUT",
                body: JSON.stringify({ mot_de_passe_actuel: current.value, nouveau_mot_de_passe: next.value }),
            });
            sessionStorage.setItem("jwt_token", result.access_token);
            showCardMessage(card, "Mot de passe modifié. Ouverture de votre espace…", true);
            window.setTimeout(() => window.location.reload(), 400);
        } catch (error) {
            showCardMessage(card, error.message);
            submit.disabled = false;
        }
    });
    card.append(form);
    container.append(card);
}

async function renderPatientDashboard(container, token) {
    const [practitioners, consents, records] = await Promise.all([
        dashboardRequest("/api/praticiens", token),
        dashboardRequest("/api/consentements", token),
        dashboardRequest("/api/dossiers/moi", token),
    ]);
    const consentByPractitioner = new Map(consents.map((consent) => [consent.medecin_id, consent.statut]));

    const consentCard = createDashboardCard("Gérer les accès", "Autorisez un praticien à consulter vos dossiers, ou révoquez son accès.");
    if (!practitioners.length) {
        const empty = document.createElement("p");
        empty.textContent = "Aucun praticien actif n'est disponible pour le moment.";
        consentCard.append(empty);
    } else {
        const form = document.createElement("form");
        const practitionerSelect = createFormField(form, "Praticien", "medecin_id", {
            required: true,
            select: practitioners.map((person) => ({ value: String(person.id), label: `${person.prenom} ${person.nom}` })),
        });
        const consentSelect = createFormField(form, "Autorisation", "statut", {
            required: true,
            select: [
                { value: "true", label: "Autoriser l'accès" },
                { value: "false", label: "Révoquer l'accès" },
            ],
        });
        const syncConsent = () => {
            const current = consentByPractitioner.get(Number(practitionerSelect.value));
            consentSelect.value = current ? "true" : "false";
        };
        practitionerSelect.addEventListener("change", syncConsent);
        syncConsent();
        const submit = document.createElement("button");
        submit.type = "submit";
        submit.className = "btn";
        submit.textContent = "Enregistrer mon choix";
        form.append(submit);
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            submit.disabled = true;
            try {
                await dashboardRequest("/api/consentements", token, {
                    method: "PUT",
                    body: JSON.stringify({ medecin_id: Number(practitionerSelect.value), statut: consentSelect.value === "true" }),
                });
                consentByPractitioner.set(Number(practitionerSelect.value), consentSelect.value === "true");
                showCardMessage(consentCard, "Votre choix a été enregistré.", true);
            } catch (error) {
                showCardMessage(consentCard, error.message);
            } finally {
                submit.disabled = false;
            }
        });
        consentCard.append(form);
    }
    container.append(consentCard);

    const recordsCard = createDashboardCard("Mes dossiers médicaux", "Les dossiers ne sont visibles que par vous et par les praticiens auxquels vous avez donné accès.");
    const recordsList = document.createElement("div");
    recordsList.className = "records-list";
    renderRecords(recordsList, records, "Aucun dossier médical n'a été ajouté.");
    recordsCard.append(recordsList);
    container.append(recordsCard);
}

async function renderPractitionerDashboard(container, token) {
    const patients = await dashboardRequest("/api/patients-consentis", token);
    const card = createDashboardCard("Patients ayant donné leur accord", "Vous pouvez consulter leurs dossiers et en ajouter un nouveau tant que leur autorisation reste active.");
    if (!patients.length) {
        const empty = document.createElement("p");
        empty.textContent = "Aucun patient ne vous a encore autorisé à consulter ses dossiers.";
        card.append(empty);
        container.append(card);
        return;
    }

    const patientSelect = createFormField(card, "Patient", "patient_id", {
        required: true,
        select: patients.map((patient) => ({ value: String(patient.id), label: `${patient.prenom} ${patient.nom}` })),
    });
    const recordsList = document.createElement("div");
    recordsList.className = "records-list";
    card.append(recordsList);
    const loadRecords = async () => {
        recordsList.textContent = "Chargement des dossiers…";
        try {
            const records = await dashboardRequest(`/api/patients/${encodeURIComponent(patientSelect.value)}/dossiers`, token);
            renderRecords(recordsList, records, "Aucun dossier n'a été ajouté pour ce patient.");
        } catch (error) {
            recordsList.textContent = error.message;
        }
    };
    patientSelect.addEventListener("change", loadRecords);
    await loadRecords();
    container.append(card);

    const createCard = createDashboardCard("Ajouter un dossier", "Le contenu sera chiffré avant son enregistrement.");
    const form = document.createElement("form");
    const recordPatient = createFormField(form, "Patient", "patient_id", {
        required: true,
        select: patients.map((patient) => ({ value: String(patient.id), label: `${patient.prenom} ${patient.nom}` })),
    });
    const content = createFormField(form, "Contenu du dossier", "contenu", { required: true, maxLength: 100000, multiline: true });
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "btn";
    submit.textContent = "Enregistrer le dossier";
    form.append(submit);
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        submit.disabled = true;
        try {
            await dashboardRequest("/api/dossiers", token, {
                method: "POST",
                body: JSON.stringify({ patient_id: Number(recordPatient.value), contenu: content.value.trim() }),
            });
            content.value = "";
            showCardMessage(createCard, "Dossier enregistré et chiffré.", true);
            if (patientSelect.value === recordPatient.value) await loadRecords();
        } catch (error) {
            showCardMessage(createCard, error.message);
        } finally {
            submit.disabled = false;
        }
    });
    createCard.append(form);
    container.append(createCard);
}

async function renderAdminDashboard(container, token, currentUserId) {
    const createCard = createDashboardCard("Créer un compte professionnel", "Le titulaire devra remplacer son mot de passe temporaire à sa première connexion.");
    const form = document.createElement("form");
    createFormField(form, "Nom", "nom", { required: true, maxLength: 100 });
    createFormField(form, "Prénom", "prenom", { required: true, maxLength: 100 });
    createFormField(form, "Adresse e-mail", "email", { type: "email", required: true, maxLength: 150 });
    createFormField(form, "Téléphone (facultatif)", "telephone", { type: "tel", maxLength: 50 });
    const role = createFormField(form, "Rôle", "role", {
        required: true,
        select: [
            { value: "Médecin", label: "Médecin" },
            { value: "Spécialiste", label: "Spécialiste" },
            { value: "Administrateur", label: "Administrateur" },
        ],
    });
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "btn";
    submit.textContent = "Créer le compte";
    form.append(submit);
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        submit.disabled = true;
        const controls = Object.fromEntries(new FormData(form).entries());
        try {
            const result = await dashboardRequest("/api/admin/users", token, { method: "POST", body: JSON.stringify(controls) });
            appendOneTimeCredentials(createCard, result);
            showCardMessage(createCard, "Compte professionnel créé.", true);
            form.reset();
            await refreshAdminUsers(usersList, token, currentUserId);
        } catch (error) {
            showCardMessage(createCard, error.message);
        } finally {
            submit.disabled = false;
        }
    });
    createCard.append(form);
    container.append(createCard);

    const usersCard = createDashboardCard("Comptes utilisateurs", "Les identifiants temporaires et les clés MFA ne sont montrés qu'au moment de la création ou de la réinitialisation.");
    const usersList = document.createElement("div");
    usersList.className = "users-list";
    usersCard.append(usersList);
    container.append(usersCard);
    await refreshAdminUsers(usersList, token, currentUserId);

    const auditCard = createDashboardCard("Journal d'audit", "Les 500 actions les plus récentes.");
    const auditButton = document.createElement("button");
    auditButton.type = "button";
    auditButton.className = "btn btn-secondary";
    auditButton.textContent = "Charger le journal";
    const logs = document.createElement("pre");
    logs.className = "audit-output";
    auditButton.addEventListener("click", () => fetchAuditLogs(logs, auditButton));
    auditCard.append(auditButton, logs);
    container.append(auditCard);
}

async function refreshAdminUsers(list, token, currentUserId) {
    try {
        const users = await dashboardRequest("/api/admin/users", token);
        list.replaceChildren();
        users.forEach((user) => {
            const row = document.createElement("article");
            row.className = "user-entry";
            const identity = document.createElement("p");
            identity.textContent = `${user.prenom} ${user.nom} — ${user.email} (${user.role}) — ${user.actif ? "Actif" : "Désactivé"}`;
            row.append(identity);
            const actions = document.createElement("div");
            actions.className = "inline-actions";
            const statusButton = document.createElement("button");
            statusButton.type = "button";
            statusButton.className = "btn btn-secondary btn-small";
            statusButton.textContent = user.actif ? "Désactiver" : "Réactiver";
            statusButton.disabled = user.id === currentUserId && user.actif;
            statusButton.addEventListener("click", async () => {
                statusButton.disabled = true;
                try {
                    await dashboardRequest(`/api/admin/users/${user.id}/status`, token, {
                        method: "PATCH",
                        body: JSON.stringify({ actif: !user.actif }),
                    });
                    await refreshAdminUsers(list, token, currentUserId);
                } catch (error) {
                    showCardMessage(list.closest(".card"), error.message);
                    statusButton.disabled = false;
                }
            });
            const resetButton = document.createElement("button");
            resetButton.type = "button";
            resetButton.className = "btn btn-secondary btn-small";
            resetButton.textContent = "Réinitialiser l'accès";
            resetButton.disabled = user.id === currentUserId;
            resetButton.addEventListener("click", async () => {
                resetButton.disabled = true;
                try {
                    const result = await dashboardRequest(`/api/admin/users/${user.id}/reset-access`, token, { method: "POST" });
                    appendOneTimeCredentials(list.closest(".card"), result);
                    showCardMessage(list.closest(".card"), `Accès réinitialisé pour ${user.email}.`, true);
                } catch (error) {
                    showCardMessage(list.closest(".card"), error.message);
                } finally {
                    resetButton.disabled = false;
                }
            });
            actions.append(statusButton, resetButton);
            row.append(actions);
            list.append(row);
        });
        if (!users.length) {
            const empty = document.createElement("p");
            empty.textContent = "Aucun compte.";
            list.append(empty);
        }
    } catch (error) {
        list.textContent = error.message;
    }
}

function renderRecoveryCodeTools(container, token) {
    const card = createDashboardCard("Codes de secours MFA", "Générez une nouvelle série si vous avez perdu vos codes. Les anciens seront invalidés.");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-secondary";
    button.textContent = "Régénérer les codes";
    button.addEventListener("click", async () => {
        button.disabled = true;
        try {
            const result = await dashboardRequest("/api/mfa/recovery-codes", token, { method: "POST" });
            const codes = document.createElement("pre");
            codes.className = "recovery-codes";
            codes.textContent = result.codes_de_secours.join("\n");
            card.querySelector(".recovery-codes")?.remove();
            card.append(codes);
            showCardMessage(card, "Copiez ces codes dans un endroit privé. Ils ne seront plus réaffichés.", true);
        } catch (error) {
            showCardMessage(card, error.message);
        } finally {
            button.disabled = false;
        }
    });
    card.append(button);
    container.append(card);
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
