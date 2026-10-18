"""Text mining module for extracting emails and phone numbers from documents."""

from __future__ import annotations

import io
import re
from typing import ClassVar, Iterable

import phonenumbers
import pypdf

from tddt.core.entity import BaseEntity, Document, Email, Phone
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


@register_module(
    name="user.document.text_mine",
    mode=["user"],
    consumes=[Document],
    produces=[Email, Phone],
    active=False,
    requires_key=None,
)
class DocumentTextMineModule(BaseModule):
    """Mines document text for emails and telephone numbers."""

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

            extracted_text = ""
            # Attempt PDF extraction
            try:
                reader = pypdf.PdfReader(io.BytesIO(resp.content))
                text_parts = [page.extract_text() or "" for page in reader.pages]
                extracted_text = "\n".join(text_parts)
            except Exception as e:
                _log.debug("PDF text extraction failed for %s: %s", entity.value, e)

            # If empty or not PDF, attempt DOCX extraction
            if not extracted_text.strip():
                try:
                    import docx

                    doc = docx.Document(io.BytesIO(resp.content))
                    extracted_text = "\n".join(p.text for p in doc.paragraphs)
                except Exception as e:
                    _log.debug("DOCX text extraction failed for %s: %s", entity.value, e)

            # If still empty, check raw bytes for plain text
            if not extracted_text.strip():
                try:
                    extracted_text = resp.content.decode("utf-8", errors="ignore")
                except Exception as e:
                    _log.debug("Plain text decoding failed for %s: %s", entity.value, e)

            if not extracted_text:
                continue

            # Extract Emails
            seen_emails = set()
            for match in EMAIL_RE.finditer(extracted_text):
                email_val = match.group(0).lower()
                if email_val in seen_emails:
                    continue
                seen_emails.add(email_val)
                yield Email(
                    value=email_val,
                    source_module=self.name,
                    confidence=0.8,
                    metadata={"document": entity.value, "source": "text_mine"},
                )

            # Extract Phones via phonenumbers matcher
            seen_phones = set()
            try:
                for match in phonenumbers.PhoneNumberMatcher(extracted_text, None):
                    formatted = phonenumbers.format_number(
                        match.number, phonenumbers.PhoneNumberFormat.E164
                    )
                    if formatted in seen_phones:
                        continue
                    seen_phones.add(formatted)
                    yield Phone(
                        value=formatted,
                        source_module=self.name,
                        confidence=0.8,
                        metadata={"document": entity.value, "source": "text_mine"},
                    )
            except Exception as e:
                _log.debug("Phone matching error in %s: %s", entity.value, e)
