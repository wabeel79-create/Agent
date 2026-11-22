/* Kapsi ISO — PWA (sans dépendance, fonctionne hors Internet sur le réseau du cabinet) */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const store = {
  get(k, d = "") { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* stockage indisponible */ } },
};
let catalog = null;
let history = [];

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.add("hidden"), 2500);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  const tok = store.get("kapsi_token"); if (tok) headers["X-Kapsi-Token"] = tok;
  const r = await fetch(path, { ...opts, headers: { ...headers, ...(opts.headers || {}) } });
  if (r.status === 401) { toast("Jeton d'accès requis (⚙)"); throw new Error("401"); }
  if (!r.ok) { const e = await r.json().catch(() => ({})); toast(e.detail || "Erreur " + r.status); throw new Error(r.status); }
  return r;
}
const getJSON = async (p) => (await api(p)).json();
const postJSON = async (p, body) => (await api(p, { method: "POST", body: JSON.stringify(body) })).json();

function setTitle(t, canBack) { $("#title").textContent = t; $("#back").classList.toggle("hidden", !canBack); }
function go(fn, ...args) { history.push([fn, args]); fn(...args); window.scrollTo(0, 0); }
$("#back").onclick = () => { history.pop(); const [fn, args] = history[history.length - 1] || [home, []]; fn(...args); };
$("#settings").onclick = () => go(settings);

/* ---------------------------------------------------------------- accueil */
async function home() {
  setTitle("Kapsi ISO", false);
  const clients = await getJSON("/api/clients");
  view.innerHTML = `
  <section class="card"><h2>Clients du cabinet</h2>
    ${clients.length ? `<ul class="list">${clients.map(c => `<li data-id="${c.id}"><div><b>${esc(c.name)}</b><div class="sub">${esc(c.sector)} · ${esc(c.size)} salariés</div></div><span>›</span></li>`).join("")}</ul>`
      : `<p class="sub">Aucun client. Créez le premier ci-dessous.</p>`}
  </section>
  <section class="card"><h2>Nouveau client</h2>
    <form id="nc">
      <label>Raison sociale *</label><input name="name" required>
      <label>Secteur</label><input name="sector" placeholder="ex. Fabrication de pièces métalliques">
      <label>Effectif</label><input name="size" inputmode="numeric" placeholder="ex. 50">
      <label>Activités principales (séparées par des virgules)</label><textarea name="activities" placeholder="ex. Découpe laser, Soudure, Peinture"></textarea>
      <label>Contact</label><input name="contact">
      <p><button class="btn">Créer le client</button></p>
    </form>
  </section>
  <section class="card"><h2>Assistant ISO</h2><p class="sub">Questions sur les exigences, sans connexion Internet.</p>
    <button class="btn alt" id="gochat">Ouvrir l'assistant</button></section>`;
  view.querySelectorAll(".list li").forEach(li => li.onclick = () => go(client, +li.dataset.id));
  $("#gochat").onclick = () => go(chat);
  $("#nc").onsubmit = async (e) => {
    e.preventDefault();
    const c = await postJSON("/api/clients", Object.fromEntries(new FormData(e.target)));
    toast("Client créé"); go(client, c.id);
  };
}

/* ------------------------------------------------------------ fiche client */
async function client(id, tab = "gen") {
  const c = (await getJSON("/api/clients")).find(x => x.id === id);
  if (!c) return home();
  setTitle(c.name, true);
  catalog = catalog || await getJSON("/api/catalog");
  const tabs = [["gen", "Générer"], ["gap", "Analyse d'écarts"], ["docs", "Documents"]];
  view.innerHTML = `<div class="tabs">${tabs.map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "on" : ""}">${l}</button>`).join("")}</div><div id="tab"></div>`;
  view.querySelectorAll(".tabs button").forEach(b => b.onclick = () => client(id, b.dataset.t));
  const el = $("#tab");
  if (tab === "gen") {
    el.innerHTML = `<section class="card"><h2>Livrables</h2><div class="grid">${catalog.generators.map(g => `<button class="tile" data-k="${g.kind}">${esc(g.label)}</button>`).join("")}</div>
      <p class="note">Chaque livrable est un projet à relire et valider par le consultant.</p></section>`;
    el.querySelectorAll(".tile").forEach(t => t.onclick = async () => {
      t.disabled = true; t.textContent = "Génération…";
      const doc = await postJSON(`/api/clients/${id}/generate`, { kind: t.dataset.k });
      go(showDoc, doc.id);
    });
  } else if (tab === "gap") {
    const saved = await getJSON(`/api/clients/${id}/gap`);
    el.innerHTML = `<section class="card"><h2>Évaluation ISO 9001 par exigence</h2>
      <p class="sub">C = conforme · P = partiel · NC = non conforme · NA = non applicable</p>
      <div id="rows">${catalog.clauses.map(cl => {
        const s = saved[cl.id]?.status || "";
        return `<div class="gap-row" data-c="${cl.id}"><b>${cl.id}</b><div>${esc(cl.title)}
          <div class="seg">${["C", "P", "NC", "NA"].map(k => `<button type="button" data-s="${k}" class="${k === s ? "on" : ""}">${k}</button>`).join("")}</div>
          <input class="obs" placeholder="Observation" value="${esc(saved[cl.id]?.note || "")}"></div></div>`;
      }).join("")}</div>
      <p><button class="btn" id="mkgap">Générer le rapport d'écarts</button></p></section>`;
    el.querySelectorAll(".seg button").forEach(b => b.onclick = () => {
      b.parentElement.querySelectorAll("button").forEach(x => x.classList.remove("on")); b.classList.add("on");
    });
    $("#mkgap").onclick = async () => {
      const answers = {};
      el.querySelectorAll(".gap-row").forEach(r => {
        const on = r.querySelector(".seg .on");
        answers[r.dataset.c] = { status: on ? on.dataset.s : "NC", note: r.querySelector(".obs").value };
      });
      const doc = await postJSON(`/api/clients/${id}/gap`, { answers });
      go(showDoc, doc.id);
    };
  } else {
    const docs = await getJSON(`/api/clients/${id}/documents`);
    el.innerHTML = `<section class="card"><h2>Documents générés</h2>${docs.length
      ? `<ul class="list">${docs.map(d => `<li data-id="${d.id}"><div>${esc(d.title)}<div class="sub">${esc(d.created_at)}</div></div><span>›</span></li>`).join("")}</ul>`
      : `<p class="sub">Aucun document.</p>`}</section>
      <section class="card"><button class="btn danger" id="del">Supprimer ce client</button></section>`;
    el.querySelectorAll(".list li").forEach(li => li.onclick = () => go(showDoc, +li.dataset.id));
    $("#del").onclick = async () => {
      if (!window.confirm("Supprimer définitivement ce client et ses documents ?")) return;
      await api(`/api/clients/${id}`, { method: "DELETE" }); history = []; go(home);
    };
  }
}

/* ------------------------------------------------------------- document */
async function showDoc(did) {
  const d = await getJSON(`/api/documents/${did}`);
  setTitle(d.title, true);
  const sec = (s) => `<section class="card"><h2>${esc(s.heading)}</h2>
    ${s.score !== undefined ? `<div class="score">${s.score} %</div>` : ""}
    ${(s.paragraphs || []).map(p => `<p>${esc(p)}</p>`).join("")}
    ${s.bullets ? `<ul>${s.bullets.map(b => `<li>${esc(b)}</li>`).join("")}</ul>` : ""}
    ${s.table ? `<div class="tbl"><table><thead><tr>${s.table.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${s.table.rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : ""}</section>`;
  view.innerHTML = `<div class="row" style="margin-bottom:1rem"><button class="btn" id="dl">Télécharger (Word)</button>
    <span class="sub">${esc(d.client)} · ${esc(d.date)}</span></div>${d.sections.map(sec).join("")}<p class="note">${esc(d.footer)}</p>`;
  $("#dl").onclick = async () => {
    const r = await api(`/api/documents/${did}/docx`);
    const url = URL.createObjectURL(await r.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: d.title.replace(/[^\w-]+/g, "_") + ".docx" });
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
}

/* ---------------------------------------------------------------- chat */
function chat() {
  setTitle("Assistant ISO", true);
  view.innerHTML = `<section class="card chat"><div id="log"><p class="sub">Exemples : « Que demande le 7.5 ? », « Qu'est-ce qui change en 2026 sur les risques ? »</p></div>
    <form id="f" class="row" style="margin-top:1rem"><input name="q" placeholder="Votre question" required style="flex:1"><button class="btn">Envoyer</button></form></section>`;
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    const q = e.target.q.value; e.target.q.value = "";
    const log = $("#log");
    log.insertAdjacentHTML("beforeend", `<div class="q">${esc(q)}</div><div class="a">…</div>`);
    const r = await postJSON("/api/ask", { question: q });
    log.lastElementChild.textContent = r.answer + (r.sources.length ? "\n\nRéférences : " + r.sources.join(" ; ") : "");
  };
}

/* ------------------------------------------------------------- réglages */
async function settings() {
  setTitle("Réglages", true);
  const h = await getJSON("/api/health");
  view.innerHTML = `<section class="card"><h2>Serveur</h2>
    <p>Version ${esc(h.version)} · moteur IA : <b>${esc(h.ai_backend)}</b> · données stockées sur le serveur du cabinet uniquement.</p></section>
    <section class="card"><h2>Jeton d'accès</h2><input id="tok" value="${esc(store.get("kapsi_token"))}" placeholder="Fourni par l'administrateur">
    <p><button class="btn" id="save">Enregistrer</button></p></section>
    <section class="card"><h2>Installer sur iPhone</h2><p class="sub">Dans Safari : bouton Partager → « Sur l'écran d'accueil ».</p></section>`;
  $("#save").onclick = () => { store.set("kapsi_token", $("#tok").value.trim()); toast("Enregistré"); };
}

/* ---------------------------------------------------------------- init */
(async () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  try { const h = await getJSON("/api/health"); $("#status").textContent = `v${h.version} · ${h.ai_backend === "none" ? "mode hors ligne" : "IA : " + h.ai_backend}`; } catch { $("#status").textContent = "serveur injoignable"; }
  go(home);
})();
