"""GrayhatWarfare cloud bucket discovery module."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Bucket, Domain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.bucket.grayhat",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Bucket],
    active=False,
    requires_key="grayhat_api_key",
)
class GrayhatBucketModule(BaseModule):
    """Discovers exposed S3/GCP/Azure buckets via GrayhatWarfare API."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            api_key = getattr(self.settings, "grayhat", "") or getattr(
                self.settings, "grayhat_api_key", ""
            )
            if not api_key:
                self.log.debug("GrayhatWarfare API key not configured; skipping %s", domain)
                continue

            url = f"https://buckets.grayhatwarfare.com/api/v1/buckets/{domain}"
            headers = {"Authorization": f"Bearer {api_key}"}

            try:
                resp = self.client.get(
                    url, headers=headers, host_hint="buckets.grayhatwarfare.com", timeout=15
                )
            except Exception:
                self.log.debug("GrayhatWarfare request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (401, 403, 429):
                self.log.warning(
                    "GrayhatWarfare returned status %d for %s (forbidden / rate limit)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("GrayhatWarfare returned non-200 status %d for %s", resp.status_code, domain)
                continue

            try:
                payload = resp.json()
            except Exception:
                self.log.debug("Failed to decode GrayhatWarfare JSON for %s", domain, exc_info=True)
                continue

            for item in payload.get("buckets", []):
                bucket_url = item.get("url") or f"https://{item.get('bucket')}.s3.amazonaws.com/"
                yield Bucket(
                    value=bucket_url,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={
                        "source": "grayhat",
                        "bucket_name": item.get("bucket"),
                        "cloud": item.get("cloud", "Unknown"),
                        "domain": domain,
                    },
                )
