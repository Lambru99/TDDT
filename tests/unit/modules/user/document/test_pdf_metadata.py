"""Tests for user document pdf_metadata module."""

import io
import pytest
import pypdf
import responses

from tddt.core.config import Settings
from tddt.core.entity import Document, FullName
from tddt.core.http import HttpClient
from tddt.modules.user.document.pdf_metadata import DocumentPdfMetadataModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def _create_sample_pdf(author="Jane Doe", title="Resume") -> bytes:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({
        "/Author": author,
        "/Title": title,
    })
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@responses.activate
def test_pdf_metadata_extracts_author(http_client):
    mod = DocumentPdfMetadataModule(http_client, Settings())
    doc = Document(value="https://example.com/resume.pdf")

    pdf_bytes = _create_sample_pdf(author="Johnathan Doe")
    responses.add(
        responses.GET,
        "https://example.com/resume.pdf",
        body=pdf_bytes,
        status=200,
    )

    entities = list(mod.run([doc]))
    names = [e for e in entities if isinstance(e, FullName)]
    assert len(names) == 1
    assert names[0].value == "Johnathan Doe"
