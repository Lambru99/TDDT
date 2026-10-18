"""PDF metadata extraction module for user documents."""

from __future__ import annotations

import io
from typing import ClassVar, Iterable

import pypdf

from tddt.core.entity import BaseEntity, Document, Email, FullName, Organization
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.document.pdf_metadata",
    mode=["user"],
    consumes=[Document],
    produces=[FullName, Email, Organization],
    active=False,
    requires_key=None,
)
class DocumentPdfMetadataModule(BaseModule):
    """Extracts author, email, and organization metadata from PDF documents."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Document):
                continue

            try:
                resp = self.client.get(entity.value, timeout=15)
            except Exception as e:
                _log.warning("HTTP error downloading document %s: %s", entity.value, e)
                continue

            if resp.status_code != 200:
                _log.debug("Document returned HTTP %d for %s", resp.status_code, entity.value)
                continue

            try:
                reader = pypdf.PdfReader(io.BytesIO(resp.content))
                meta = reader.metadata
            except Exception as e:
                _log.debug("Failed to parse PDF metadata from %s: %s", entity.value, e)
                continue

            if not meta:
                continue

            author = meta.author
            if author and isinstance(author, str):
                clean_author = author.strip()
                if clean_author and len(clean_author) >= 2 and "\x00" not in clean_author:
                    yield FullName(
                        value=clean_author,
                        source_module=self.name,
                        confidence=0.75,
                        metadata={
                            "document": entity.value,
                            "title": meta.title or None,
                            "creator": meta.creator or None,
                        },
                    )

            creator = meta.creator
            if creator and isinstance(creator, str):
                clean_creator = creator.strip()
                if clean_creator and len(clean_creator) >= 2:
                    yield Organization(
                        value=clean_creator,
                        source_module=self.name,
                        confidence=0.6,
                        metadata={"document": entity.value, "role": "creator"},
                    )
