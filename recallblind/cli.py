"""Command line entry point: ingest, extract, build tasks, evaluate."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from . import adapters, ingest_cpsc, ingest_oecd, negatives, tasks
from .evaluate import score, write_report
from .extract_identifiers import build as build_identifiers
from .index import build_index
from .schema import read_jsonl, write_jsonl

DATA = Path("data")
RAW = DATA / "raw"
NORMALIZED = DATA / "normalized"
DERIVED = DATA / "derived"
BENCH = DATA / "benchmark"
RESULTS = Path("results")


def _load_index():
    path = NORMALIZED / "cpsc.jsonl"
    if not path.exists():
        raise SystemExit("run `cpsc` first")
    return build_index(read_jsonl(path), DERIVED / "identifiers.jsonl")


def cmd_cpsc(args: argparse.Namespace) -> None:
    records = ingest_cpsc.fetch_range(args.start_year, args.end_year, RAW / "cpsc")
    print(f"cpsc: wrote {write_jsonl(records, NORMALIZED / 'cpsc.jsonl')} records")


def cmd_oecd(args: argparse.Namespace) -> None:
    records = ingest_oecd.fetch(RAW / "oecd", max_records=args.limit)
    print(f"oecd: wrote {write_jsonl(records, NORMALIZED / 'oecd.jsonl')} records")


def cmd_extract(_: argparse.Namespace) -> None:
    path = NORMALIZED / "cpsc.jsonl"
    if not path.exists():
        raise SystemExit("run `cpsc` first")
    report = build_identifiers(read_jsonl(path), DERIVED / "identifiers.jsonl")
    (DERIVED / "identifier_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_negatives(args: argparse.Namespace) -> None:
    report = negatives.build(_load_index(), DERIVED / "negatives.jsonl", per_brand=args.per_brand)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_tasks(args: argparse.Namespace) -> None:
    negatives_path = DERIVED / "negatives.jsonl"
    if not negatives_path.exists():
        raise SystemExit("run `negatives` first")
    report = tasks.build(
        _load_index(),
        negatives_path,
        BENCH / "tasks.jsonl",
        cutoff=args.cutoff,
        limit_per_label=args.limit,
    )
    (BENCH / "tasks_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_eval(args: argparse.Namespace) -> None:
    path = BENCH / "tasks.jsonl"
    if not path.exists():
        raise SystemExit("run `tasks` first")
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    if args.adapter == "lookup_baseline":
        answer = adapters.lookup_baseline(_load_index())
    elif args.adapter in adapters.BUILTIN:
        answer = adapters.BUILTIN[args.adapter]
    else:
        answer = adapters.load_custom(Path(args.adapter))

    report = score(items, answer)
    report["adapter"] = Path(args.adapter).stem
    report["evaluated_at"] = date.today().isoformat()
    summary = {key: value for key, value in report.items() if key != "rows"}
    write_report(report, RESULTS, Path(args.adapter).stem)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def cmd_stats(_: argparse.Namespace) -> None:
    for name in ("cpsc", "oecd"):
        path = NORMALIZED / f"{name}.jsonl"
        if not path.exists():
            continue
        records = list(read_jsonl(path))
        years = Counter(record.recall_date[:4] for record in records if record.recall_date)
        stop_using = sum(
            1 for record in records if any("stop using" in remedy.lower() for remedy in record.remedies)
        )
        print(f"\n[{name}] {len(records)} records")
        print(f"  years: {dict(sorted(years.items()))}")
        print(f"  with image: {sum(1 for r in records if r.images)} | says 'stop using': {stop_using}")


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

    neg = sub.add_parser("negatives", help="generate verified hard negatives")
    neg.add_argument("--per-brand", type=int, default=1)
    neg.set_defaults(func=cmd_negatives)

    task = sub.add_parser("tasks", help="build benchmark task file")
    task.add_argument("--cutoff", default="2025-06-01", help="training cutoff for the temporal split")
    task.add_argument("--limit", type=int, default=400, help="max items per label")
    task.set_defaults(func=cmd_tasks)

    ev = sub.add_parser("eval", help="score an adapter")
    ev.add_argument("adapter", help="builtin name, 'lookup_baseline', or path to a .py adapter")
    ev.set_defaults(func=cmd_eval)

    sub.add_parser("stats", help="summarise normalized data").set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
