"""TDDT v2 CLI entrypoint — subcommands: corp, user, update-wmn-db, clear-cache, list-modules."""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from platformdirs import user_cache_dir

from tddt.core.config import load_settings
from tddt.core.engine import CorrelationEngine
from tddt.core.entity import Domain, Email, FullName, Phone, Username
from tddt.core.http import get_client
from tddt.core.logger import get_logger, setup_logging
from tddt.core.module import MODULE_REGISTRY, autodiscover
from tddt.report.json_exporter import export_json

if TYPE_CHECKING:
    from tddt.core.entity import EntityGraph


def get_cache_path() -> Path:
    return Path(user_cache_dir("tddt")) / "http.sqlite"


def _wmn_db_path() -> Path:
    return Path(user_cache_dir("tddt")) / "wmn.json"


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", metavar="FILE", help="Output path (default: report-<target>-<ts>.json)")
    parser.add_argument("-f", "--format", default="rich,json", metavar="FMT", help="Output formats (default: rich,json)")
    parser.add_argument("-l", "--light", action="store_true", help="Passive-only mode (no active modules)")
    parser.add_argument("--only-keyless", action="store_true", help="Skip modules that require API keys")
    parser.add_argument("-t", "--threads", type=int, default=20, metavar="N")
    parser.add_argument("-v", action="count", default=0, dest="verbosity")
    parser.add_argument("--proxy", metavar="URL")
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=5, metavar="N")
    parser.add_argument("--max-runtime", type=float, default=600.0, metavar="S")
    parser.add_argument("--only-module", metavar="NAME", action="append", default=[])
    parser.add_argument("--skip-module", metavar="NAME", action="append", default=[])


def _build_scan_meta(mode: str, seeds: list, args: argparse.Namespace, started_at: datetime.datetime) -> dict:
    return {
        "mode": mode,
        "seed": {type(s).__name__: s.value for s in seeds},
        "started_at": started_at.isoformat(),
        "flags": {
            "light": getattr(args, "light", False),
            "only_keyless": getattr(args, "only_keyless", False),
            "threads": getattr(args, "threads", 20),
        },
    }


def _default_output_path(target: str) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(f"report-{target}-{ts}.json")


def _run_scan(
    seeds: list,
    mode: str,
    args: argparse.Namespace,
    target: str,
) -> int:
    setup_logging(args.verbosity)

    cli_overrides: dict = {}
    if args.proxy:
        cli_overrides["proxy"] = args.proxy
    if args.insecure:
        cli_overrides["verify_tls"] = False
    if args.threads != 20:
        cli_overrides["threads"] = args.threads
    if args.max_iterations != 5:
        cli_overrides["max_iterations"] = args.max_iterations
    if args.max_runtime != 600.0:
        cli_overrides["max_runtime"] = args.max_runtime
    if args.no_cache:
        cli_overrides["cache_enabled"] = False

    settings = load_settings(cli_overrides=cli_overrides)
    client = get_client()

    engine = CorrelationEngine(client=client, settings=settings)

    started_at = datetime.datetime.now()
    graph: EntityGraph = engine.scan(
        seeds=seeds,
        mode=mode,
        allow_active=not args.light,
        keyless_only=args.only_keyless,
    )
    finished_at = datetime.datetime.now()

    scan_meta = _build_scan_meta(mode, seeds, args, started_at)
    scan_meta["finished_at"] = finished_at.isoformat()
    scan_meta["duration_s"] = (finished_at - started_at).total_seconds()

    output_path = Path(args.output) if args.output else _default_output_path(target)
    export_json(graph, scan_meta, output_path)

    return 0


def _run_corp(args: argparse.Namespace) -> int:
    seeds = [Domain(value=args.domain)]
    return _run_scan(seeds, "corporate", args, args.domain)


def _run_user(args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> int:
    seeds: list = []
    if args.email:
        seeds.append(Email(value=args.email))
    if args.username:
        seeds.append(Username(value=args.username))
    if args.name:
        seeds.append(FullName(value=args.name))
    if args.phone:
        seeds.append(Phone(value=args.phone))
    target = args.email or args.username or (args.name or "").replace(" ", "_") or args.phone or "user"
    return _run_scan(seeds, "user", args, target)


def _run_update_wmn_db() -> int:
    log = get_logger(__name__)
    log.info("update-wmn-db: stub — real download implemented in Task 4.3")
    return 0


def _run_clear_cache() -> int:
    cache_file = get_cache_path()
    if cache_file.exists():
        cache_file.unlink()
    return 0


def _run_list_modules(args: argparse.Namespace) -> int:
    autodiscover()
    mode_filter = args.mode
    keyless_only = args.keyless_only if hasattr(args, "keyless_only") else False

    for name, cls in sorted(MODULE_REGISTRY.items()):
        if mode_filter:
            mode_map = {"corp": "corporate", "user": "user"}
            canonical = mode_map.get(mode_filter, mode_filter)
            if not hasattr(cls, "mode") or canonical not in (cls.mode or []):
                continue
        if keyless_only and getattr(cls, "requires_key", None):
            continue
        key_flag = f"[key={cls.requires_key}]" if getattr(cls, "requires_key", None) else "[keyless]"
        active_flag = "[active]" if getattr(cls, "active", False) else "[passive]"
        mode_str = ",".join(getattr(cls, "mode", []) or [])
        print(f"{name:50s} {mode_str:20s} {active_flag} {key_flag}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tddt", description="TDDT v2 — EASM + OSINT")
    subparsers = parser.add_subparsers(dest="command")

    # corp
    corp_parser = subparsers.add_parser("corp", help="Corporate domain EASM scan")
    corp_parser.add_argument("domain", help="Target domain (e.g. example.com)")
    _add_common_flags(corp_parser)
    corp_parser.add_argument("--aggressive-email", action="store_true")
    corp_parser.add_argument("--photon-path", metavar="PATH")

    # user
    user_parser = subparsers.add_parser("user", help="User OSINT scan")
    user_parser.add_argument("--email", metavar="ADDR")
    user_parser.add_argument("--username", metavar="HANDLE")
    user_parser.add_argument("--name", metavar="FULL_NAME")
    user_parser.add_argument("--phone", metavar="NUMBER")
    _add_common_flags(user_parser)
    user_parser.add_argument("--aggressive-phone", action="store_true")
    user_parser.add_argument("--follow-domains", action="store_true")

    # update-wmn-db
    subparsers.add_parser("update-wmn-db", help="Download/update WhatsMyName database")

    # clear-cache
    subparsers.add_parser("clear-cache", help="Clear HTTP response cache")

    # list-modules
    list_parser = subparsers.add_parser("list-modules", help="List registered modules")
    list_parser.add_argument("--mode", choices=["corp", "user"], metavar="MODE")
    list_parser.add_argument("--keyless-only", action="store_true")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "corp":
        return _run_corp(args)

    if args.command == "user":
        if not any([args.email, args.username, args.name, args.phone]):
            user_parser.error(
                "at least one of --email, --username, --name, --phone is required"
            )
        return _run_user(args)

    if args.command == "update-wmn-db":
        return _run_update_wmn_db()

    if args.command == "clear-cache":
        return _run_clear_cache()

    if args.command == "list-modules":
        return _run_list_modules(args)

    parser.print_help()
    return 1
