"""Active TCP port scanning module."""

from __future__ import annotations

import concurrent.futures
import socket
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, IPAddress, Port
from tddt.core.module import BaseModule, register_module

COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445,
    993, 995, 1723, 3306, 3389, 5432, 5900, 8080, 8443, 8888,
]


@register_module(
    name="corporate.vuln.port_scan",
    mode=["corporate"],
    consumes=[IPAddress],
    produces=[Port],
    active=True,
    requires_key=None,
)
class PortScanModule(BaseModule):
    """Actively probes target IP address for open TCP ports."""

    def _check_port(self, ip: str, port: int) -> int | None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            res = s.connect_ex((ip, port))
            s.close()
            if res == 0:
                return port
        except Exception:
            self.log.debug("Socket check error on %s:%d", ip, port, exc_info=True)
        return None

    def _probe_ports(
        self, entity: IPAddress, ports: list[int], max_workers: int = 20
    ) -> Iterable[Port]:
        ip = entity.value.strip()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_port = {executor.submit(self._check_port, ip, p): p for p in ports}
            for fut in concurrent.futures.as_completed(future_to_port):
                open_port = fut.result()
                if open_port is not None:
                    yield Port(
                        value=str(open_port),
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=1.0,
                        metadata={"status": "open", "verified": True, "ip": ip},
                    )

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, IPAddress):
                continue

            yield from self._probe_ports(entity, COMMON_PORTS, max_workers=20)
