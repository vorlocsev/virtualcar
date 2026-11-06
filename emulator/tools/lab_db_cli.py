#!/usr/bin/env python3
"""Local-only Virtual Car lab database initializer / private health summary.

No daemon, network listener or J2534 writes. Nothing starts automatically.
"""
import argparse
import json
from pathlib import Path
import sys

from lab_sqlite_repository import (
    RepositoryError, database_health, list_profiles, repository
)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Virtual Car lab SQLite catalog (offline)")
    ap.add_argument("action", choices=("init", "health"))
    ap.add_argument("--database", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        with repository(args.database, create=args.action == "init") as db:
            health = database_health(db)
            if not health["sqlite_quick_check_passed"] or health["foreign_key_violations"]:
                raise RepositoryError("database integrity audit failed")
    except RepositoryError:
        # Do not output private paths, SQL details, or exception strings.
        print("LAB_DB_ERROR: local database unavailable or invalid", file=sys.stderr)
        return 2
    if args.action == "init":
        print("LAB_DB_INITIALIZED: schema v1, no vehicle data imported")
    else:
        print(json.dumps(health, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
