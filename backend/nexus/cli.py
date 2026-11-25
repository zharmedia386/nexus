import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import psycopg

from nexus.checks import CHECKS
from nexus.config import Settings, get_settings
from nexus.datagen.models import World
from nexus.datagen.planner import plan_documents
from nexus.datagen.reference import REFERENCE_DOC_ID, render_reference
from nexus.datagen.world import build_world
from nexus.datagen.writer import generate_docs
from nexus.db import repo
from nexus.eval.audit import rescore_run, write_audit
from nexus.eval.harness import QUESTIONS_PATH, RUNS_DIR, run_eval
from nexus.eval.judge import run_judge
from nexus.eval.metrics import entity_lexicon
from nexus.eval.questions import build_questions, load_questions, write_questions
from nexus.eval.report import write_report
from nexus.eval.review import REVIEW_PATH, write_review_sheet
from nexus.graph.communities import detect_communities
from nexus.graph.metrics import evaluate_graph, write_graph_report
from nexus.graph.neo4j_store import GraphStore
from nexus.graph.resolve import (
    Adjudicator,
    PersonContext,
    ResolvedGraph,
    adjudicate_people,
    pair_key,
    resolve,
)
from nexus.graph.runner import extract_tenant, load_extractions
from nexus.graph.schema import ExtractionResult
from nexus.graph.summaries import summarize_tenant
from nexus.ingest.pipeline import ingest_dir
from nexus.llm import GatewayError
from nexus.retrieval.modes import MODES
from nexus.retrieval.verify import verify_claims
from nexus.vector.milvus_store import TENANT_PATTERN, ChunkStore

WORLD_DIR = Path(__file__).resolve().parents[2] / "data" / "world"
DOCS_DIR = WORLD_DIR / "docs"
WORLD_PATH = WORLD_DIR / "ground_truth.json"


def run_checks(settings: Settings, checks: dict[str, Callable[[Settings], str]]) -> int:
    failures = 0
    for name, check in checks.items():
        try:
            print(f"{name}: ok ({check(settings)})")
        except Exception as error:  # noqa: BLE001 - report any failure per service
            failures += 1
            # type name only: messages from clients can echo URLs/headers
            print(f"{name}: FAIL ({type(error).__name__})")
    return 1 if failures else 0


def _load_world() -> tuple[World, str]:
    if WORLD_PATH.exists():
        return World.from_json(WORLD_PATH), WORLD_PATH.name
    return build_world(42), "build_world(42) fallback"


def _eval(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.target == "questions":
        world_data, source = _load_world()
        plans = plan_documents(world_data)
        available = [plan for plan in plans if (DOCS_DIR / f"{plan.doc_id}.md").exists()]
        if not available:
            parser.error("no generated docs found; run `nexus datagen docs` first")
        print(f"eval: skipped {len(plans) - len(available)} plans without docs")
        questions = build_questions(world_data, available)
        write_questions(questions, QUESTIONS_PATH)
        print(f"eval: wrote {len(questions)} questions to {QUESTIONS_PATH} (world from {source})")
        for category, count in sorted(Counter(q.category for q in questions).items()):
            print(f"eval:   {category}: {count}")
        return
    if args.target == "review-sheet":
        questions = load_questions(QUESTIONS_PATH)
        write_review_sheet(questions, REVIEW_PATH)
        print(f"eval: wrote {len(questions)} rows to {REVIEW_PATH}")
        return
    if args.target in ("audit-claims", "rescore-claims", "judge", "report"):
        runs = [p for p in RUNS_DIR.glob(f"{args.run}*.json") if ".rescored" not in p.name]
        if len(runs) != 1:
            parser.error(f"--run {args.run!r} matches {len(runs)} run files")
    if args.target == "report":
        run_path = runs[0].with_name(f"{runs[0].stem}.rescored.json") if args.rescored else runs[0]
        inputs = [run_path, args.graph, args.audit, *(args.judge or [])]
        missing = [str(path) for path in inputs if path and not path.exists()]
        if missing:
            parser.error(f"missing input files: {', '.join(missing)}")
        path = write_report(
            run_path,
            world=_load_world()[0],
            docs_dir=DOCS_DIR,
            questions=load_questions(QUESTIONS_PATH),
            review_path=REVIEW_PATH,
            graph_path=args.graph,
            judge_paths=args.judge,
            audit_path=args.audit,
            # The pre-rescore run supplies v1 claim counts for the splitter disclosure.
            base_run_path=runs[0] if args.rescored else None,
        )
        print(f"eval: wrote {path} and {path.with_suffix('.json')}")
        return
    if args.target == "judge":
        path = run_judge(
            runs[0],
            args.a,
            args.b,
            args.categories.split(",") if args.categories else None,
            workers=args.workers,
        )
        report = json.loads(path.read_text(encoding="utf-8"))
        print(f"eval: wrote {path}")
        print(
            f"eval: skipped {report['skipped_rejected']} review-rejected, "
            f"excluded {report['excluded_missing']} missing/errored"
        )
        for criterion, rates in report["win_rates"].items():
            print(f"eval:   {criterion}: {rates}")
        return
    if args.target == "rescore-claims":
        path, pending = rescore_run(runs[0], verify_claims if args.verify else None)
        print(f"eval: wrote {path} ({pending} cited claims awaiting re-verify)")
        return
    if args.target == "audit-claims":
        questions = {q.id: q.text for q in load_questions(QUESTIONS_PATH)}
        with repo.connect() as conn:

            def fetch(ids: list[str]) -> dict[str, str]:
                return {row.id: row.text for row in repo.get_chunks(conn, args.tenant, ids)}

            path = write_audit(
                runs[0], args.mode, args.category, args.n, questions, fetch, args.seed
            )
        print(f"eval: wrote {path}")
        return
    modes = args.modes.split(",")
    unknown = [mode for mode in modes if mode not in MODES]
    if unknown:
        parser.error(f"unknown modes: {', '.join(unknown)}")
    if not TENANT_PATTERN.fullmatch(args.tenant):
        parser.error(f"invalid tenant: {args.tenant!r}")
    run_id = run_eval(
        modes,
        args.tenant,
        args.limit,
        verify=not args.no_verify,
        lexicon=entity_lexicon(_load_world()[0]),
    )
    print(f"eval: run {run_id}")
    print((RUNS_DIR / f"{run_id}.md").read_text(encoding="utf-8"))


def _cached_adjudicator(
    conn: psycopg.Connection, tenant: str, llm: Adjudicator | None
) -> Adjudicator:
    def adjudicate(a: PersonContext, b: PersonContext) -> bool:
        key = pair_key(a, b)
        cached = repo.get_adjudication(conn, tenant, key)
        # End the read transaction so the connection is not idle-in-transaction during the call.
        conn.rollback()
        if cached is not None:
            return cached
        if llm is None:
            return False
        same = llm(a, b)
        # Commit per verdict so a later gateway failure loses nothing; reruns resume from cache.
        repo.put_adjudication(conn, tenant, key, same)
        conn.commit()
        return same

    return adjudicate


def _resolve(
    extractions: dict[str, ExtractionResult],
    chunks: list[repo.ChunkRow],
    adjudicate: Adjudicator,
    max_adjudications: int,
) -> ResolvedGraph:
    try:
        return resolve(
            extractions, chunks, adjudicate=adjudicate, max_adjudications=max_adjudications
        )
    except GatewayError as error:
        print(
            f"graph: person adjudication failed ({error}); cached verdicts kept, re-run to resume"
        )
        sys.exit(1)


def _graph_build(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.max_adjudications < 0:
        parser.error("--max-adjudications must be >= 0")
    with repo.connect() as conn:
        counts = extract_tenant(conn, args.tenant, workers=args.workers)
        print(counts)
        if counts["failed"] and not args.allow_partial:
            print(
                f"graph: {counts['failed']} chunks failed extraction; "
                "not writing a partial graph, re-run to retry (or pass --allow-partial)"
            )
            sys.exit(1)
        extractions = load_extractions(conn, args.tenant)
        chunks = repo.list_chunks(conn, args.tenant)
        adjudicate = _cached_adjudicator(conn, args.tenant, adjudicate_people)
        resolved = _resolve(extractions, chunks, adjudicate, args.max_adjudications)
    with GraphStore() as store:
        store.ensure_schema()
        written = store.write_graph(args.tenant, resolved)
    print(written)
    print(
        f"adjudication_bound={resolved.adjudication_bound} adjudications={resolved.adjudications} "
        f"skipped_alias_unions={resolved.skipped_alias_unions}"
    )
    if counts["failed"]:
        print(f"graph: wrote partial graph ({counts['failed']} chunks failed extraction)")


def _graph_communities(args: argparse.Namespace) -> None:
    with GraphStore() as store:
        nodes, edges = store.read_entity_graph(args.tenant)
        communities = detect_communities(nodes, edges)
        store.write_communities(args.tenant, communities)
    for level in (0, 1):
        sizes = sorted((len(c.member_ids) for c in communities if c.level == level), reverse=True)
        if sizes:
            print(
                f"level {level}: {len(sizes)} communities, "
                f"size max={sizes[0]} median={sizes[len(sizes) // 2]} min={sizes[-1]}"
            )


def _graph_summarize(args: argparse.Namespace) -> dict[str, int]:
    with repo.connect() as conn, GraphStore() as store:
        chunk_store = ChunkStore(get_settings().collection("communities"))
        return summarize_tenant(conn, store, chunk_store, args.tenant, workers=args.workers)


def _graph_eval(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.max_adjudications < 0:
        parser.error("--max-adjudications must be >= 0")
    world_data, source = _load_world()
    with repo.connect() as conn:
        extractions = load_extractions(conn, args.tenant)
        chunks = repo.list_chunks(conn, args.tenant)
        # Same resolve() and verdict cache as `graph build`, so a warm cache scores the same graph.
        if args.no_adjudicate:
            adjudicate: Adjudicator = lambda a, b: False
        else:
            llm = None if args.no_llm else adjudicate_people
            adjudicate = _cached_adjudicator(conn, args.tenant, llm)
        # Cache-only runs make no LLM calls, so the call cap does not apply.
        limit = sys.maxsize if args.no_llm else args.max_adjudications
        resolved = _resolve(extractions, chunks, adjudicate, limit)
    ingested = {chunk.doc_id for chunk in chunks}
    plans = {plan.doc_id: plan for plan in plan_documents(world_data) if plan.doc_id in ingested}
    result = evaluate_graph(resolved, extractions, world_data, plans)
    result.config = {
        "tenant": args.tenant,
        "world": source,
        "chunks extracted": f"{len(extractions)}/{len(chunks)}",
        "adjudication": "off"
        if args.no_adjudicate
        else f"{resolved.adjudications} calls" + (" (cache only)" if args.no_llm else ""),
    }
    path = write_graph_report(result)
    print(f"graph: report {path}")
    print(path.read_text(encoding="utf-8"))


def main(
    argv: list[str] | None = None, llm: Callable[[list[dict[str, str]]], str] | None = None
) -> None:
    parser = argparse.ArgumentParser(prog="nexus")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    datagen = commands.add_parser("datagen").add_subparsers(dest="target", required=True)
    world = datagen.add_parser("world")
    world.add_argument("--seed", type=int, default=42)
    world.add_argument("--out", type=Path, default=WORLD_PATH)
    docs = datagen.add_parser("docs")
    docs.add_argument("--force", action="store_true")
    datagen.add_parser("reference")
    commands.add_parser("db").add_subparsers(dest="target", required=True).add_parser("migrate")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("directory", type=Path, nargs="?", default=DOCS_DIR)
    ingest.add_argument("--tenant", default="demo")
    graph = commands.add_parser("graph").add_subparsers(dest="target", required=True)
    extract = graph.add_parser("extract")
    extract.add_argument("--tenant", default="demo")
    extract.add_argument("--force", action="store_true")
    extract.add_argument("--workers", type=int, default=4)
    build = graph.add_parser("build")
    build.add_argument("--tenant", default="demo")
    build.add_argument("--workers", type=int, default=4)
    build.add_argument("--allow-partial", action="store_true")
    build.add_argument("--max-adjudications", type=int, default=500)
    graph_eval = graph.add_parser("eval")
    graph_eval.add_argument("--tenant", default="demo")
    graph_eval.add_argument("--max-adjudications", type=int, default=500)
    graph_eval.add_argument("--no-adjudicate", action="store_true")
    graph_eval.add_argument("--no-llm", action="store_true", help="cached verdicts only")
    communities = graph.add_parser("communities")
    communities.add_argument("--tenant", default="demo")
    summarize = graph.add_parser("summarize")
    summarize.add_argument("--tenant", default="demo")
    summarize.add_argument("--workers", type=int, default=4)
    evaluate = commands.add_parser("eval").add_subparsers(dest="target", required=True)
    evaluate.add_parser("questions")
    evaluate.add_parser("review-sheet")
    run = evaluate.add_parser("run")
    run.add_argument("--modes", default="rag,hybrid")
    run.add_argument("--no-verify", action="store_true")
    run.add_argument("--limit", type=int)
    run.add_argument("--tenant", default="demo")
    audit = evaluate.add_parser("audit-claims")
    audit.add_argument("--run", required=True)
    audit.add_argument("--mode", required=True, choices=sorted(MODES))
    audit.add_argument("--category", required=True)
    audit.add_argument("--n", type=int, default=30)
    audit.add_argument("--seed", type=int, default=42)
    audit.add_argument("--tenant", default="demo")
    judge = evaluate.add_parser("judge")
    judge.add_argument("--run", required=True)
    judge.add_argument("--a", required=True, choices=sorted(MODES))
    judge.add_argument("--b", required=True, choices=sorted(MODES))
    judge.add_argument("--categories")
    judge.add_argument("--workers", type=int, default=4)
    rescore = evaluate.add_parser("rescore-claims")
    rescore.add_argument("--run", required=True)
    rescore.add_argument("--verify", action="store_true")
    report = evaluate.add_parser("report")
    report.add_argument("--run", required=True)
    report.add_argument("--rescored", action="store_true")
    report.add_argument("--graph", type=Path)
    report.add_argument("--judge", type=Path, action="extend", nargs="+")
    report.add_argument("--audit", type=Path)
    args = parser.parse_args(argv)
    if args.command == "eval":
        _eval(parser, args)
        return
    if args.command == "ingest":
        if not TENANT_PATTERN.fullmatch(args.tenant):
            parser.error(f"invalid tenant: {args.tenant!r}")
        if not args.directory.is_dir():
            parser.error(f"not a directory: {args.directory}")
        counts = ingest_dir(args.directory, args.tenant)
        print(counts)
        if counts["failed"]:
            sys.exit(1)
        return
    if args.command == "graph":
        if not TENANT_PATTERN.fullmatch(args.tenant):
            parser.error(f"invalid tenant: {args.tenant!r}")
        if args.target == "eval":
            _graph_eval(parser, args)
            return
        if args.target == "communities":
            _graph_communities(args)
            return
        if args.workers < 1:
            parser.error("--workers must be >= 1")
        if args.target == "build":
            _graph_build(parser, args)
            return
        if args.target == "summarize":
            counts = _graph_summarize(args)
            print(counts)
            if counts["failed"]:
                sys.exit(1)
            return
        with repo.connect() as conn:
            counts = extract_tenant(conn, args.tenant, force=args.force, workers=args.workers)
        print(counts)
        if counts["failed"]:
            sys.exit(1)
        return
    if args.command == "db":
        with repo.connect() as conn:
            repo.migrate(conn)
        print("db: migrated")
        return
    if args.command == "datagen" and args.target == "docs":
        world_data, source = _load_world()
        print(f"docs: world from {source}")
        plans = plan_documents(world_data)
        count, failures = generate_docs(
            world_data, plans, DOCS_DIR, WORLD_DIR / "doc_facts.json", llm, args.force
        )
        print(f"docs: wrote {count} of {len(plans)}")
        for reason in failures.values():
            print(f"docs: FAILED {reason}")
        if failures:
            sys.exit(1)
        return
    if args.command == "datagen" and args.target == "reference":
        path = DOCS_DIR / f"{REFERENCE_DOC_ID}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_reference(_load_world()[0]), encoding="utf-8")
        print(f"reference: wrote {path}")
        return
    if args.command == "datagen":
        build_world(args.seed).to_json(args.out)
        print(f"world: wrote {args.out}")
        return
    sys.exit(run_checks(get_settings(), CHECKS))
