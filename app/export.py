"""Export Word (.docx) des livrables, au nom du cabinet."""
from __future__ import annotations

import io
import os

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.shared import Pt, RGBColor

CABINET = os.getenv("KAPSI_CABINET", "Cabinet de conseil")


def to_docx(doc: dict) -> bytes:
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(11)

    wide = any(len(s.get("table", {}).get("columns", [])) > 4 for s in doc["sections"])
    if wide:
        sec = d.sections[0]
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width

    head = d.sections[0].header.paragraphs[0]
    head.text = f"{CABINET} · Kapsi-Q — {doc.get('client', '')}"
    d.add_heading(doc["title"], level=0)
    meta = d.add_paragraph(f"Date : {doc.get('date', '')}    Version : 0 (projet)")
    meta.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    for s in doc["sections"]:
        d.add_heading(s["heading"], level=1)
        for p in s.get("paragraphs", []):
            d.add_paragraph(p)
        for b in s.get("bullets", []):
            d.add_paragraph(b, style="List Bullet")
        if "table" in s:
            t = s["table"]
            tbl = d.add_table(rows=1, cols=len(t["columns"]))
            tbl.style = "Light Grid Accent 1"
            for i, col in enumerate(t["columns"]):
                tbl.rows[0].cells[i].text = col
            for row in t["rows"]:
                cells = tbl.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = str(v)
    d.add_paragraph()
    foot = d.add_paragraph(doc.get("footer", ""))
    foot.runs[0].italic = True
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
