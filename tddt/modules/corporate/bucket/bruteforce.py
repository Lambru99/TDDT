"""Brute-force cloud storage bucket discovery module (threaded)."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Bucket, Domain
from tddt.core.module import BaseModule, register_module

BUCKET_PATTERNS = [
    "{name}",
    "{name}-backup",
    "{name}-backups",
    "{name}-dev",
    "{name}-staging",
    "{name}-prod",
    "{name}-production",
    "{name}-assets",
    "{name}-static",
    "{name}-files",
    "{name}-media",
    "{name}-images",
    "{name}-uploads",
    "{name}-data",
    "{name}-logs",
    "{name}-archive",
    "{name}-dump",
    "{name}-public",
    "{name}-private",
    "{name}-internal",
    "{name}-test",
    "{name}-qa",
    "{name}data",
    "{name}backup",
    "{name}dev",
    "{name}prod",
]

CLOUD_TEMPLATES = [
    ("AWS S3", "https://{bucket}.s3.amazonaws.com/"),
    ("Azure Blob", "https://{bucket}.blob.core.windows.net/"),
    ("GCP Storage", "https://storage.googleapis.com/{bucket}/"),
]


@register_module(
    name="corporate.bucket.bruteforce",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Bucket],
    active=True,
    requires_key=None,
)
class BucketBruteforceModule(BaseModule):
    """Actively probes cloud storage bucket permutations concurrently."""

    def _generate_candidate_urls(self, domain: str) -> list[str]:
        company_name = domain.split(".")[0].lower()
        candidates: list[str] = []
        for pattern in BUCKET_PATTERNS:
            bucket_name = pattern.format(name=company_name)
            for _, template in CLOUD_TEMPLATES:
                candidates.append(template.format(bucket=bucket_name))
        return candidates

    def _probe_single_url(self, url: str) -> tuple[str, int | None]:
        try:
            resp = self.client.get(url, timeout=5)
            return (url, resp.status_code)
        except Exception:
            self.log.debug("Bucket probe failed for %s", url, exc_info=True)
            return (url, None)

    def _probe_urls(
        self, entity: Domain, urls: list[str], max_workers: int = 20
    ) -> Iterable[Bucket]:
        domain = entity.value.strip().lower()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self._probe_single_url, u): u for u in urls}
            for fut in concurrent.futures.as_completed(future_to_url):
                url, status = fut.result()
                if status in (200, 403):
                    yield Bucket(
                        value=url,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "status": status,
                            "access": "public" if status == 200 else "protected",
                            "domain": domain,
                        },
                    )

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            candidate_urls = self._generate_candidate_urls(domain)
            yield from self._probe_urls(entity, candidate_urls, max_workers=20)
