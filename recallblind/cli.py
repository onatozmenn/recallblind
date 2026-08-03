"""Command line entry point: ingest, extract, build tasks, evaluate."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from . import adapters, campaign, gold, hazards, ingest_cpsc, ingest_oecd, negatives, tasks
from .evaluate import score, select_items, write_report
from .extract_identifiers import build as build_identifiers
from .index import build_index
from .remedies import MINIMISING_RE
from .schema import read_jsonl, write_jsonl

DATA = Path("data")
RAW = DATA / "raw"
NORMALIZED = DATA / "normalized"
DERIVED = DATA / "derived"
BENCH = DATA / "benchmark"
GOLD = DATA / "gold"
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
        limit_action=args.limit_action,
        limit_notice=args.limit_notice,
        fresh_after=args.fresh_after,
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

    items = select_items(items, args.task, args.limit)
    if not items:
        raise SystemExit("no items selected")

    module = None
    if args.adapter == "lookup_baseline":
        answer = adapters.lookup_baseline(_load_index())
    elif args.adapter in adapters.BUILTIN:
        answer = adapters.BUILTIN[args.adapter]
    else:
        answer, module = adapters.load_custom(Path(args.adapter), with_module=True)

    # Progress goes to stderr so stdout stays parseable JSON.
    print(f"scoring {len(items)} items with {args.adapter}", file=sys.stderr, flush=True)
    report = score(items, answer)
    report["adapter"] = Path(args.adapter).stem
    report["evaluated_at"] = date.today().isoformat()
    if module is not None and hasattr(module, "usage"):
        report["usage"] = module.usage()
    if module is not None and hasattr(module, "MODEL"):
        report["model"] = module.MODEL

    summary = {key: value for key, value in report.items() if key != "rows"}
    write_report(report, RESULTS, Path(args.adapter).stem)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def cmd_gold_sample(args: argparse.Namespace) -> None:
    path = NORMALIZED / "cpsc.jsonl"
    if not path.exists():
        raise SystemExit("run `cpsc` first")
    report = gold.build_sample(list(read_jsonl(path)), BENCH / "gold_sample.jsonl", size=args.size)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_annotate(args: argparse.Namespace) -> None:
    sample = BENCH / "gold_sample.jsonl"
    if not sample.exists():
        raise SystemExit("run `gold-sample` first")
    gold.annotate(sample, GOLD / f"{args.annotator}.jsonl", args.annotator, limit=args.limit)


def cmd_agreement(args: argparse.Namespace) -> None:
    print(json.dumps(gold.cohens_kappa(Path(args.first), Path(args.second)), indent=2))


def cmd_extractor_score(args: argparse.Namespace) -> None:
    paths = [Path(path) for path in args.annotations]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit(f"missing annotation files: {', '.join(missing)}")
    print(json.dumps(gold.score_extractor(paths), indent=2))


def cmd_hazards(_: argparse.Namespace) -> None:
    path = NORMALIZED / "cpsc.jsonl"
    if not path.exists():
        raise SystemExit("run `cpsc` first")
    report = hazards.coverage(read_jsonl(path))
    (DERIVED / "hazard_coverage.json").parent.mkdir(parents=True, exist_ok=True)
    (DERIVED / "hazard_coverage.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _campaign(name: str) -> campaign.Campaign:
    if name not in campaign.CAMPAIGNS:
        raise SystemExit(f"unknown campaign: {name}")
    return campaign.CAMPAIGNS[name]


def cmd_campaign_sample(args: argparse.Namespace) -> None:
    spec = _campaign(args.campaign)
    if spec.name == "hazards":
        source = NORMALIZED / "cpsc.jsonl"
        if not source.exists():
            raise SystemExit("run `cpsc` first")
        rows = campaign.sample_hazards(list(read_jsonl(source)), args.size, args.seed)
    else:
        source = DERIVED / "negatives.jsonl"
        if not source.exists():
            raise SystemExit("run `negatives` first")
        rows = campaign.sample_negatives(campaign.load(source), args.size, args.seed)
    print(json.dumps(campaign.write_sample(rows, BENCH / f"{spec.name}_sample.jsonl"), indent=2))


def cmd_campaign_label(args: argparse.Namespace) -> None:
    spec = _campaign(args.campaign)
    sample = BENCH / f"{spec.name}_sample.jsonl"
    if not sample.exists():
        raise SystemExit(f"run `campaign-sample {spec.name}` first")
    campaign.annotate(
        spec, sample, GOLD / f"{spec.name}-{args.annotator}.jsonl", args.annotator, args.limit
    )


def cmd_campaign_agreement(args: argparse.Namespace) -> None:
    spec = _campaign(args.campaign)
    print(json.dumps(campaign.agreement(spec, Path(args.first), Path(args.second)), indent=2))


def cmd_campaign_report(args: argparse.Namespace) -> None:
    spec = _campaign(args.campaign)
    paths = [Path(path) for path in args.annotations] or sorted(GOLD.glob(f"{spec.name}-*.jsonl"))
    if not paths:
        raise SystemExit(f"no annotations found in {GOLD}")
    report = campaign.summarise(spec, paths, BENCH / f"{spec.name}_sample.jsonl")
    print(json.dumps(report, indent=2, ensure_ascii=False))


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
        # Measured at 0.2% of CPSC records, so minimising wording in a model
        # response is almost always introduced by the model, not quoted.
        minimising = sum(
            1
            for record in records
            if MINIMISING_RE.search(" ".join([*record.remedies, record.description, record.title]))
        )
        print(f"\n[{name}] {len(records)} records")
        print(f"  years: {dict(sorted(years.items()))}")
        print(f"  with image: {sum(1 for r in records if r.images)} | says 'stop using': {stop_using}")
        print(f"  contains GPSR-banned minimising wording: {minimising} ({minimising / len(records):.1%})")


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
    task.add_argument("--limit", type=int, default=400, help="max T1/T2 items per label")
    task.add_argument("--limit-action", type=int, default=300, help="max T3 items")
    task.add_argument("--limit-notice", type=int, default=300, help="max T4 items")
    task.add_argument(
        "--fresh-after",
        default=None,
        help="recalls issued after this date form the contamination-resistant 'fresh' split",
    )
    task.set_defaults(func=cmd_tasks)

    ev = sub.add_parser("eval", help="score an adapter")
    ev.add_argument("adapter", help="builtin name, 'lookup_baseline', or path to a .py adapter")
    ev.add_argument("--limit", type=int, default=None, help="pilot run: cap items, spread across tasks")
    ev.add_argument("--task", nargs="+", default=None, help="restrict to given tasks, e.g. T1 T2")
    ev.set_defaults(func=cmd_eval)

    sub.add_parser("stats", help="summarise normalized data").set_defaults(func=cmd_stats)

    sample = sub.add_parser("gold-sample", help="draw the deterministic annotation sample")
    sample.add_argument("--size", type=int, default=300)
    sample.set_defaults(func=cmd_gold_sample)

    annotate = sub.add_parser("annotate", help="label extracted identifiers by hand")
    annotate.add_argument("annotator", help="your name; one file per annotator")
    annotate.add_argument("--limit", type=int, default=None, help="items to label this session")
    annotate.set_defaults(func=cmd_annotate)

    agreement = sub.add_parser("agreement", help="Cohen's kappa between two annotators")
    agreement.add_argument("first")
    agreement.add_argument("second")
    agreement.set_defaults(func=cmd_agreement)

    extractor = sub.add_parser("extractor-score", help="precision/recall/F1 against the gold set")
    extractor.add_argument("annotations", nargs="+")
    extractor.set_defaults(func=cmd_extractor_score)

    sub.add_parser("hazards", help="coverage of the draft hazard taxonomy").set_defaults(
        func=cmd_hazards
    )

    names = sorted(campaign.CAMPAIGNS)
    csample = sub.add_parser("campaign-sample", help="draw an annotation sample")
    csample.add_argument("campaign", choices=names)
    csample.add_argument("--size", type=int, default=200)
    csample.add_argument("--seed", type=int, default=20260804)
    csample.set_defaults(func=cmd_campaign_sample)

    clabel = sub.add_parser("campaign-label", help="label a sample by hand")
    clabel.add_argument("campaign", choices=names)
    clabel.add_argument("annotator")
    clabel.add_argument("--limit", type=int, default=None)
    clabel.set_defaults(func=cmd_campaign_label)

    cagree = sub.add_parser("campaign-agreement", help="Cohen's kappa for a campaign")
    cagree.add_argument("campaign", choices=names)
    cagree.add_argument("first")
    cagree.add_argument("second")
    cagree.set_defaults(func=cmd_campaign_agreement)

    creport = sub.add_parser("campaign-report", help="label distribution, and rates per family")
    creport.add_argument("campaign", choices=names)
    creport.add_argument("annotations", nargs="*", help="defaults to every file in data/gold")
    creport.set_defaults(func=cmd_campaign_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
