/* Kapsi Campus : gestion opérationnelle d'un établissement d'enseignement (ISO 21001). */
let CMETA = null;
const fmtD = (s) => (s ? s.slice(0, 16).replace(" ", " à ") : "—");
const kv = (v, lb) => (v === null || v === undefined ? "—" : lb ? `${v} j` : `${v} %`);
const okPill = (i) => i.ok === null ? `<span class="pill" style="background:#7a6a75">À mesurer</span>` : i.ok ? `<span class="pill" style="background:#1e7a4c">Atteint</span>` : `<span class="pill" style="background:#c92a45">Sous la cible</span>`;
const stPill = (s) => `<span class="pill" style="background:${{ Nouvelle: "#7b2ff7", Planifiée: "#5b3a8a", "En cours": "#b86e00", Réalisée: "#2a6fb0", Réceptionnée: "#1e7a4c", Refusée: "#7a6a75", Ouverte: "#c92a45", "En traitement": "#b86e00", Clôturée: "#1e7a4c", Enregistré: "#7b2ff7", Diffusé: "#2a6fb0", Traité: "#1e7a4c" }[s] || "#555"}">${esc(s)}</span>`;

ROUTES.campus = async (cid, tab = "pilotage") => {
  title("Campus");
  CMETA = CMETA || await get("/api/campus/meta");
  const cl = await get("/api/clients");
  if (!cl.length) { view.innerHTML = `<div class="card empty">Créez d'abord l'établissement dans Clients.</div>`; return; }
  cid = cid || +ls.get("kapsi_campus") || (cl.find((c) => /21001|ISI|Universit|Institut|École|Ecole/i.test(c.name)) || cl[0]).id;
  if (!cl.some((c) => c.id === cid)) cid = cl[0].id;
  ls.set("kapsi_campus", cid);
  const tabs = [["pilotage", "Pilotage"], ["demandes", "Demandes"], ["equipements", "Équipements"], ["plannings", "Plannings"], ["courrier", "Courrier et appels"],
    ["reclamations", "Réclamations"], ["processus", "Processus ISO 21001"], ["agents", "Agents"], ["guichet", "Guichet numérique"]];
  view.innerHTML = `<div class="card row" style="margin-bottom:.8rem"><label for="ccl" class="sub" style="margin:0">Établissement</label>
      <select id="ccl" class="grow" style="max-width:460px">${cl.map((c) => `<option value="${c.id}" ${c.id === cid ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
      <span class="sub">Kapsi Campus · ISO 21001</span></div>
    <div class="tabs">${tabs.map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "on" : ""}">${l}</button>`).join("")}</div><div id="ctab"></div>`;
  $("#ccl").onchange = () => { stack[stack.length - 1][1] = [+$("#ccl").value, tab]; render(); };
  $$(".tabs button").forEach((b) => (b.onclick = () => { stack[stack.length - 1][1] = [cid, b.dataset.t]; render(); }));
  await CTABS[tab]($("#ctab"), cid);
};

const CTABS = {};

CTABS.pilotage = async (el, cid) => {
  const s = await get(`/api/clients/${cid}/campus`);
  if (!s.open_requests && !s.assets && !s.by_month.length) {
    el.innerHTML = `<section class="card"><h2>Démarrer Kapsi Campus</h2><p>Aucune activité enregistrée pour cet établissement. Ouvrez le <b>guichet numérique</b> aux enseignants et au personnel, déclarez les équipements, ou chargez la démonstration.</p>
      <p class="row"><button class="btn" id="cdemo" data-busy="Chargement…">Charger la démonstration (7 mois d'activité simulée)</button><button class="btn alt" id="cgo">Ouvrir le guichet</button></p>
      <p class="sub">La démonstration reprend un parc type d'institut (laboratoires, copieurs, bâtiments, parc auto) ; toute l'activité est simulée. À remplacer par vos données réelles.</p></section>`;
    $("#cdemo").onclick = (e) => busy(e.currentTarget, async () => { await send(`/api/clients/${cid}/campus/demo`); toast("Démonstration chargée"); render(); });
    $("#cgo").onclick = () => { stack[stack.length - 1][1] = [cid, "guichet"]; render(); };
    return;
  }
  const bar = (i) => { const v = i.value ?? 0, t = i.target ?? 0, lb = i.lower_better; const w = lb ? Math.min(100, (t / Math.max(v, 0.1)) * 100) : Math.min(100, v);
    return `<div class="kbar"><div class="kl"><b>${esc(i.code)}</b> ${esc(i.name)}<div class="sub">${esc(i.detail)} · ${esc(i.freq)}</div></div>
      <div class="kt"><div class="kf ${i.ok === false ? "ko" : i.ok ? "ok" : ""}" style="width:${i.value === null ? 0 : w}%"></div>${lb ? "" : `<i style="left:${t}%"></i>`}</div>
      <div class="kv"><b>${kv(i.value, lb)}</b><small>cible ${kv(i.target, lb)}</small></div></div>`; };
  el.innerHTML = `<div class="kpis">
      <div class="kpi"><b>${s.open_requests}</b><small>Demandes en cours</small></div>
      <div class="kpi"><b style="color:${s.late_requests ? "#c92a45" : "inherit"}">${s.late_requests}</b><small>Demandes en retard</small></div>
      <div class="kpi"><b>${s.to_receive}</b><small>À faire réceptionner</small></div>
      <div class="kpi"><b>${s.open_complaints}</b><small>Réclamations ouvertes · ${s.late_complaints} en retard</small></div>
      <div class="kpi"><b>${s.tasks_today}</b><small>Tâches planifiées aujourd'hui · ${s.tasks_overdue} à rattraper</small></div>
      <div class="kpi"><b>${s.kpi_ok}/${s.kpi_ok + s.kpi_ko}</b><small>Indicateurs à la cible (${s.kpi_na} à mesurer)</small></div></div>
    <section class="card"><div class="row"><h2 class="grow" style="margin:0">Indicateurs du processus Services généraux (fiche GSG-PP)</h2><button class="btn" id="cpil">▶ Lancer le Pilote Campus</button></div>
      <p class="sub">Calculés automatiquement à partir des demandes, plannings, fiches de vie, réclamations et inventaires enregistrés · 6 derniers mois.</p>${s.indicators.map(bar).join("")}</section>
    <div class="cols"><section class="card"><h2>Demandes par mois</h2><div style="height:240px"><canvas id="cm"></canvas></div></section>
      <section class="card"><h2>Répartition des demandes (6 mois)</h2><div style="height:240px"><canvas id="ct"></canvas></div></section></div>`;
  chart($("#cm"), { type: "bar", data: { labels: s.by_month.map((m) => m.m), datasets: [{ label: "Reçues", data: s.by_month.map((m) => m.n), backgroundColor: "#7b2ff7" }, { label: "Réalisées", data: s.by_month.map((m) => m.d), backgroundColor: "#e8327f" }] }, options: { maintainAspectRatio: false } });
  chart($("#ct"), { type: "doughnut", data: { labels: s.by_type.map((t) => CMETA.types[t.type]?.label || t.type), datasets: [{ data: s.by_type.map((t) => t.n), backgroundColor: ["#e8327f", "#7b2ff7", "#ff8fc8", "#5b3a8a", "#ffb347", "#2a6fb0", "#1e7a4c", "#c92a45", "#9a8496", "#b86e00", "#3ab0a0"] }] }, options: { maintainAspectRatio: false, plugins: { legend: { position: "right" } } } });
  $("#cpil").onclick = async () => { const r = await send(`/api/clients/${cid}/agents/campus_pilote`, { standard: "ISO 21001" }); nav("run", r.run_id); };
};

CTABS.demandes = async (el, cid, ftype = "") => {
  const all = await get(`/api/clients/${cid}/campus/requests${ftype ? "?type=" + ftype : ""}`);
  const cols = ["Nouvelle", "Planifiée", "En cours", "Réalisée"];
  const card = (q) => `<div class="kcard ${q.late ? "late" : ""}" data-q="${q.id}" tabindex="0" role="button"><div class="row" style="gap:.3rem"><b class="grow">${esc(q.type_label)}</b>${q.priority === "Urgente" ? `<span class="pill" style="background:#c92a45">Urgente</span>` : ""}</div>
      <div>${esc(q.title)}${q.qty > 1 ? ` · ${q.qty}` : ""}</div><div class="sub">${esc(q.dept || q.requester)} · ${esc(q.ticket)}</div>
      <div class="sub">${q.late ? "⚠ En retard · " : ""}Échéance ${fmtD(q.needed_by)}${q.assignee ? " · " + esc(q.assignee) : ""}</div></div>`;
  el.innerHTML = `<section class="card"><div class="row"><select id="cft" style="max-width:260px"><option value="">Tous les types</option>${Object.entries(CMETA.types).map(([k, t]) => `<option value="${k}" ${k === ftype ? "selected" : ""}>${esc(t.label)}</option>`).join("")}</select>
      <span class="grow sub">${all.filter((q) => cols.includes(q.status)).length} demande(s) ouvertes · ${all.filter((q) => q.late && cols.slice(0, 3).includes(q.status)).length} en retard</span><button class="btn" id="cnew">+ Nouvelle demande</button></div><div id="cform"></div></section>
    <div class="kanban">${cols.map((c) => { const L = all.filter((q) => q.status === c); return `<section class="kcol"><h3>${c} <span class="sub">${L.length}</span></h3>${L.slice(0, 40).map(card).join("") || `<p class="sub">Aucune.</p>`}${L.length > 40 ? `<p class="sub">+ ${L.length - 40} autres</p>` : ""}</section>`; }).join("")}</div>
    <section class="card"><h2>Dernières demandes réceptionnées</h2><div class="tbl"><table><thead><tr><th>Ticket</th><th>Demande</th><th>Demandeur</th><th>Échéance</th><th>Réalisée</th><th>Avis</th></tr></thead><tbody>
      ${all.filter((q) => q.status === "Réceptionnée").slice(0, 25).map((q) => `<tr><td>${esc(q.ticket)}</td><td>${esc(q.type_label)} · ${esc(q.title)}</td><td>${esc(q.dept || q.requester)}</td><td>${fmtD(q.needed_by)}</td><td>${fmtD(q.done_at)}${q.late ? ' <span class="pill" style="background:#c92a45">hors délai</span>' : ""}</td><td>${q.satisfied ? "Satisfait" : "Non satisfait"}</td></tr>`).join("")}</tbody></table></div></section>`;
  $("#cft").onchange = () => CTABS.demandes(el, cid, $("#cft").value);
  const open = (id) => { const q = all.find((x) => x.id === id); const box = $("#cform");
    box.innerHTML = `<div class="tdet2"><div class="grow"><b>${esc(q.ticket)} · ${esc(q.type_label)}</b> (${esc(q.form)}) ${stPill(q.status)}<div>${esc(q.title)}</div>
      <div class="sub">${esc(q.requester)} · ${esc(q.dept)} · déposée le ${fmtD(q.created_at)} · échéance ${fmtD(q.needed_by)}</div>${Object.keys(q.details || {}).length ? `<div class="sub">${Object.entries(q.details).map(([k, v]) => `${esc(k)} : ${esc(v)}`).join(" · ")}</div>` : ""}</div>
      <div class="row">${["Planifiée", "En cours", "Réalisée", "Refusée"].filter((s) => s !== q.status).map((s) => `<button class="btn sm ${s === "Refusée" ? "danger" : s === "Réalisée" ? "" : "alt"}" data-s="${s}">${s === "Réalisée" ? "✓ Réalisée" : s}</button>`).join("")}</div></div>`;
    $$("[data-s]", box).forEach((b) => (b.onclick = async () => { await send(`/api/campus/requests/${id}`, { status: b.dataset.s }, "PUT"); toast("Demande mise à jour"); CTABS.demandes(el, cid, ftype); }));
    box.scrollIntoView({ block: "nearest" }); };
  $$("[data-q]", el).forEach((c) => { c.onclick = () => open(+c.dataset.q); c.onkeydown = (e) => { if (e.key === "Enter") open(+c.dataset.q); }; });
  $("#cnew").onclick = () => { $("#cform").innerHTML = `<div class="row" style="margin-top:.8rem"><select id="nt" style="max-width:240px">${Object.entries(CMETA.types).map(([k, t]) => `<option value="${k}">${esc(t.label)}</option>`).join("")}</select>
      <input id="nr" placeholder="Demandeur" style="max-width:180px"><input id="nd" placeholder="Département ou service" style="max-width:220px"><input id="no" class="grow" placeholder="Objet"><input id="nq" type="number" min="1" value="1" style="max-width:90px" aria-label="Quantité"><button class="btn" id="nok">Enregistrer</button></div>`;
    $("#nok").onclick = async () => { if (!$("#no").value.trim()) return toast("Indiquez l'objet"); const r = await send(`/api/clients/${cid}/campus/requests`, { type: $("#nt").value, requester: $("#nr").value, dept: $("#nd").value, title: $("#no").value, qty: +$("#nq").value || 1 }); toast(`Ticket ${r.ticket} · échéance ${fmtD(r.needed_by)}`); CTABS.demandes(el, cid, ftype); }; };
};

CTABS.equipements = async (el, cid) => {
  const as = await get(`/api/clients/${cid}/campus/assets`);
  const by = Object.keys(CMETA.categories).map((k) => [k, as.filter((a) => a.category === k)]);
  el.innerHTML = by.map(([k, L]) => `<section class="card"><h2>${esc(CMETA.categories[k].label)} <span class="sub">fiche de vie ${esc(CMETA.categories[k].form)} · ${L.reduce((a, b) => a + b.qty, 0)} unité(s)</span></h2>
      ${L.length ? `<div class="tbl"><table><thead><tr><th>Code</th><th>Lieu</th><th>Équipement</th><th>Qté</th><th>État</th><th>Pannes 12 mois</th><th>Préventives</th><th>Arrêt (h)</th></tr></thead><tbody>
      ${L.map((a) => `<tr data-as="${a.id}" class="clickable" tabindex="0"><td>${esc(a.code)}</td><td>${esc(a.location)}</td><td>${esc(a.label)}</td><td>${a.qty}</td><td>${a.state === "En service" ? esc(a.state) : `<span class="pill" style="background:#c92a45">${esc(a.state)}</span>`}</td>
        <td>${a.curatives_12m >= 3 ? `<b style="color:#c92a45">${a.curatives_12m}</b>` : a.curatives_12m}</td><td>${a.preventives_12m}</td><td>${Math.round(a.downtime_12m)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="sub">Aucun équipement déclaré.</p>`}</section>`).join("") +
    `<section class="card"><h2>Déclarer un équipement</h2><div class="row"><select id="ac" style="max-width:220px">${Object.entries(CMETA.categories).map(([k, c]) => `<option value="${k}">${esc(c.label)}</option>`).join("")}</select>
      <input id="acode" placeholder="Code" style="max-width:120px"><input id="aloc" placeholder="Lieu (ex. Laboratoire A 104)" style="max-width:220px"><input id="alab" class="grow" placeholder="Désignation (marque, modèle)"><input id="aq" type="number" min="1" value="1" style="max-width:80px" aria-label="Quantité"><button class="btn" id="aadd">Ajouter</button></div></section><div id="alife"></div>`;
  $("#aadd").onclick = async () => { if (!$("#alab").value.trim()) return; await send(`/api/clients/${cid}/campus/assets`, { category: $("#ac").value, code: $("#acode").value, location: $("#aloc").value, label: $("#alab").value, qty: +$("#aq").value || 1 }); CTABS.equipements(el, cid); };
  $$("[data-as]", el).forEach((r) => (r.onclick = async () => {
    const a = await get(`/api/campus/assets/${r.dataset.as}`);
    $("#alife").innerHTML = `<section class="card"><h2>Fiche de vie · ${esc(a.label)} (${esc(a.location)})</h2>
      <div class="tbl"><table><thead><tr><th>Date</th><th>Type</th><th>Nature</th><th>Intervenant</th><th>Description</th><th>Coût</th><th>Arrêt (h)</th><th>Efficace</th></tr></thead><tbody>
      ${a.interventions.map((i) => `<tr><td>${esc(i.date)}</td><td>${i.kind === "P" ? "Préventive" : "Curative"}</td><td>${{ R: "Réparation", C: "Changement de pièce", E: "Entretien", G: "Réglage" }[i.nature] || esc(i.nature)}</td><td>${i.intervenant === "E" ? "Externe" : "Interne"}</td><td>${esc(i.description)}</td><td>${i.cost || ""}</td><td>${i.downtime || ""}</td><td>${i.kind === "C" ? (i.effective ? "Oui" : "Non") : ""}</td></tr>`).join("") || `<tr><td colspan="8">Aucune intervention.</td></tr>`}</tbody></table></div>
      <div class="row" style="margin-top:.6rem"><select id="ik" style="max-width:140px"><option value="C">Curative</option><option value="P">Préventive</option></select><select id="in" style="max-width:180px"><option value="R">Réparation</option><option value="C">Changement de pièce</option><option value="E">Entretien</option><option value="G">Réglage</option></select>
        <input id="idesc" class="grow" placeholder="Description de l'intervention"><input id="icost" type="number" placeholder="Coût TND" style="max-width:110px"><label class="check" style="margin:0"><input type="checkbox" id="ieff" checked> efficace</label><button class="btn" id="iadd">Enregistrer</button></div></section>`;
    $("#iadd").onclick = async () => { await send(`/api/campus/assets/${a.id}/interventions`, { kind: $("#ik").value, nature: $("#in").value, description: $("#idesc").value, cost: +$("#icost").value || 0, effective: $("#ieff").checked }); toast("Intervention enregistrée"); r.click(); };
    $("#alife").scrollIntoView({ block: "start", behavior: "smooth" });
  }));
};

CTABS.plannings = async (el, cid, plan = "nettoyage") => {
  const today = new Date().toISOString().slice(0, 10), add = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
  const ts = await get(`/api/clients/${cid}/campus/tasks?plan=${plan}&start=${add(-14)}&end=${add(14)}`);
  const days = [...new Set(ts.map((t) => t.date))];
  const late = ts.filter((t) => t.date < today && !t.done);
  el.innerHTML = `<section class="card"><div class="row"><select id="cpl" style="max-width:420px">${Object.entries(CMETA.plans).map(([k, p]) => `<option value="${k}" ${k === plan ? "selected" : ""}>${esc(p.label)} (${esc(p.form)})</option>`).join("")}</select>
      <span class="grow sub">${ts.filter((t) => t.date <= today).length ? Math.round(100 * ts.filter((t) => t.date <= today && t.done).length / ts.filter((t) => t.date <= today).length) : "—"} % réalisé sur les 14 derniers jours · ${late.length} tâche(s) à rattraper</span></div></section>
    <div class="days">${days.map((d) => `<section class="card day ${d === today ? "today" : ""}"><h3>${new Date(d + "T00:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "short" })}</h3>
      ${ts.filter((t) => t.date === d).map((t) => `<label class="check task ${t.date < today && !t.done ? "late" : ""}"><input type="checkbox" data-tk="${t.id}" ${t.done ? "checked" : ""}> <span>${esc(t.label)}${t.location && !t.label.includes(t.location) ? ` · <span class="sub">${esc(t.location)}</span>` : ""}</span></label>`).join("")}</section>`).join("") || `<div class="card empty">Aucune tâche sur cette période. Lancez l'agent Planificateur de maintenance pour les plannings préventifs.</div>`}</div>`;
  $("#cpl").onchange = () => CTABS.plannings(el, cid, $("#cpl").value);
  $$("[data-tk]", el).forEach((c) => (c.onchange = async () => { await send(`/api/campus/tasks/${c.dataset.tk}`, { done: c.checked }, "PUT"); saved(); }));
};

CTABS.courrier = async (el, cid, dir = "entrant") => {
  const [ml, calls] = await Promise.all([get(`/api/clients/${cid}/campus/mail`), get(`/api/clients/${cid}/campus/calls`)]);
  const L = ml.filter((m) => m.direction === dir);
  el.innerHTML = `<section class="card"><div class="row">${[["entrant", "Courrier entrant (GSG-RG-01)"], ["sortant", "Courrier sortant (GSG-RG-02)"], ["interne", "Courrier interne (GSG-RG-03)"]].map(([k, l]) => `<button class="btn sm ${k === dir ? "" : "alt"}" data-dir="${k}">${l}</button>`).join("")}</div>
      <div class="row" style="margin-top:.7rem"><input id="mc" placeholder="Correspondant" style="max-width:220px"><input id="ms" class="grow" placeholder="Objet"><input id="msv" placeholder="Service destinataire" style="max-width:200px"><button class="btn" id="madd">Enregistrer</button></div>
      <div class="tbl" style="margin-top:.7rem"><table><thead><tr><th>N°</th><th>Date</th><th>Correspondant</th><th>Objet</th><th>Service</th><th>Statut</th></tr></thead><tbody>
      ${L.slice(0, 60).map((m) => `<tr><td>${esc(m.number)}</td><td>${esc(m.date)}</td><td>${esc(m.correspondent)}</td><td>${esc(m.subject)}</td><td>${esc(m.service)}</td><td><select data-m="${m.id}">${["Enregistré", "Diffusé", "Traité"].map((s) => `<option ${s === m.status ? "selected" : ""}>${s}</option>`).join("")}</select></td></tr>`).join("") || `<tr><td colspan="6">Aucun courrier.</td></tr>`}</tbody></table></div></section>
    <section class="card"><h2>Appels téléphoniques (GSG-RG-04)</h2><div class="row"><input id="cc" placeholder="Appelant" style="max-width:200px"><input id="cs" class="grow" placeholder="Objet"><input id="cr" placeholder="Orienté vers" style="max-width:180px"><button class="btn" id="cadd">Enregistrer</button></div>
      <div class="tbl" style="margin-top:.6rem"><table><thead><tr><th>Date</th><th>Appelant</th><th>Objet</th><th>Orienté vers</th></tr></thead><tbody>${calls.slice(0, 20).map((c) => `<tr><td>${fmtD(c.date)}</td><td>${esc(c.caller)}</td><td>${esc(c.subject)}</td><td>${esc(c.routed_to)}</td></tr>`).join("")}</tbody></table></div></section>`;
  $$("[data-dir]", el).forEach((b) => (b.onclick = () => CTABS.courrier(el, cid, b.dataset.dir)));
  $$("[data-m]", el).forEach((s) => (s.onchange = async () => { await send(`/api/campus/mail/${s.dataset.m}`, { status: s.value }, "PUT"); saved(); }));
  $("#madd").onclick = async () => { if (!$("#ms").value.trim()) return; await send(`/api/clients/${cid}/campus/mail`, { direction: dir, correspondent: $("#mc").value, subject: $("#ms").value, service: $("#msv").value }); CTABS.courrier(el, cid, dir); };
  $("#cadd").onclick = async () => { if (!$("#cs").value.trim()) return; await send(`/api/clients/${cid}/campus/calls`, { caller: $("#cc").value, subject: $("#cs").value, routed_to: $("#cr").value }); CTABS.courrier(el, cid, dir); };
};

CTABS.reclamations = async (el, cid) => {
  const L = await get(`/api/clients/${cid}/campus/complaints`);
  el.innerHTML = `<section class="card"><h2>Registre des réclamations et suggestions · ${L.filter((c) => c.status !== "Clôturée").length} ouverte(s) · ${L.filter((c) => c.late).length} en retard</h2>
    <p class="sub">Délai de réponse : 7 jours. Les réclamations arrivent du guichet numérique, de la boîte à réclamations ou par mail ; le service est proposé automatiquement.</p>
    <div class="row"><select id="rs" style="max-width:160px"><option>Apprenant</option><option>Enseignant</option><option>Personnel</option><option>Parent</option><option>Visiteur</option></select><input id="rt" class="grow" placeholder="Objet de la réclamation"><button class="btn" id="radd2">Enregistrer</button></div>
    <div class="tbl" style="margin-top:.7rem"><table><thead><tr><th>N°</th><th>Date</th><th>Émetteur</th><th>Service</th><th>Objet</th><th>Échéance</th><th>Réponse</th><th>Statut</th></tr></thead><tbody>
    ${L.slice(0, 80).map((c) => `<tr data-k="${c.id}"><td>${esc(c.ticket || c.id)}</td><td>${esc(c.date.slice(0, 10))}</td><td>${esc(c.source)}<div class="sub">${esc(c.channel)}</div></td><td>${esc(c.service)}</td><td>${esc(c.subject)}</td>
      <td>${c.late ? `<b style="color:#c92a45">${esc(c.due)}</b>` : esc(c.due)}</td><td><input data-f="response" value="${esc(c.response || "")}" placeholder="Réponse apportée"></td>
      <td><select data-f="status">${["Ouverte", "En traitement", "Clôturée"].map((s) => `<option ${s === c.status ? "selected" : ""}>${s}</option>`).join("")}</select></td></tr>`).join("")}</tbody></table></div></section>`;
  $$("tr[data-k] [data-f]", el).forEach((f) => (f.onchange = async () => { await send(`/api/campus/complaints/${f.closest("tr").dataset.k}`, { [f.dataset.f]: f.value }, "PUT"); saved(); }));
  $("#radd2").onclick = async () => { if ($("#rt").value.trim().length < 5) return; const c = await send(`/api/clients/${cid}/campus/complaints`, { subject: $("#rt").value, source: $("#rs").value, channel: "Saisie" }); toast(`Affectée à : ${c.service}`); CTABS.reclamations(el, cid); };
};

CTABS.processus = async (el, cid) => {
  const ps = await get(`/api/clients/${cid}/campus/processes`);
  const lane = (k) => `<div class="lane"><h3>${k === "Management" ? "Processus de management" : k === "Réalisation" ? "Processus de réalisation (apprenants)" : "Processus support"}</h3><div class="pgrid">${ps.filter((p) => p.kind === k).map((p) =>
    `<div class="proc ${p.mode}"><b>${esc(p.code)}</b><div>${esc(p.name)}</div><div class="sub">Pilote : ${esc(p.pilot)} · ISO 21001 § ${esc(p.clauses)}</div>
      <div class="row" style="gap:.3rem;margin-top:.3rem">${p.mode === "auto" || p.mode === "qualite" ? `<span class="pill" style="background:#7b2ff7">Mesure automatique</span>` : `<span class="pill" style="background:#5b3a8a">Saisie du pilote</span>`}${p.ok ? `<span class="pill" style="background:#1e7a4c">${p.ok} atteint(s)</span>` : ""}${p.ko ? `<span class="pill" style="background:#c92a45">${p.ko} sous la cible</span>` : ""}</div></div>`).join("")}</div></div>`;
  const all = ps.flatMap((p) => p.indicators);
  el.innerHTML = `<section class="card"><h2>Cartographie des processus</h2><p class="sub">Codes repris de la fiche GSG-PP de l'ISI quand ils y figurent. Les indicateurs des processus autres que GSG sont proposés et doivent être validés par leurs pilotes.</p>
      <div class="lanes"><div class="pi">Exigences et attentes des apprenants et parties intéressées</div><div>${["Management", "Réalisation", "Support"].map(lane).join("")}</div><div class="pi">Satisfaction des apprenants et parties intéressées</div></div></section>
    <section class="card"><h2>Tableau de bord de tous les processus</h2><div class="tbl"><table><thead><tr><th>Processus</th><th>Indicateur</th><th>Formule</th><th>Fréquence</th><th>Valeur</th><th>Cible</th><th>Statut</th></tr></thead><tbody>
    ${all.map((i) => `<tr><td>${esc(i.process)}</td><td><b>${esc(i.code)}</b> ${esc(i.name)}<div class="sub">${esc(i.detail)}</div></td><td class="sub">${esc(i.formula)}</td><td>${esc(i.freq)}</td>
      <td>${i.mode === "Saisie" ? `<input type="number" step="0.1" data-v="${i.code}" value="${i.value ?? ""}" style="max-width:90px" aria-label="Valeur ${esc(i.code)}">` : kv(i.value, i.lower_better)}</td>
      <td><input type="number" step="0.1" data-t="${i.code}" value="${i.target ?? ""}" style="max-width:80px" aria-label="Cible ${esc(i.code)}"></td><td>${okPill(i)}</td></tr>`).join("")}</tbody></table></div></section>`;
  $$("[data-v]", el).forEach((f) => (f.onchange = async () => { await send(`/api/clients/${cid}/campus/indicators/${f.dataset.v}`, { value: +f.value, period: "courante" }, "PUT"); saved(); }));
  $$("[data-t]", el).forEach((f) => (f.onchange = async () => { await send(`/api/clients/${cid}/campus/indicators/${f.dataset.t}`, { target: +f.value }, "PUT"); saved(); }));
};

CTABS.agents = async (el, cid) => {
  const [ag, runs] = await Promise.all([get("/api/agents?campus_only=true"), get(`/api/clients/${cid}/runs`)]);
  const cr = runs.filter((r) => r.agent.startsWith("campus_"));
  el.innerHTML = `<section class="card"><h2>Agents Kapsi Campus</h2><p class="sub">Ils travaillent sur les registres de l'établissement. Leurs documents sont produits au statut « À valider » ; ils ne modifient jamais une demande réceptionnée ni une donnée saisie par une personne.</p>
      <div class="grid">${ag.map((a) => `<div class="tile agent ${a.key === "campus_pilote" ? "lead" : ""}"><b>${esc(a.name)}</b><small>${esc(a.desc)}</small><button class="btn sm" data-run="${a.key}" style="margin-top:.6rem">Lancer</button></div>`).join("")}</div></section>
    <section class="card"><h2>Exécutions</h2>${cr.length ? `<ul class="list">${cr.map((r) => `<li data-run-id="${r.id}"><div><b>${esc(r.agent_name)}</b><div class="sub">${esc(r.created_at)}</div></div>${runPill(r.status)}</li>`).join("")}</ul>` : `<p class="sub">Aucune exécution.</p>`}</section>
    <section class="card"><h2>Agents qualité ISO 21001</h2><p class="sub">Pour le système de management complet (documentation, formation, audit interne, actions, préparation à la certification), utilisez le menu Agents avec la norme ISO 21001.</p><button class="btn alt" id="toq">Ouvrir l'arbre des agents</button></section>`;
  $$("[data-run]", el).forEach((b) => (b.onclick = async () => { const r = await send(`/api/clients/${cid}/agents/${b.dataset.run}`, { standard: "ISO 21001" }); nav("run", r.run_id); }));
  $$("[data-run-id]", el).forEach((l) => (l.onclick = () => nav("run", +l.dataset.runId)));
  $("#toq").onclick = () => { stack.length = 0; nav("agents"); };
};

CTABS.guichet = async (el, cid) => {
  const [{ code }, net] = await Promise.all([get(`/api/clients/${cid}/campus/guichet`), get("/api/network").catch(() => ({ urls: [location.origin] }))]);
  const base = (net.urls && net.urls[0]) || location.origin;
  const url = `${base}/guichet?e=${cid}&code=${code}`;
  el.innerHTML = `<section class="card"><div class="cols"><div><h2>Guichet numérique</h2>
      <p>Enseignants, personnel et apprenants déposent leurs demandes (tirage, intervention, véhicule, salle, vidéoprojecteur, fournitures, clé) et leurs réclamations depuis leur téléphone, suivent leur ticket et confirment la réception.</p>
      <p>Chaque dépôt alimente directement les registres et les indicateurs ISO 21001 : plus de formulaire papier à ressaisir.</p>
      <p class="sub">Code d'accès de l'établissement : <b style="font-size:1.3rem;letter-spacing:.1em">${esc(code)}</b> · à afficher dans les salles avec le QR code.</p>
      <p class="row"><a class="btn" href="${esc(url)}" target="_blank" rel="noopener">Ouvrir le guichet</a><button class="btn alt" id="gcopy">Copier le lien</button><button class="btn alt" id="gnew">Changer le code</button></p>
      <p class="sub"><code>${esc(url)}</code></p></div>
      <div style="text-align:center"><div id="gqr" style="max-width:260px;margin:0 auto;background:#fff;padding:12px;border-radius:12px"></div><p class="sub">Affiche à imprimer : QR code + code d'accès</p></div></div></section>`;
  if (window.qrcode) { const q = qrcode(0, "M"); q.addData(url); q.make(); $("#gqr").innerHTML = q.createSvgTag({ cellSize: 6, margin: 2, scalable: true }); }
  $("#gcopy").onclick = async () => { try { await navigator.clipboard.writeText(url); toast("Lien copié"); } catch { toast(url); } };
  $("#gnew").onclick = async () => { if (!confirm("Changer le code ? L'ancien QR code ne fonctionnera plus.")) return; await get(`/api/clients/${cid}/campus/guichet?renew=true`); CTABS.guichet(el, cid); };
};
