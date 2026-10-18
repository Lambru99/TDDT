#!/usr/bin/env python3
"""Legacy main.py shim — redirects to TDDT v2 CLI with deprecation warning.

Usage:
    python main.py <target_domain> [flags]
    Redirects to: tddt corp <target_domain> [flags]
"""

from __future__ import annotations

import argparse
import sys

import tddt.cli

DEPRECATION_BANNER = (
    "\n[DEPRECATION WARNING] Running 'python main.py' is deprecated and will be removed.\n"
    "Please use the TDDT v2 CLI entrypoint instead:\n"
    "  tddt corp <domain> [options]    # for corporate attack surface discovery\n"
    "  tddt user [options]             # for user OSINT investigation\n"
)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Always output deprecation warning to stderr
    print(DEPRECATION_BANNER, file=sys.stderr)

    if not argv or "-h" in argv or "--help" in argv:
        return tddt.cli.main(["corp", "-h"])

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("domain", nargs="?", default=None)
    parser.add_argument("-l", "--light", action="store_true")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-t", "--threads", default=None)
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--only-keyless", action="store_true")

    args, unknown = parser.parse_known_args(argv)

    if not args.domain:
        return tddt.cli.main(["corp", "-h"])

    translated = ["corp", args.domain]
    if args.light:
        translated.append("--light")
    if args.output:
        translated.extend(["-o", args.output])
    if args.threads:
        translated.extend(["-t", str(args.threads)])
    if args.verbose:
        translated.append(f"-{'v' * args.verbose}")
    if args.only_keyless:
        translated.append("--only-keyless")

    return tddt.cli.main(translated)


if __name__ == "__main__":
    sys.exit(main())