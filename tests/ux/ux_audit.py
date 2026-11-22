"""Audit UI/UX automatisé de Kapsi-Q (Playwright + axe-core).
Usage : python ux_audit.py <label> [base_url]"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
AXE = Path(__import__("os").environ.get("AXE_JS", "node_modules/axe-core/axe.min.js")).read_text()
OUT = Path(f"ux-results/{LABEL}"); OUT.mkdir(parents=True, exist_ok=True)
VIEWPORTS = {"mobile": (375, 812), "tablet": (768, 1024), "desktop": (1366, 900)}

# écrans : (nom, actions pour y arriver depuis l'accueil)
SCREENS = [
    ("dashboard", []),
    ("clients", [("click", ".side a[data-r=clients]")]),
    ("client", [("click", ".side a[data-r=clients]"), ("click", "li[data-id] >> nth=0")]),
    ("client_form", [("click", ".side a[data-r=clients]"), ("click", "#new")]),
    ("project_gap", [("click", ".side a[data-r=clients]"), ("click", "li[data-id] >> nth=0"), ("click", "[data-open] >> nth=0")]),
    ("project_road", [("click", ".side a[data-r=clients]"), ("click", "li[data-id] >> nth=0"), ("click", "[data-open] >> nth=0"), ("click", ".tabs button[data-t=road]")]),
    ("project_gen", [("click", ".side a[data-r=clients]"), ("click", "li[data-id] >> nth=0"), ("click", "[data-open] >> nth=0"), ("click", ".tabs button[data-t=gen]")]),
    ("audits", [("click", ".side a[data-r=audits]")]),
    ("audit", [("click", ".side a[data-r=audits]"), ("click", "li[data-a] >> nth=0")]),
    ("audit_form", [("click", ".side a[data-r=audits]"), ("click", "#na")]),
    ("doc_report", [("click", ".side a[data-r=audits]"), ("click", "li[data-a] >> nth=0"), ("click", "#rep")]),
    ("writer", [("click", ".side a[data-r=writer]")]),
    ("assistant", [("click", ".side a[data-r=assistant]")]),
    ("settings", [("click", ".side a[data-r=settings]")]),
]

SMALL_TARGETS = """() => [...document.querySelectorAll('a,button,input,select,textarea,summary,[role=button]')]
  .filter(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
     return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && e.type !== 'hidden' && (r.height < 32 || r.width < 32) && !(e.type==='checkbox' && e.closest('label')); })
  .map(e => (e.tagName + (e.id ? '#' + e.id : '') + (e.className && typeof e.className==='string' ? '.' + e.className.split(' ')[0] : '') + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height) + ' «' + (e.innerText||e.value||e.placeholder||'').trim().slice(0,20) + '»'))"""

res = {"label": LABEL, "screens": {}, "keyboard": {}, "perf": {}}
with sync_playwright() as p:
    b = p.chromium.launch()
    for vp, (w, h) in VIEWPORTS.items():
        for name, acts in SCREENS:
            pg = b.new_page(viewport={"width": w, "height": h})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
            t0 = time.time(); pg.goto(BASE); pg.wait_for_selector(".kpis", timeout=8000); load = time.time() - t0
            ok = True
            for kind, sel in acts:
                try:
                    pg.click(sel, timeout=4000); pg.wait_for_timeout(700)
                except Exception as e:
                    ok = False; errs.append(f"action impossible: {sel} ({type(e).__name__})"); break
            pg.wait_for_timeout(500)
            pg.add_script_tag(content=AXE)
            axe = pg.evaluate("async () => (await axe.run(document, {resultTypes:['violations']})).violations.map(v => ({id:v.id, impact:v.impact, help:v.help, n:v.nodes.length, ex:v.nodes.slice(0,3).map(n=>n.target.join(' '))}))")
            overflow = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            small = pg.evaluate(SMALL_TARGETS) if vp == "mobile" else []
            pg.screenshot(path=str(OUT / f"{vp}_{name}.png"))
            res["screens"][f"{vp}/{name}"] = {"ok": ok, "errors": errs, "axe": axe, "h_overflow_px": overflow, "small_targets": small[:15], "n_small": len(small), "load_s": round(load, 2)}
            pg.close()
    # clavier : la navigation principale doit être atteignable à la touche Tab
    pg = b.new_page(viewport={"width": 1366, "height": 900}); pg.goto(BASE); pg.wait_for_selector(".kpis")
    seen = []
    for _ in range(25):
        pg.keyboard.press("Tab")
        seen.append(pg.evaluate("() => { const e = document.activeElement; return e.tagName + ':' + (e.dataset.r || e.innerText || e.id || '').trim().slice(0,25); }"))
    res["keyboard"]["tab_sequence"] = seen
    res["keyboard"]["nav_reachable"] = any("clients" in s.lower() for s in seen)
    vis = pg.evaluate("() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.boxShadow; }")
    res["keyboard"]["focus_style"] = vis
    # performance
    pg2 = b.new_page(); t0 = time.time(); pg2.goto(BASE); pg2.wait_for_selector(".kpis"); res["perf"]["first_dashboard_s"] = round(time.time() - t0, 2)
    res["perf"]["resources_kb"] = round(pg2.evaluate("() => performance.getEntriesByType('resource').reduce((a,r)=>a+(r.transferSize||r.encodedBodySize||0),0)") / 1024)
    b.close()

Path(OUT / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
# synthèse
agg = {}
for k, v in res["screens"].items():
    for a in v["axe"]:
        d = agg.setdefault(a["id"], {"impact": a["impact"], "help": a["help"], "screens": set(), "ex": a["ex"]})
        d["screens"].add(k)
print("=== AXE ===")
for k, d in sorted(agg.items(), key=lambda x: ["critical", "serious", "moderate", "minor"].index(x[1]["impact"] or "minor")):
    print(f"[{d['impact']}] {k}: {d['help']} — {len(d['screens'])} écrans — ex {d['ex'][:2]}")
print("=== ERREURS / ÉCHECS ===")
for k, v in res["screens"].items():
    if v["errors"] or not v["ok"]:
        print(k, v["errors"][:3])
print("=== DÉBORDEMENT HORIZONTAL ===", {k: v["h_overflow_px"] for k, v in res["screens"].items() if v["h_overflow_px"] > 0})
print("=== PETITES CIBLES (mobile) ===")
for k, v in res["screens"].items():
    if v["n_small"]:
        print(k, v["n_small"], v["small_targets"][:6])
print("=== CLAVIER ===", res["keyboard"]["nav_reachable"], res["keyboard"]["tab_sequence"][:10], res["keyboard"]["focus_style"])
print("=== PERF ===", res["perf"])
