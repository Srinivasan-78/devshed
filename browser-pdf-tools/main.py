"""
PDF Tools backend — real text editing via PyMuPDF (MuPDF core).

Endpoints:
  GET  /health            -> liveness check
  POST /api/inspect       -> extract real text spans (position, font, size, color) for a page
  POST /api/apply-edits   -> redact original spans and redraw replacements, reusing the
                              PDF's actual embedded font where possible; falls back to a
                              metric-matched standard font (bold/italic/serif/mono detected
                              from the span's font flags) only when the original font can't
                              be extracted (e.g. a non-embedded base font).

Run:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import io
import json
import os

import pymupdf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI(title="PDF Tools backend")

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


FALLBACK_FONTS = {
    # (bold, italic, serif, mono)
    (False, False, False, False): "Helvetica",
    (True, False, False, False): "Helvetica-Bold",
    (False, True, False, False): "Helvetica-Oblique",
    (True, True, False, False): "Helvetica-BoldOblique",
    (False, False, True, False): "Times-Roman",
    (True, False, True, False): "Times-Bold",
    (False, True, True, False): "Times-Italic",
    (True, True, True, False): "Times-BoldItalic",
    (False, False, False, True): "Courier",
    (True, False, False, True): "Courier-Bold",
    (False, True, False, True): "Courier-Oblique",
    (True, True, False, True): "Courier-BoldOblique",
    (False, False, True, True): "Courier",
    (True, False, True, True): "Courier-Bold",
    (False, True, True, True): "Courier-Oblique",
    (True, True, True, True): "Courier-BoldOblique",
}


def pick_fallback_font(flags: int) -> str:
    """Metric-matched PDF standard font, used only when the original font
    can't be extracted/embedded. Bits per PyMuPDF span['flags']:
    0 superscript, 1 italic, 2 serifed, 3 monospaced, 4 bold."""
    bold = bool(flags & (1 << 4))
    italic = bool(flags & (1 << 1))
    serif = bool(flags & (1 << 2))
    mono = bool(flags & (1 << 3))
    return FALLBACK_FONTS.get((bold, italic, serif, mono), "Helvetica")


async def read_upload_bounded(file: UploadFile) -> bytes:
    """Read an uploaded file while enforcing MAX_UPLOAD_BYTES."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"uploaded file exceeds {MAX_UPLOAD_BYTES} byte limit",
        )
    return data


def open_pdf(data: bytes):
    """Open an upload, or answer 400 saying why."""
    if not data:
        raise HTTPException(status_code=400, detail="no file content received")
    try:
        return pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"could not open this file as a PDF: {exc}") from exc


def parse_edits(edits: str):
    """Validate the edits form field before any of it is trusted."""
    try:
        edit_list = json.loads(edits)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"edits is not valid JSON: {exc}") from exc

    if not isinstance(edit_list, list):
        raise HTTPException(status_code=400, detail="edits must be a JSON array")

    for i, e in enumerate(edit_list):
        if not isinstance(e, dict):
            raise HTTPException(status_code=400, detail=f"edits[{i}] is not an object")
        if not isinstance(e.get("page"), int) or isinstance(e.get("page"), bool):
            raise HTTPException(status_code=400, detail=f"edits[{i}].page must be an integer")
        bbox = e.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise HTTPException(status_code=400, detail=f"edits[{i}].bbox must be four numbers")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in bbox):
            raise HTTPException(status_code=400, detail=f"edits[{i}].bbox must be four numbers")
        if not isinstance(e.get("newText"), str):
            raise HTTPException(status_code=400, detail=f"edits[{i}].newText must be a string")
        if "size" in e:
            size = e["size"]
            if not isinstance(size, (int, float)) or isinstance(size, bool) or not (0 < size <= 1000):
                raise HTTPException(status_code=400, detail=f"edits[{i}].size must be a number in (0, 1000]")
        if "flags" in e:
            flags = e["flags"]
            if not isinstance(flags, int) or isinstance(flags, bool):
                raise HTTPException(status_code=400, detail=f"edits[{i}].flags must be an integer")
        if "font" in e and not isinstance(e["font"], str):
            raise HTTPException(status_code=400, detail=f"edits[{i}].font must be a string")
        if "color" in e:
            color = e["color"]
            if (
                not isinstance(color, (list, tuple))
                or len(color) != 3
                or not all(isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 255 for c in color)
            ):
                raise HTTPException(status_code=400, detail=f"edits[{i}].color must be three numbers in [0, 255]")

    return edit_list


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/inspect")
async def inspect(file: UploadFile = File(...), page: int = Form(...)):
    data = await read_upload_bounded(file)
    doc = open_pdf(data)
    try:
        if not 0 <= page < doc.page_count:
            raise HTTPException(
                status_code=400,
                detail=f"page {page} out of range: this document has {doc.page_count} pages",
            )
        pg = doc[page]
        rect = pg.rect
        raw = pg.get_text("dict")

        spans = []
        sid = 0
        for block in raw.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    color_int = span.get("color", 0)
                    r = (color_int >> 16) & 255
                    g = (color_int >> 8) & 255
                    b = color_int & 255
                    spans.append({
                        "id": sid,
                        "bbox": list(span["bbox"]),
                        "text": text,
                        "font": span.get("font", ""),
                        "size": span.get("size", 12),
                        "flags": span.get("flags", 0),
                        "color": [r, g, b],
                    })
                    sid += 1

        return {"width": rect.width, "height": rect.height, "spans": spans}
    finally:
        doc.close()


@app.post("/api/apply-edits")
async def apply_edits(file: UploadFile = File(...), edits: str = Form(...)):
    data = await read_upload_bounded(file)
    edit_list = parse_edits(edits)
    doc = open_pdf(data)
    try:
        by_page = {}
        for e in edit_list:
            page_num = e["page"]
            if not 0 <= page_num < doc.page_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"edit targets page {page_num}, but this document has {doc.page_count} pages",
                )
            by_page.setdefault(page_num, []).append(e)

        for page_num, page_edits in by_page.items():
            pg = doc[page_num]

            font_cache = {}
            page_fonts = {f[3]: f[0] for f in pg.get_fonts(full=False)}  # basefont -> xref

            for e in page_edits:
                rect = pymupdf.Rect(e["bbox"])
                rect.x0 -= 1
                rect.x1 += 1
                rect.y0 -= 1
                rect.y1 += 2
                pg.add_redact_annot(rect, fill=(1, 1, 1))
            pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)

            for e in page_edits:
                basefont = e.get("font", "")
                fontname = font_cache.get(basefont)

                if not fontname and basefont in page_fonts:
                    try:
                        xref = page_fonts[basefont]
                        extracted = doc.extract_font(xref)
                        fontbuffer = extracted[3]
                        if fontbuffer:
                            alias = f"F_{xref}"
                            pg.insert_font(fontname=alias, fontbuffer=fontbuffer)
                            font_cache[basefont] = alias
                            fontname = alias
                    except Exception:
                        fontname = None

                if not fontname:
                    fontname = pick_fallback_font(e.get("flags", 0))

                color = tuple(c / 255 for c in e.get("color", [0, 0, 0]))
                x0, y0, x1, y1 = e["bbox"]
                size = e.get("size", 12)
                baseline_y = y1 - size * 0.2

                try:
                    pg.insert_text((x0, baseline_y), e["newText"], fontsize=size, fontname=fontname, color=color)
                except Exception:
                    fallback = pick_fallback_font(e.get("flags", 0))
                    try:
                        pg.insert_text((x0, baseline_y), e["newText"], fontsize=size, fontname=fallback, color=color)
                    except Exception as exc:
                        raise HTTPException(
                            status_code=400,
                            detail=f"could not render replacement text on page {page_num}: {exc}",
                        ) from exc

        out = io.BytesIO()
        doc.save(out)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=edited.pdf"},
        )
    finally:
        doc.close()
