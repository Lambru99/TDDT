"""Photon crawler and OSINT extractor wrapper module."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

from tddt.core.entity import BaseEntity, Domain, Email, Secret, URL
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.external.photon",
    mode=["corporate"],
    consumes=[Domain],
    produces=[URL, Secret, Email],
    active=True,
    requires_key=None,
)
class PhotonModule(BaseModule):
    """Wraps Photon OSINT web crawler for deep URL, secret, and email harvesting."""

    def _find_photon_exec(self) -> list[str] | None:
        env_path = getattr(self.settings, "photon_path", "")
        if env_path and os.path.exists(env_path):
            # Bug §2.13 fix: use sys.executable
            return [sys.executable, env_path]

        if shutil.which("photon"):
            return ["photon"]

        if shutil.which("photon.py"):
            return [sys.executable, shutil.which("photon.py")]  # type: ignore[list-item]

        # Check local photon directory if present
        local_py = Path("photon/photon.py")
        if local_py.is_file():
            return [sys.executable, str(local_py.resolve())]

        return None

    def _get_output_dir(self, temp_dir: str) -> Path:
        return Path(temp_dir) / "out"

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            cmd_prefix = self._find_photon_exec()
            if not cmd_prefix:
                self.log.debug("Photon executable not found in PATH or settings; skipping %s", domain)
                continue

            target_url = f"https://{domain}"
            temp_dir = tempfile.mkdtemp(prefix="tddt_photon_")
            output_folder = self._get_output_dir(temp_dir)

            command = cmd_prefix + [
                "-u", target_url,
                "-l", "3",
                "-t", "10",
                "--keys",
                "--wayback",
                "-o", str(output_folder),
            ]

            timed_out = False
            try:
                # Bug §2.13 fix: timeout 300s
                subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                # Bug §2.13 fix: preserve output folder on timeout for partial results
                timed_out = True
                self.log.warning(
                    "Photon crawler timed out after 300s on %s; preserving partial results", domain
                )
            except Exception:
                self.log.debug("Photon execution failed for %s", domain, exc_info=True)

            if not output_folder.is_dir():
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    self.log.debug("Cleanup error for %s", temp_dir, exc_info=True)
                continue

            # Parse discovered files
            url_files = ["internal.txt", "external.txt", "scripts.txt", "endpoints.txt", "fuzzable.txt"]
            for fname in url_files:
                fpath = output_folder / fname
                if fpath.is_file():
                    try:
                        with open(fpath, encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                u = line.strip()
                                if u:
                                    yield URL(
                                        value=u,
                                        parent_id=entity.id,
                                        source_module=self.name,
                                        metadata={"category": fname.replace(".txt", ""), "domain": domain},
                                    )
                    except Exception:
                        self.log.debug("Failed reading %s", fpath, exc_info=True)

            # Keys
            keys_file = output_folder / "keys.txt"
            if keys_file.is_file():
                try:
                    with open(keys_file, encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            key = line.strip()
                            if key:
                                yield Secret(
                                    value=key,
                                    parent_id=entity.id,
                                    source_module=self.name,
                                    metadata={"source": "photon_keys", "domain": domain},
                                )
                except Exception:
                    self.log.debug("Failed reading keys from Photon", exc_info=True)

            # Intel (Emails)
            intel_file = output_folder / "intel.txt"
            if intel_file.is_file():
                try:
                    with open(intel_file, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        emails = extract_domain_emails(content, domain)
                        for email in sorted(emails):
                            yield Email(
                                value=email,
                                parent_id=entity.id,
                                source_module=self.name,
                                metadata={"source": "photon_intel", "domain": domain},
                            )
                except Exception:
                    self.log.debug("Failed reading intel from Photon", exc_info=True)

            # Cleanup
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                self.log.debug("Cleanup error for %s", temp_dir, exc_info=True)
