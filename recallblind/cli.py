"""Command line entry point: ingest sources, then derive identifiers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from . import ingest_cpsc, ingest_oecd
from .extract_identifiers import build
from .schema import read_jsonl, write_jsonl

DATA = Path("data")
RAW = DATA / "raw"
NORMALIZED = DATA / "normalized"
DERIVED = DATA / "derived"


def cmd_cpsc(args: argparse.Namespace) -> None:
    records = ingest_cpsc.fetch_range(args.start_year, args.end_year, RAW / "cpsc")
    count = write_jsonl(records, NORMALIZED / "cpsc.jsonl")
    print(f"cpsc: wrote {count} records")


def cmd_oecd(args: argparse.Namespace) -> None:
    records = ingest_oecd.fetch(RAW / "oecd", max_records=args.limit)
    count = write_jsonl(records, NORMALIZED / "oecd.jsonl")
    print(f"oecd: wrote {count} records")


def cmd_extract(_: argparse.Namespace) -> None:
    path = NORMALIZED / "cpsc.jsonl"
    if not path.exists():
        raise SystemExit("run `cpsc` first")
    report = build(read_jsonl(path), DERIVED / "identifiers.jsonl")
    (DERIVED / "identifier_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_stats(_: argparse.Namespace) -> None:
    for name in ("cpsc", "oecd"):
        path = NORMALIZED / f"{name}.jsonl"
        if not path.exists():
            continue
        records = list(read_jsonl(path))
        years = Counter(record.recall_date[:4] for record in records if record.recall_date)
        with_image = sum(1 for record in records if record.images)
        with_remedy = sum(1 for record in records if record.remedies)
        stop_using = sum(
            1 for record in records if any("stop using" in remedy.lower() for remedy in record.remedies)
        )
        print(f"\n[{name}] {len(records)} records")
        print(f"  years: {dict(sorted(years.items()))}")
        print(f"  with image: {with_image} | with remedy: {with_remedy} | says 'stop using': {stop_using}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="recallblind")
    sub = parser.add_subparsers(dest="command", required=True)

    cpsc = sub.add_parser("cpsc", help="ingest US CPSC recalls")
    cpsc.add_argument("--start-year", type=int, default=2023)
    cpsc.add_argument("--end-year", type=int, default=date.today().year)
    cpsc.set_defaults(func=cmd_cpsc)

    oecd = sub.add_parser("oecd", help="ingest OECD Global Recalls")
    oecd.add_argument("--limit", type=int, default=500)
    oecd.set_defaults(func=cmd_oecd)

    sub.add_parser("extract", help="derive product identifiers").set_defaults(func=cmd_extract)
    sub.add_parser("stats", help="summarise normalized data").set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
