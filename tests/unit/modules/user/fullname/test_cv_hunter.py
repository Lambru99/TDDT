"""Tests for user fullname cv_hunter module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Document, FullName
from tddt.core.http import HttpClient
from tddt.modules.user.fullname.cv_hunter import FullNameCvHunterModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_fullname_cv_hunter_finds_documents(http_client):
    mod = FullNameCvHunterModule(http_client, Settings())
    name = FullName(value="Alice Smith")

    html = """
    <html>
      <a href="https://university.edu/staff/asmith_cv.pdf">Alice Smith Curriculum Vitae</a>
      <a href="https://company.org/docs/resume.docx">Resume</a>
      <a href="https://google.com/search">Search</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22Alice+Smith%22+%28filetype%3Apdf+OR+filetype%3Adoc+OR+filetype%3Adocx%29",
        body=html,
        status=200,
    )

    entities = list(mod.run([name]))
    docs = [e for e in entities if isinstance(e, Document)]
    assert len(docs) == 2
    assert any("asmith_cv.pdf" in d.value for d in docs)
    assert any("resume.docx" in d.value for d in docs)
