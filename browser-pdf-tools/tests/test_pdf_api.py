import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as pdf_main  # noqa: E402


client = TestClient(pdf_main.app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_pick_fallback_font_flags():
    assert pdf_main.pick_fallback_font(0) == "Helvetica"
    assert pdf_main.pick_fallback_font(1 << 4) == "Helvetica-Bold"
    assert pdf_main.pick_fallback_font((1 << 4) | (1 << 1) | (1 << 2)) == "Times-BoldItalic"
    assert pdf_main.pick_fallback_font(1 << 3) == "Courier"


def test_parse_edits_validation():
    valid = '[{"page": 0, "bbox": [10, 20, 100, 40], "newText": "hi", "size": 12, "color": [0, 0, 0]}]'
    parsed = pdf_main.parse_edits(valid)
    assert len(parsed) == 1

    import pytest
    from fastapi import HTTPException

    for bad in [
        "not-json",
        "{}",
        '[{"page": true, "bbox": [0,0,1,1], "newText": "x"}]',
        '[{"page": 0, "bbox": [0,0,1], "newText": "x"}]',
        '[{"page": 0, "bbox": [0,0,1,1], "newText": "x", "color": [300, 0, 0]}]',
        '[{"page": 0, "bbox": [0,0,1,1], "newText": "x", "size": -5}]',
    ]:
        with pytest.raises(HTTPException) as exc:
            pdf_main.parse_edits(bad)
        assert exc.value.status_code == 400


def test_inspect_and_apply_edits_roundtrip():
    import pymupdf

    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((72, 72), "Hello DevShed", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()

    res = client.post(
        "/api/inspect",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"page": "0"},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["spans"]) >= 1
    span = body["spans"][0]

    edits = [{"page": 0, "bbox": span["bbox"], "newText": "Updated", "size": 14, "color": [0, 0, 0]}]
    import json

    res2 = client.post(
        "/api/apply-edits",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"edits": json.dumps(edits)},
    )
    assert res2.status_code == 200
    assert res2.headers["content-type"] == "application/pdf"
