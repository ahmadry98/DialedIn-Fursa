#!/usr/bin/env python3
"""Import/export trusted equipment profiles between JSON files and repository storage.

Examples:
  python scripts/profile_repository_cli.py export --type machine --output /tmp/machines.json
  DIALEDIN_PROFILE_STORAGE=dynamodb DIALEDIN_PROFILE_TABLE=... python scripts/profile_repository_cli.py import --type grinder --input services/espresso_mcp/grinder_profiles.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.espresso_mcp import grinder_profiles, machine_profiles, profile_repository  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import/export DialedIN equipment profiles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export profiles from the configured repository backend.")
    export_parser.add_argument("--type", choices=["machine", "grinder"], required=True)
    export_parser.add_argument("--output", type=Path, required=True)

    import_parser = subparsers.add_parser("import", help="Import profiles into the configured repository backend.")
    import_parser.add_argument("--type", choices=["machine", "grinder"], required=True)
    import_parser.add_argument("--input", type=Path, required=True)

    args = parser.parse_args()
    json_path = machine_profiles.PROFILE_PATH if args.type == "machine" else grinder_profiles.PROFILE_PATH

    if args.command == "export":
        profiles = profile_repository.load_profiles(args.type, json_path)
        args.output.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
        print(f"Exported {len(profiles)} {args.type} profiles to {args.output}")
        return

    profiles = profile_repository.load_profiles_json(args.input)
    profile_repository.save_profiles(args.type, profiles, json_path)
    print(f"Imported {len(profiles)} {args.type} profiles into configured repository storage")


if __name__ == "__main__":
    main()
