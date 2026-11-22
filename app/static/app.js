/* Kapsi-Q — interface (PWA sans dépendance externe ; Chart.js embarqué) */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const view = $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ls = {
  get(k, d = "") { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* indisponible */ } },
};
let CAT = null;
let charts = [];
const stack = [];
const GRADE_COLOR = { PF: "#1e7a4c", C: "#4fae7a", OA: "#b86e00", NCm: "#c92a45", NCM: "#7d1426", NA: "#8a96a0" };
const stdColor = (s) => CAT?.standards.find((x) => x.code === s)?.color || "#7b2ff7";
/* Accessibilité : assombrit une couleur jusqu'à un contraste ≥ 4.5:1 avec du texte blanc (WCAG AA) */
function readable(hex) {
  let [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const lum = (r, g, b) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }).reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
  for (let k = 0; k < 20 && 1.05 / (lum(r, g, b) + 0.05) < 4.6; k++) { r *= 0.92; g *= 0.92; b *= 0.92; }
  return "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
}
const chip = (s) => `<span class="chip" style="background:${readable(stdColor(s))}">${esc(s)}</span>`;

/* Accessibilité : relie chaque <label> à son champ, nomme les champs sans label, rend les éléments cliquables utilisables au clavier */
let uid = 0;
function a11y(root = document) {
  $$("label", root).forEach((l) => {
    if (l.htmlFor || l.querySelector("input,select,textarea")) return;
    const f = l.nextElementSibling;
    if (f && /^(INPUT|SELECT|TEXTAREA)$/.test(f.tagName)) { f.id = f.id || "f" + ++uid; l.htmlFor = f.id; }
  });
  $$("input,select,textarea", root).forEach((f) => {
    if (f.labels?.length || f.getAttribute("aria-label")) return;
    f.setAttribute("aria-label", f.placeholder || f.name || f.id || "champ");
  });
  $$("li[data-id],li[data-a],li[data-d],tr[data-c]", root).forEach((e) => { e.tabIndex = 0; e.classList.add("clickable"); });
  $$(".tbl", root).forEach((t, i) => { t.tabIndex = 0; t.setAttribute("role", "region"); t.setAttribute("aria-label", "Tableau : " + (t.closest(".card")?.querySelector("h2")?.textContent || i + 1)); });
}
document.addEventListener("keydown", (e) => {
  const t = e.target;
  if ((e.key === "Enter" || e.key === " ") && t.matches?.(".clickable,.side a")) { e.preventDefault(); t.click(); }
});
const GAPL = { C: "Conforme", P: "Partiellement conforme", NC: "Non conforme", NA: "Non applicable" };
function toggleRow(row, force) {
  const b = $(".body", row), t = $(".tog", row); const open = force ?? b.hidden;
  b.hidden = !open; t.setAttribute("aria-expanded", String(open)); row.classList.toggle("open", open);
}
document.addEventListener("click", (e) => { const t = e.target.closest?.(".tog"); if (t) toggleRow(t.closest(".clause")); });
function saved() { const s = $("#savestate"); s.textContent = "✓ Enregistré"; s.classList.add("on"); clearTimeout(saved.t); saved.t = setTimeout(() => s.classList.remove("on"), 1600); }
const pct = (v) => (v === null || v === undefined ? "—" : v + " %");

function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.add("hidden"), 2600); }
async function api(path, opts = {}) {
  const h = { "Content-Type": "application/json" }; const tok = ls.get("kapsi_token"); if (tok) h["X-Kapsi-Token"] = tok;
  const r = await fetch(path, { ...opts, headers: h });
  if (r.status === 401) { toast("Jeton d'accès requis (Réglages)"); throw new Error("401"); }
  if (!r.ok) { const e = await r.json().catch(() => ({})); toast(typeof e.detail === "string" ? e.detail : "Erreur " + r.status); throw new Error(r.status); }
  return r;
}
const get = async (p) => (await api(p)).json();
const send = async (p, body, method = "POST") => (await api(p, { method, body: body === undefined ? undefined : JSON.stringify(body) })).json();
async function busy(btn, fn) { const t = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spin"></span> ${btn.dataset.busy || "Génération…"}`; try { return await fn(); } finally { btn.disabled = false; btn.innerHTML = t; } }

/* ----------------------------------------------------------- navigation */
const ROUTES = {};
function nav(name, ...args) { stack.push([name, args]); render(); }
function render() {
  charts.forEach((c) => c.destroy()); charts = [];
  const [name, args] = stack[stack.length - 1];
  $$(".side a").forEach((a) => { const on = a.dataset.r === stack[0][0]; a.classList.toggle("on", on); on ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"); });
  $("#back").classList.toggle("hidden", stack.length < 2);
  window.scrollTo(0, 0);
  ROUTES[name](...args).then(() => { a11y(view); $("#title").focus({ preventScroll: true }); }).catch((e) => { console.error(e); });
}
$("#back").onclick = () => { if (stack.length > 1) { stack.pop(); render(); } };
$$(".side a").forEach((a) => (a.onclick = (e) => { e.preventDefault(); stack.length = 0; nav(a.dataset.r); }));
const title = (t) => { $("#title").textContent = t; document.title = t + " · Kapsi-Q"; };

function chart(el, cfg) { if (window.Chart) charts.push(new Chart(el, cfg)); }
const radar = (el, data, label = "Conformité %") => chart(el, { type: "radar", data: { labels: Object.keys(data).map((k) => (k === "Annexe A" ? k : "Ch. " + k)), datasets: [{ label, data: Object.values(data), fill: true, backgroundColor: "rgba(240,53,138,.18)", borderColor: "#9b2cf0", pointBackgroundColor: "#f0358a" }] }, options: { maintainAspectRatio: false, scales: { r: { min: 0, max: 100, ticks: { stepSize: 25 } } }, plugins: { legend: { display: false } } } });

/* -------------------------------------------------------- tableau de bord */
ROUTES.dashboard = async () => {
  title("Tableau de bord");
  const d = await get("/api/dashboard");
  const avg = (arr) => (arr.length ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : null);
  const gaps = d.projects.filter((p) => p.gap !== null).map((p) => p.gap);
  view.innerHTML = `
  <div class="kpis">
    <div class="kpi"><b>${d.clients}</b><small>Clients</small></div>
    <div class="kpi"><b>${d.projects.length}</b><small>Projets de mise en place</small></div>
    <div class="kpi"><b>${pct(avg(gaps))}</b><small>Conformité moyenne (diagnostics)</small></div>
    <div class="kpi"><b>${d.audits}</b><small>Audits</small></div>
    <div class="kpi"><b>${d.documents}</b><small>Livrables générés</small></div>
  </div>
  <div class="cols">
    <section class="card"><h2>Projets par norme</h2><div class="chartbox"><canvas id="c1"></canvas></div></section>
    <section class="card"><h2>Constats d'audit (tous audits)</h2><div class="chartbox"><canvas id="c2"></canvas></div></section>
  </div>
  <section class="card"><h2>Avancement des projets</h2>${d.projects.length ? `<div class="tbl"><table><thead><tr><th>Client</th><th>Norme</th><th>Diagnostic</th><th>Feuille de route</th></tr></thead><tbody>
    ${d.projects.map((p) => `<tr data-c="${p.client_id}" data-s="${esc(p.standard)}" style="cursor:pointer"><td>${esc(p.client)}</td><td>${chip(p.standard)}</td>
      <td><div class="row"><div class="bar grow"><i style="width:${p.gap || 0}%"></i></div><small>${pct(p.gap)}</small></div></td>
      <td><div class="row"><div class="bar grow"><i style="width:${p.roadmap}%"></i></div><small>${p.roadmap} %</small></div></td></tr>`).join("")}</tbody></table></div>`
    : `<div class="empty">Aucun projet. <button class="btn sm" id="go-new">Créer un premier client</button></div>`}</section>
  <section class="card"><h2>Derniers audits</h2>${d.recent_audits.length ? `<ul class="list">${d.recent_audits.map((a) => `<li data-a="${a.id}"><div><b>${esc(a.client)}</b> · ${esc(a.type)}<div>${a.standards.map(chip).join("")}</div></div><div class="sub">${pct(a.conformity)} · ${esc(a.verdict)}</div></li>`).join("")}</ul>` : `<p class="sub">Aucun audit.</p>`}</section>`;
  $$("tr[data-c]").forEach((r) => (r.onclick = () => nav("project", +r.dataset.c, r.dataset.s)));
  $$("li[data-a]").forEach((l) => (l.onclick = () => nav("audit", +l.dataset.a)));
  $("#go-new")?.addEventListener("click", () => nav("clientForm"));
  const bs = d.by_standard;
  chart($("#c1"), { type: "doughnut", data: { labels: Object.keys(bs), datasets: [{ data: Object.values(bs), backgroundColor: Object.keys(bs).map(stdColor) }] }, options: { maintainAspectRatio: false, plugins: { legend: { position: "right" } } } });
  const f = Object.entries(d.findings).filter(([k]) => k !== "NA");
  chart($("#c2"), { type: "bar", data: { labels: f.map(([k]) => CAT.audit_grades[k]), datasets: [{ data: f.map(([, v]) => v), backgroundColor: f.map(([k]) => GRADE_COLOR[k]), borderRadius: 6 }] }, options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
};

/* ---------------------------------------------------------------- clients */
ROUTES.clients = async () => {
  title("Clients");
  const cl = await get("/api/clients");
  view.innerHTML = `<div class="row" style="margin-bottom:1rem"><button class="btn" id="new">+ Nouveau client</button></div>
    <section class="card">${cl.length ? `<ul class="list">${cl.map((c) => `<li data-id="${c.id}"><div><b>${esc(c.name)}</b><div class="sub">${esc(c.sector)}${c.size ? " · " + esc(c.size) + " salariés" : ""}</div><div>${c.standards.map(chip).join("")}</div></div><span>›</span></li>`).join("")}</ul>` : `<div class="empty">Aucun client pour l'instant.</div>`}</section>`;
  $("#new").onclick = () => nav("clientForm");
  $$(".list li").forEach((li) => (li.onclick = () => nav("client", +li.dataset.id)));
};

ROUTES.clientForm = async (id) => {
  const c = id ? await get(`/api/clients/${id}`) : {};
  title(id ? "Modifier le client" : "Nouveau client");
  view.innerHTML = `<section class="card"><form id="f">
    <label>Raison sociale *</label><input name="name" required value="${esc(c.name)}">
    <label>Secteur d'activité</label><input name="sector" value="${esc(c.sector)}" placeholder="ex. Fabrication de pièces automobiles">
    <label>Effectif</label><input name="size" inputmode="numeric" value="${esc(c.size)}" placeholder="ex. 120">
    <label>Activités / processus de réalisation (séparés par des virgules)</label><textarea name="activities" placeholder="ex. Injection plastique, Assemblage, Contrôle final">${esc(c.activities)}</textarea>
    <label>Contact</label><input name="contact" value="${esc(c.contact)}">
    ${id ? "" : `<label>Normes visées</label><div class="grid">${CAT.standards.map((s) => `<label class="check tile" style="margin:0"><input type="checkbox" name="std" value="${esc(s.code)}" ${s.code === "ISO 9001" ? "checked" : ""}><span>${chip(s.code)} ${esc(s.label)}</span></label>`).join("")}</div>`}
    <p class="row"><button class="btn">${id ? "Enregistrer" : "Créer le client"}</button></p></form></section>`;
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = { name: fd.get("name"), sector: fd.get("sector"), size: fd.get("size"), activities: fd.get("activities"), contact: fd.get("contact"), standards: fd.getAll("std") };
    if (id) { await send(`/api/clients/${id}`, body, "PUT"); toast("Enregistré"); stack.pop(); render(); }
    else { const r = await send("/api/clients", body); toast("Client créé"); stack.pop(); nav("client", r.id); }
  };
};

ROUTES.client = async (id, tab = "projects") => {
  const c = await get(`/api/clients/${id}`);
  title(c.name);
  const tabs = [["projects", "Mise en place"], ["audits", "Audits"], ["docs", "Documents"], ["info", "Fiche"]];
  view.innerHTML = `<div class="tabs">${tabs.map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "on" : ""}">${l}</button>`).join("")}</div><div id="tab"></div>`;
  $$(".tabs button").forEach((b) => (b.onclick = () => { stack[stack.length - 1][1] = [id, b.dataset.t]; render(); }));
  const el = $("#tab");
  if (tab === "projects") {
    const have = c.projects.map((p) => p.standard);
    const left = CAT.standards.filter((s) => !have.includes(s.code));
    el.innerHTML = `<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(270px,1fr))">${c.projects.map((p) => {
      const n = CAT.roadmap.reduce((a, ph) => a + ph.tasks.length, 0); const done = Object.values(p.progress).filter(Boolean).length; const rp = Math.round(100 * done / n);
      return `<div class="projcard" style="border-top-color:${stdColor(p.standard)}"><div class="row"><div class="ring" style="--p:${p.gap.score || 0};--c:${stdColor(p.standard)}" data-v="${pct(p.gap.score)}"></div>
        <div class="grow"><b>${esc(p.standard)}</b><div class="sub">${esc(CAT.standards.find((s) => s.code === p.standard)?.label)}</div><div class="sub">Diagnostic : ${p.gap.answered}/${p.gap.total} exigences</div>
        <div class="row" style="margin-top:.4rem"><div class="bar grow"><i style="width:${rp}%"></i></div><small>${rp} %</small></div></div></div>
        <p class="row" style="margin:.8rem 0 0"><button class="btn sm" data-open="${esc(p.standard)}">Ouvrir le projet</button></p></div>`;
    }).join("") || `<div class="empty">Aucune norme.</div>`}</div>
      ${left.length ? `<section class="card" style="margin-top:1rem"><h2>Ajouter une norme</h2><div class="row"><select id="addstd" class="grow">${left.map((s) => `<option>${esc(s.code)}</option>`).join("")}</select><button class="btn" id="add">Ajouter</button></div></section>` : ""}`;
    $$("[data-open]").forEach((b) => (b.onclick = () => nav("project", id, b.dataset.open)));
    $("#add")?.addEventListener("click", async () => { await send(`/api/clients/${id}/projects/${encodeURIComponent($("#addstd").value)}`); render(); });
  } else if (tab === "audits") {
    el.innerHTML = `<div class="row" style="margin-bottom:1rem"><button class="btn" id="na">+ Nouvel audit</button></div><section class="card">${c.audits.length ? `<ul class="list">${c.audits.map((a) => `<li data-a="${a.id}"><div><b>${esc(CAT.audit_types[a.type])}</b> · ${esc(a.date)}<div>${a.standards.map(chip).join("")}</div></div><div class="sub">${pct(a.stats.conformity)}<br>${esc(a.stats.verdict)}</div></li>`).join("")}</ul>` : `<div class="empty">Aucun audit.</div>`}</section>`;
    $("#na").onclick = () => nav("auditForm", id);
    $$("li[data-a]").forEach((l) => (l.onclick = () => nav("audit", +l.dataset.a)));
  } else if (tab === "docs") {
    el.innerHTML = `<section class="card">${c.documents.length ? `<ul class="list">${c.documents.map((d) => `<li data-d="${d.id}"><div>${esc(d.title)}<div class="sub">${d.standard ? chip(d.standard.split(",")[0]) : ""} ${esc(d.created_at)}</div></div><span>›</span></li>`).join("")}</ul>` : `<div class="empty">Aucun document.</div>`}</section>`;
    $$("li[data-d]").forEach((l) => (l.onclick = () => nav("doc", +l.dataset.d)));
  } else {
    el.innerHTML = `<section class="card"><table><tbody>${[["Secteur", c.sector], ["Effectif", c.size], ["Activités", c.activities], ["Contact", c.contact], ["Créé le", c.created_at]].map(([k, v]) => `<tr><th style="width:30%">${k}</th><td>${esc(v)}</td></tr>`).join("")}</tbody></table>
      <p class="row" style="margin-top:1rem"><button class="btn alt" id="ed">Modifier</button><button class="btn danger" id="del">Supprimer le client</button></p></section>`;
    $("#ed").onclick = () => nav("clientForm", id);
    $("#del").onclick = async () => { if (!confirm("Supprimer définitivement ce client et toutes ses données ?")) return; await send(`/api/clients/${id}`, undefined, "DELETE"); stack.length = 0; nav("clients"); };
  }
};

/* ------------------------------------------------- projet de mise en place */
ROUTES.project = async (id, std, tab = "gap") => {
  const c = await get(`/api/clients/${id}`);
  const p = c.projects.find((x) => x.standard === std);
  if (!p) { await send(`/api/clients/${id}/projects/${encodeURIComponent(std)}`); return render(); }
  title(`${c.name} — ${std}`);
  const tabs = [["gap", "Diagnostic"], ["road", "Feuille de route"], ["gen", "Livrables"]];
  view.innerHTML = `<div class="tabs">${tabs.map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "on" : ""}">${l}</button>`).join("")}</div><div id="tab"></div>`;
  $$(".tabs button").forEach((b) => (b.onclick = () => { stack[stack.length - 1][1] = [id, std, b.dataset.t]; render(); }));
  const el = $("#tab");
  if (tab === "gap") {
    const g = await get(`/api/clients/${id}/gap/${encodeURIComponent(std)}`);
    el.innerHTML = `<div class="cols"><section class="card"><h2>Résultat du diagnostic</h2><div class="row"><div class="score" id="sc">${pct(g.score.score)}</div><div class="sub" id="cnt"></div></div><div class="chartbox"><canvas id="rd"></canvas></div>
        <p class="sub">Évaluez chaque exigence avec le client : <b>C</b> conforme, <b>P</b> partiel, <b>NC</b> non conforme, <b>NA</b> non applicable. Enregistrement automatique.</p>
        <p class="row"><button class="btn" id="rep">Générer le rapport d'écarts</button></p></section></div>
      <section class="card"><h2>Exigences ${esc(std)} (${g.clauses.length})</h2>${g.clauses.map((cl) => {
        const a = g.answers[cl.id] || {};
        return `<div class="clause" data-c="${esc(cl.id)}"><div class="head"><button type="button" class="tog" aria-expanded="false"><span class="cid">${esc(cl.id)}</span><span class="grow">${esc(cl.title)}</span><span class="chev" aria-hidden="true">▾</span></button><span class="seg" role="group" aria-label="Évaluation ${esc(cl.id)}">${["C", "P", "NC", "NA"].map((k) => `<button type="button" class="g-${k} ${a.status === k ? "on" : ""}" data-s="${k}" aria-pressed="${a.status === k}" aria-label="${k} — ${GAPL[k]}" title="${GAPL[k]}">${k}</button>`).join("")}</span></div>
          <div class="body" hidden><p class="sub">${esc(cl.summary)}</p><b>Questions</b><ul>${cl.questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul><b>Preuves attendues</b><ul>${cl.evidence.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>
          <input class="obs" placeholder="Observation" aria-label="Observation ${esc(cl.id)}" value="${esc(a.note)}"></div></div>`;
      }).join("")}</section>`;
    let rd;
    const upd = (s) => {
      $("#sc").textContent = pct(s.score);
      $("#cnt").innerHTML = `${s.answered}/${s.total} évaluées<br>C ${s.counts.C} · P ${s.counts.P} · NC ${s.counts.NC} · NA ${s.counts.NA}`;
      if (rd) { rd.data.labels = Object.keys(s.by_chapter).map((k) => (k === "Annexe A" ? k : "Ch. " + k)); rd.data.datasets[0].data = Object.values(s.by_chapter); rd.update(); }
    };
    radar($("#rd"), g.score.by_chapter); rd = charts[charts.length - 1]; upd(g.score);
    const save = async (row) => {
      const on = $(".seg .on", row); if (!on) return;
      const s = await send(`/api/clients/${id}/gap/${encodeURIComponent(std)}`, { answers: { [row.dataset.c]: { status: on.dataset.s, note: $(".obs", row).value } } }, "PUT");
      upd(s); saved();
    };
    $$(".clause").forEach((row) => {
      $$(".seg button", row).forEach((b) => (b.onclick = (e) => { e.preventDefault(); $$(".seg button", row).forEach((x) => { x.classList.remove("on"); x.setAttribute("aria-pressed", "false"); }); b.classList.add("on"); b.setAttribute("aria-pressed", "true"); save(row); }));
      $(".obs", row).onchange = () => save(row);
    });
    $("#rep").onclick = (e) => busy(e.currentTarget, async () => { const d = await send(`/api/clients/${id}/gap/${encodeURIComponent(std)}/report`); nav("doc", d.id); });
  } else if (tab === "road") {
    const prog = { ...p.progress };
    el.innerHTML = `<section class="card"><h2>Feuille de route ${esc(std)}</h2><div class="row" style="margin-bottom:1rem"><div class="bar grow"><i id="pb"></i></div><b id="pv"></b></div>
      ${CAT.roadmap.map((ph) => `<div class="phase"><h3>${esc(ph.phase)}</h3>${ph.tasks.map((t) => { const k = `${ph.phase}|${t}`; return `<label class="check"><input type="checkbox" data-k="${esc(k)}" ${prog[k] ? "checked" : ""}><span>${esc(t)}</span></label>`; }).join("")}</div>`).join("")}
      <p><button class="btn alt" id="rdoc">Exporter la feuille de route</button></p></section>`;
    const n = CAT.roadmap.reduce((a, ph) => a + ph.tasks.length, 0);
    const bar = () => { const v = Math.round(100 * Object.values(prog).filter(Boolean).length / n); $("#pb").style.width = v + "%"; $("#pv").textContent = v + " %"; };
    bar();
    $$("input[data-k]").forEach((i) => (i.onchange = async () => { prog[i.dataset.k] = i.checked; bar(); await send(`/api/clients/${id}/projects/${encodeURIComponent(std)}/progress`, { progress: prog }, "PUT"); saved(); }));
    $("#rdoc").onclick = (e) => busy(e.currentTarget, async () => { const d = await send(`/api/clients/${id}/generate`, { kind: "roadmap", standard: std }); nav("doc", d.id); });
  } else {
    const gens = CAT.generators.filter((g) => !g.only || g.only.includes(std));
    el.innerHTML = `<section class="card"><h2>Livrables ${esc(std)}</h2><div class="grid">${gens.map((g) => `<button class="tile" data-k="${g.kind}">${esc(g.label)}<small>${g.only ? "Spécifique " + esc(g.only[0]) : "Adapté à " + esc(std)}</small></button>`).join("")}
      <button class="tile" id="ai" style="border:2px solid var(--pink)">✎ Rédiger un document avec l'IA<small>Procédure, instruction, manuel…</small></button></div>
      <p class="note">Chaque livrable est un projet à relire et valider par le consultant. Export Word disponible.</p></section>`;
    $$(".tile[data-k]").forEach((t) => (t.onclick = () => busy(t, async () => { const d = await send(`/api/clients/${id}/generate`, { kind: t.dataset.k, standard: std }); nav("doc", d.id); })));
    $("#ai").onclick = () => nav("writer", id, std);
  }
};

/* ---------------------------------------------------------- audits 3e partie */
ROUTES.audits = async () => {
  title("Audits tierce partie");
  const d = await get("/api/dashboard");
  const cl = await get("/api/clients");
  view.innerHTML = `<div class="row" style="margin-bottom:1rem">${cl.length ? `<select id="cl" style="max-width:320px">${cl.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select><button class="btn" id="na">+ Nouvel audit</button>` : `<p class="sub">Créez d'abord un client.</p>`}</div>
    <section class="card"><h2>Audits récents</h2>${d.recent_audits.length ? `<ul class="list">${d.recent_audits.map((a) => `<li data-a="${a.id}"><div><b>${esc(a.client)}</b> · ${esc(a.type)}<div>${a.standards.map(chip).join("")}</div></div><div class="sub" style="text-align:right">Avancement ${a.progress} %<br>${pct(a.conformity)} · ${esc(a.verdict)}</div></li>`).join("")}</ul>` : `<div class="empty">Aucun audit.</div>`}</section>`;
  $("#na")?.addEventListener("click", () => nav("auditForm", +$("#cl").value));
  $$("li[data-a]").forEach((l) => (l.onclick = () => nav("audit", +l.dataset.a)));
};

ROUTES.auditForm = async (cid) => {
  const c = await get(`/api/clients/${cid}`);
  title(`Nouvel audit — ${c.name}`);
  const pre = c.projects.map((p) => p.standard);
  view.innerHTML = `<section class="card"><form id="f">
    <label>Type d'audit</label><select name="type">${Object.entries(CAT.audit_types).map(([k, v]) => `<option value="${k}" ${k === "stage2" ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>
    <label>Référentiel(s) — plusieurs = audit intégré</label><div class="grid">${CAT.standards.map((s) => `<label class="check tile" style="margin:0"><input type="checkbox" name="std" value="${esc(s.code)}" ${pre.includes(s.code) ? "checked" : ""}><span>${chip(s.code)} ${esc(s.label)}</span></label>`).join("")}</div>
    <div class="row"><div class="grow"><label>Date</label><input type="date" name="date" value="${new Date().toISOString().slice(0, 10)}"></div><div class="grow"><label>Auditeur responsable</label><input name="lead" placeholder="Nom de l'auditeur"></div></div>
    <p><button class="btn">Créer l'audit</button></p></form></section>`;
  $("#f").onsubmit = async (e) => {
    e.preventDefault(); const fd = new FormData(e.target); const stds = fd.getAll("std");
    if (!stds.length) return toast("Choisissez au moins une norme");
    const a = await send(`/api/clients/${cid}/audits`, { type: fd.get("type"), standards: stds, date: fd.get("date"), lead_auditor: fd.get("lead") });
    stack.pop(); nav("audit", a.id);
  };
};

ROUTES.audit = async (aid, std) => {
  const a = await get(`/api/audits/${aid}`);
  std = std || a.standards[0];
  title(`Audit — ${a.client.name}`);
  const vclass = (v) => (v.startsWith("Certification recommandée sous") ? "v-warn" : v.startsWith("Certification recommandée") ? "v-ok" : v.startsWith("Certification non") ? "v-bad" : "v-none");
  view.innerHTML = `
  <div class="kpis">
    <div class="kpi"><b id="k-prog">${a.stats.progress} %</b><small>Avancement de l'audit</small></div>
    <div class="kpi"><b id="k-conf">${pct(a.stats.conformity)}</b><small>Taux de conformité</small></div>
    <div class="kpi"><b id="k-ncM" style="color:var(--bad2)">${a.stats.counts.NCM}</b><small>NC majeures</small></div>
    <div class="kpi"><b id="k-ncm" style="color:var(--bad)">${a.stats.counts.NCm}</b><small>NC mineures</small></div>
    <div class="kpi"><b id="k-oa" style="color:var(--warn)">${a.stats.counts.OA}</b><small>Opportunités d'amélioration</small></div>
  </div>
  <div class="cols">
    <section class="card"><h2>${esc(CAT.audit_types[a.type])}</h2><div>${a.standards.map(chip).join("")}</div><p class="sub">${esc(a.date)} · ${esc(a.lead_auditor || "Auditeur non renseigné")}</p>
      <div class="verdict ${vclass(a.stats.verdict)}" id="verdict">${esc(a.stats.verdict)}</div>
      <p class="row"><button class="btn alt" id="plan" data-busy="Préparation…">Plan d'audit</button><button class="btn" id="rep">Rapport d'audit</button><button class="btn sm danger" id="del">Supprimer</button></p></section>
    <section class="card"><h2>Répartition des constats</h2><div class="chartbox" style="height:220px"><canvas id="dn"></canvas></div></section>
    <section class="card"><h2>Conformité par chapitre</h2><div class="chartbox" style="height:220px"><canvas id="rd"></canvas></div></section>
  </div>
  ${a.standards.length > 1 ? `<div class="tabs">${a.standards.map((s) => `<button data-s="${esc(s)}" class="${s === std ? "on" : ""}">${esc(s)}</button>`).join("")}</div>` : ""}
  <section class="card"><h2>Grille d'audit ${esc(std)}</h2><p class="sub">PF point fort · C conforme · OA opportunité d'amélioration · NCm NC mineure · NCM NC majeure · NA non audité. Enregistrement automatique.</p>
  ${a.clauses[std].map((cl) => {
    const k = `${std}|${cl.id}`; const f = a.findings[k] || {};
    return `<div class="clause" data-k="${esc(k)}"><div class="head"><button type="button" class="tog" aria-expanded="false"><span class="cid">${esc(cl.id)}</span><span class="grow">${esc(cl.title)}</span><span class="chev" aria-hidden="true">▾</span></button><span class="seg" role="group" aria-label="Cotation ${esc(cl.id)}">${Object.keys(CAT.audit_grades).map((g) => `<button type="button" class="g-${g} ${f.grade === g ? "on" : ""}" data-g="${g}" aria-pressed="${f.grade === g}" aria-label="${g} — ${esc(CAT.audit_grades[g])}" title="${esc(CAT.audit_grades[g])}">${g}</button>`).join("")}</span></div>
      <div class="body" hidden><p class="sub">${esc(cl.summary)}</p><b>Questions de l'auditeur</b><ul>${cl.questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>
      <b>Preuves à échantillonner</b><ul>${cl.evidence.map((q) => `<li>${esc(q)}</li>`).join("")}<li>Enregistrements sur au moins 3 mois ; entretien pilote + opérateur ; cohérence document / terrain</li></ul>
      <label>Constat</label><textarea class="note-f" placeholder="Constat factuel, exigence concernée">${esc(f.note)}</textarea>
      <label>Preuve d'audit (référence, document, personne interrogée)</label><input class="ev-f" value="${esc(f.evidence)}"></div></div>`;
  }).join("")}</section>`;
  $$(".tabs button[data-s]").forEach((b) => (b.onclick = () => { stack[stack.length - 1][1] = [aid, b.dataset.s]; render(); }));
  const dnData = () => Object.keys(CAT.audit_grades).filter((g) => g !== "NA");
  chart($("#dn"), { type: "doughnut", data: { labels: dnData().map((g) => CAT.audit_grades[g]), datasets: [{ data: dnData().map((g) => a.stats.counts[g]), backgroundColor: dnData().map((g) => GRADE_COLOR[g]) }] }, options: { maintainAspectRatio: false, plugins: { legend: { position: "right", labels: { boxWidth: 12 } } } } });
  const dn = charts[charts.length - 1];
  radar($("#rd"), a.stats.by_chapter); const rd = charts[charts.length - 1];
  const upd = (s) => {
    $("#k-prog").textContent = s.progress + " %"; $("#k-conf").textContent = pct(s.conformity); $("#k-ncM").textContent = s.counts.NCM; $("#k-ncm").textContent = s.counts.NCm; $("#k-oa").textContent = s.counts.OA;
    const v = $("#verdict"); v.textContent = s.verdict; v.className = "verdict " + vclass(s.verdict);
    if (dn) { dn.data.datasets[0].data = dnData().map((g) => s.counts[g]); dn.update(); }
    if (rd) { rd.data.labels = Object.keys(s.by_chapter).map((k) => (k === "Annexe A" ? k : "Ch. " + k)); rd.data.datasets[0].data = Object.values(s.by_chapter); rd.update(); }
  };
  const save = async (row) => {
    const on = $(".seg .on", row);
    const s = await send(`/api/audits/${aid}/findings`, { findings: { [row.dataset.k]: { grade: on ? on.dataset.g : "", note: $(".note-f", row).value, evidence: $(".ev-f", row).value } } }, "PUT");
    upd(s); saved();
  };
  $$(".clause").forEach((row) => {
    $$(".seg button", row).forEach((b) => (b.onclick = (e) => { e.preventDefault(); const was = b.classList.contains("on"); $$(".seg button", row).forEach((x) => { x.classList.remove("on"); x.setAttribute("aria-pressed", "false"); }); if (!was) { b.classList.add("on"); b.setAttribute("aria-pressed", "true"); } if (["NCm", "NCM", "OA"].includes(b.dataset.g) && !was) toggleRow(row, true); save(row); }));
    $(".note-f", row).onchange = () => save(row); $(".ev-f", row).onchange = () => save(row);
  });
  $("#plan").onclick = (e) => busy(e.currentTarget, async () => { const d = await send(`/api/audits/${aid}/plan`); nav("doc", d.id); });
  $("#rep").onclick = (e) => busy(e.currentTarget, async () => { const d = await send(`/api/audits/${aid}/report`); nav("doc", d.id); });
  $("#del").onclick = async () => { if (!confirm("Supprimer cet audit ?")) return; await send(`/api/audits/${aid}`, undefined, "DELETE"); stack.pop(); render(); };
};

/* --------------------------------------------------------------- documents */
ROUTES.doc = async (did) => {
  const d = await get(`/api/documents/${did}`);
  title(d.title);
  const sec = (s, i) => `<section class="card"><h2>${esc(s.heading)}</h2>
    ${s.score !== undefined && s.score !== null ? `<div class="score">${s.score} %</div>` : ""}
    ${s.chart ? `<div class="chartbox" style="height:240px"><canvas id="ch${i}"></canvas></div>` : ""}
    ${(s.paragraphs || []).map((p) => `<p>${esc(p)}</p>`).join("")}
    ${s.bullets ? `<ul>${s.bullets.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>` : ""}
    ${s.table ? (s.table.rows.length ? `<div class="tbl"><table><thead><tr>${s.table.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${s.table.rows.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : `<p class="sub">Aucun élément.</p>`) : ""}</section>`;
  view.innerHTML = `<div class="row" style="margin-bottom:1rem"><button class="btn" id="dl">⬇ Télécharger (Word)</button><button class="btn alt" id="pr">Imprimer / PDF</button>
    <span class="sub">${esc(d.client)} · ${esc(d.date)} ${d.standard ? "· " + esc(d.standard) : ""} ${d.ai ? '· <span class="badge">rédigé avec l\'IA</span>' : ""}</span></div>
    <div class="doc">${d.sections.map(sec).join("")}</div><p class="note">${esc(d.footer)}</p>`;
  d.sections.forEach((s, i) => {
    if (!s.chart) return;
    if (s.chart.type === "radar") radar($("#ch" + i), s.chart.data);
    else chart($("#ch" + i), { type: "bar", data: { labels: Object.keys(s.chart.data), datasets: [{ data: Object.values(s.chart.data), backgroundColor: ["#2e8b57", "#5bb381", "#d08b00", "#c0392b", "#8e1b10"], borderRadius: 6 }] }, options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
  });
  $("#pr").onclick = () => window.print();
  $("#dl").onclick = async () => {
    const r = await api(`/api/documents/${did}/docx`); const url = URL.createObjectURL(await r.blob());
    const el = Object.assign(document.createElement("a"), { href: url, download: d.title.replace(/[^\w-]+/g, "_").slice(0, 80) + ".docx" });
    document.body.appendChild(el); el.click(); el.remove(); setTimeout(() => URL.revokeObjectURL(url), 1500);
  };
};

/* ------------------------------------------------------------ rédacteur IA */
ROUTES.writer = async (cid, std) => {
  title("Rédacteur IA");
  const cl = await get("/api/clients");
  const h = await get("/api/health");
  if (!cl.length) { view.innerHTML = `<div class="card empty">Créez d'abord un client.</div>`; return; }
  view.innerHTML = `${h.ai.provider === "none" ? `<div class="warnbox" style="margin-bottom:1rem">Aucun modèle d'IA connecté : Kapsi-Q produira un modèle structuré. Connectez Llama ou DeepSeek dans <button type="button" class="btn sm alt" id="gs">Ouvrir les Réglages</button> pour obtenir un texte rédigé.</div>` : ""}
    <section class="card"><form id="f">
    <div class="row"><div class="grow"><label>Client</label><select name="cid">${cl.map((c) => `<option value="${c.id}" ${c.id === cid ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>
    <div class="grow"><label>Norme</label><select name="std">${CAT.standards.map((s) => `<option ${s.code === std ? "selected" : ""}>${esc(s.code)}</option>`).join("")}</select></div>
    <div class="grow"><label>Type de document</label><select name="type">${CAT.doc_types.map((t) => `<option>${esc(t)}</option>`).join("")}</select></div></div>
    <label>Sujet *</label><input name="subject" required placeholder="ex. Gestion des réclamations clients, Évaluation des fournisseurs, Sauvegarde des données…">
    <label>Consignes au rédacteur (facultatif)</label><textarea name="ins" placeholder="ex. 2 pages max, inclure un logigramme textuel, vocabulaire simple pour les opérateurs"></textarea>
    <p><button class="btn" id="go">✎ Rédiger</button></p></form></section>`;
  $("#gs")?.addEventListener("click", (e) => { e.preventDefault(); nav("settings"); });
  $("#f").onsubmit = (e) => {
    e.preventDefault(); const fd = new FormData(e.target);
    busy($("#go"), async () => { const d = await send(`/api/clients/${fd.get("cid")}/write`, { standard: fd.get("std"), doc_type: fd.get("type"), subject: fd.get("subject"), instructions: fd.get("ins") }); nav("doc", d.id); });
  };
};

/* --------------------------------------------------------------- assistant */
ROUTES.assistant = async () => {
  title("Assistant ISO");
  view.innerHTML = `<section class="card chat"><div id="log"><p class="sub">Exemples : « Que demande ISO 14001 6.1.2 ? », « Différence entre NC mineure et majeure ? », « Qu'est-ce qui change en 2026 ? », « Quelles preuves pour la DdA 27001 ? »</p></div>
    <form id="f" class="row" style="margin-top:1rem"><select name="std" style="max-width:160px"><option value="">Toutes normes</option>${CAT.standards.map((s) => `<option>${esc(s.code)}</option>`).join("")}</select><input name="q" class="grow" placeholder="Votre question" required style="min-width:200px"><button class="btn">Envoyer</button></form></section>`;
  $("#f").onsubmit = async (e) => {
    e.preventDefault(); const q = e.target.q.value; const std = e.target.std.value || null; e.target.q.value = "";
    const log = $("#log"); log.insertAdjacentHTML("beforeend", `<div class="q">${esc(q)}</div><div class="a">…</div>`); const box = log.lastElementChild;
    try { const r = await send("/api/ask", { question: q, standard: std }); box.textContent = r.answer + (r.sources.length ? "\n\nRéférences : " + r.sources.join(" ; ") : ""); } catch { box.textContent = "Erreur."; }
  };
};

/* ----------------------------------------------------------------- réglages */
ROUTES.settings = async () => {
  title("Réglages");
  const s = await get("/api/settings/llm");
  const P = CAT.providers;
  view.innerHTML = `<section class="card"><h2>Moteur d'IA (génération de textes)</h2>
    <label>Fournisseur</label><select id="prov">${Object.entries(P).map(([k, v]) => `<option value="${k}" ${k === s.provider ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select>
    <div id="cloudw" class="warnbox hidden" style="margin-top:.7rem">API en ligne : les textes envoyés au modèle quittent le serveur du cabinet. Pour des données clients confidentielles, préférez Ollama en local.</div>
    <div class="row"><div class="grow"><label>Adresse (URL)</label><input id="url" value="${esc(s.url)}"></div><div class="grow"><label>Modèle</label><input id="model" value="${esc(s.model)}"></div></div>
    <label>Clé API ${s.has_key ? "(enregistrée — laisser vide pour la conserver)" : ""}</label><input id="key" type="password" autocomplete="off" placeholder="Groq / OpenRouter / DeepSeek">
    <label>Module Python Kapsi (fournisseur « kapsi »)</label><input id="mod" value="${esc(s.module)}" placeholder="ex. kapsi_model">
    <p class="row"><button class="btn" id="save">Enregistrer</button><button class="btn alt" id="test" data-busy="Test…">Tester la connexion</button></p><div id="res" class="sub"></div>
    <details style="margin-top:.8rem"><summary class="sub" style="cursor:pointer">Installer Llama / DeepSeek gratuitement en local (Ollama)</summary><ol class="sub">
      <li>Télécharger Ollama : ollama.com (Windows, macOS, Linux)</li><li>Dans un terminal : <code>ollama pull llama3.1:8b</code> ou <code>ollama pull deepseek-r1:8b</code></li>
      <li>Choisir « Ollama » ci-dessus, modèle <code>llama3.1:8b</code>, puis Tester</li></ol></details></section>
    <section class="card"><h2>Accès</h2><label>Jeton d'accès (si exigé par le serveur)</label><input id="tok" value="${esc(ls.get("kapsi_token"))}"><p><button class="btn alt" id="stok">Enregistrer le jeton</button></p></section>
    <section class="card"><h2>Installer sur iPhone / Android</h2><p class="sub">Safari : Partager → « Sur l'écran d'accueil ». Chrome : menu → « Installer l'application ».</p></section>`;
  const cloudCheck = () => $("#cloudw").classList.toggle("hidden", !P[$("#prov").value].cloud);
  cloudCheck();
  $("#prov").onchange = () => { const p = P[$("#prov").value]; $("#url").value = p.url; $("#model").value = p.model; cloudCheck(); };
  $("#save").onclick = async () => {
    const body = { provider: $("#prov").value, url: $("#url").value, model: $("#model").value, module: $("#mod").value };
    if ($("#key").value) body.api_key = $("#key").value;
    await send("/api/settings/llm", body, "PUT"); toast("Réglages enregistrés"); refreshStatus();
  };
  $("#test").onclick = (e) => busy(e.currentTarget, async () => { const r = await send("/api/settings/llm/test"); $("#res").textContent = (r.ok ? "✓ " : "✗ ") + r.message; });
  $("#stok").onclick = () => { ls.set("kapsi_token", $("#tok").value.trim()); toast("Jeton enregistré"); };
};

/* ------------------------------------------------- bouton revenir en haut */
const totop = $("#totop");
const onScroll = () => totop.classList.toggle("show", window.scrollY > 400);
window.addEventListener("scroll", onScroll, { passive: true });
totop.onclick = () => {
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: smooth ? "smooth" : "auto" });
  $("#title").focus({ preventScroll: true });
};

/* --------------------------------------------------------------------- init */
async function refreshStatus() {
  try {
    const h = await get("/api/health");
    $("#status").textContent = `v${h.version} · SmartCell Technologies`;
    const b = $("#aibadge"); const ai = h.ai;
    b.textContent = ai.provider === "none" ? "Hors ligne · générateurs" : `IA : ${ai.provider} · ${ai.model}`;
    b.className = "badge" + (ai.cloud ? " cloud" : "");
  } catch { $("#status").textContent = "Serveur injoignable"; }
}
(async () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  try { CAT = await get("/api/catalog"); } catch { view.innerHTML = `<div class="card empty">Serveur injoignable ou jeton requis.<br><br><input id="tok0" placeholder="Jeton"><button class="btn" id="t0" style="margin-top:.5rem">OK</button></div>`; $("#t0").onclick = () => { ls.set("kapsi_token", $("#tok0").value.trim()); location.reload(); }; return; }
  refreshStatus();
  nav("dashboard");
})();
