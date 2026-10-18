"""Tests for user document text_mine module."""

import io
import pytest
import pypdf
import responses

from tddt.core.config import Settings
from tddt.core.entity import Document, Email, Phone
from tddt.core.http import HttpClient
from tddt.modules.user.document.text_mine import DocumentTextMineModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def _create_sample_pdf_with_text(text: str) -> bytes:
    # Use reportlab or pypdf to create a basic pdf with stream
    # Minimal hand-crafted PDF with plain text
    content = text.encode("utf-8")
    stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin1")
    pdf_data = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj\n"
        b"4 0 obj <</Length " + str(len(stream)).encode("latin1") + b">> stream\n" + stream + b"\nendstream\nendobj\n"
        b"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n999\n%%EOF\n"
    )
    return pdf_data


@responses.activate
def test_text_mine_extracts_email_and_phone(http_client):
    mod = DocumentTextMineModule(http_client, Settings())
    doc = Document(value="https://example.com/cv.pdf")

    # Or simply mock PdfReader
    pdf_bytes = _create_sample_pdf_with_text("Contact: candidate@example.org or +14155552671")
    responses.add(
        responses.GET,
        "https://example.com/cv.pdf",
        body=pdf_bytes,
        status=200,
    )

    entities = list(mod.run([doc]))
    emails = [e for e in entities if isinstance(e, Email)]
    phones = [e for e in entities if isinstance(e, Phone)]

    assert any(e.value == "candidate@example.org" for e in emails)
    assert any("+14155552671" in p.value for p in phones)
