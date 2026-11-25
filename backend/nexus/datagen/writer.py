import json
import os
import re
from collections.abc import Callable
from pathlib import Path

from nexus.datagen.models import Edge, World
from nexus.datagen.planner import DocPlan, Lang, components
from nexus.datagen.prompts import build_messages
from nexus.llm import GatewayError, chat_text

MAX_ATTEMPTS = 3
WRITE_MAX_TOKENS = 4096
WRITE_TEMPERATURE = 0.3
WRITE_TIMEOUT = 300

LLM = Callable[[list[dict[str, str]]], str]

FAMILY_PHRASES: dict[Lang, dict[str, str]] = {
    "id": {
        "parent": "{a} adalah orang tua dari {b}",
        "child": "{a} adalah anak dari {b}",
        "sibling": "{a} adalah saudara kandung {b}",
        "spouse": "{a} adalah pasangan suami/istri dari {b}",
        "in-law": "{a} adalah kerabat semenda (ipar/mertua/menantu) dari {b}",
    },
    "en": {
        "parent": "{a} is a parent of {b}",
        "child": "{a} is a child of {b}",
        "sibling": "{a} is a sibling of {b}",
        "spouse": "{a} is the spouse of {b}",
        "in-law": "{a} is an in-law relative of {b}",
    },
}
PARTNER_KINDS: dict[Lang, dict[str, str]] = {
    "id": {
        "JV": "usaha patungan",
        "supply": "kemitraan pasokan",
        "distribution": "kemitraan distribusi",
    },
    "en": {
        "JV": "a joint venture",
        "supply": "a supply partnership",
        "distribution": "a distribution partnership",
    },
}


ONE_OFF = frozenset({"FOUNDED", "INVESTED_IN"})


class DocGenError(Exception):
    pass


def _span(edge: Edge, lang: Lang, once: bool = False) -> str:
    if edge.since is not None and edge.until is not None:
        word = ("dari", "hingga") if lang == "id" else ("from", "until")
        return f" {word[0]} {edge.since} {word[1]} {edge.until}"
    if edge.since is not None and once:
        return f" pada {edge.since}" if lang == "id" else f" in {edge.since}"
    if edge.since is not None:
        return f" sejak {edge.since}" if lang == "id" else f" since {edge.since}"
    if edge.until is not None:
        return f" hingga {edge.until}" if lang == "id" else f" until {edge.until}"
    return ""


def _sentence(edge: Edge, src: str, dst: str, lang: Lang) -> str:
    id_lang = lang == "id"
    past = edge.until is not None
    span = _span(edge, lang, once=edge.type in ONE_OFF)
    props = edge.props
    match edge.type:
        case "FAMILY_OF":
            return FAMILY_PHRASES[lang][str(props["relation"])].format(a=src, b=dst)
        case "FOUNDED":
            verb = ("mendirikan", "founded")[not id_lang]
            return f"{src} {verb} {dst}{span}"
        case "SERVES_AS":
            if id_lang:
                verb = "pernah menjabat" if past else "menjabat"
                return f"{src} {verb} sebagai {props['role']} di {dst}{span}"
            return f"{src} {'served' if past else 'serves'} as {props['role']} at {dst}{span}"
        case "OWNS_STAKE":
            if id_lang:
                verb = "pernah memegang" if past else "memegang"
                return f"{src} {verb} {props['pct']}% saham {dst}{span}"
            return f"{src} {'held' if past else 'holds'} a {props['pct']}% stake in {dst}{span}"
        case "SUBSIDIARY_OF":
            if id_lang:
                verb = "pernah menjadi" if past else "adalah"
                return f"{src} {verb} anak usaha {dst}{span}"
            return f"{src} {'was' if past else 'is'} a subsidiary of {dst}{span}"
        case "INVESTED_IN":
            amount, stage = props.get("amount_idr_bn"), props.get("round")
            if id_lang:
                return f"{src} berinvestasi di {dst} pada putaran {stage} senilai Rp{amount} miliar{span}"
            return f"{src} invested in {dst} in the {stage} round, IDR {amount} billion{span}"
        case "PARTNERS_WITH":
            kind = PARTNER_KINDS[lang][str(props["kind"])]
            if id_lang:
                verb = "pernah menjalin" if past else "menjalin"
                return f"{src} {verb} {kind} dengan {dst}{span}"
            return f"{src} {'had' if past else 'has'} {kind} with {dst}{span}"
        case "MEMBER_OF_GROUP":
            named = any(word in dst.lower() for word in ("group", "grup"))
            if id_lang:
                noun = "" if named else "grup "
                return f"{src} {'pernah menjadi' if past else 'adalah'} anggota {noun}{dst}{span}"
            noun = "" if named else " group"
            return f"{src} {'was' if past else 'is'} a member of the {dst}{noun}{span}"
        case _:
            raise DocGenError(f"cannot render edge type {edge.type}")


def render_facts(plan: DocPlan, world: World) -> list[str]:
    edges = {edge.id: edge for edge in world.edges}
    forms = plan.surface_forms
    return [
        _sentence(edges[eid], forms[edges[eid].src], forms[edges[eid].dst], plan.lang) + "."
        for eid in plan.edge_ids
    ]


def write_document(plan: DocPlan, world: World, llm: LLM | None = None) -> str:
    write = llm or (
        lambda messages: chat_text(
            messages,
            temperature=WRITE_TEMPERATURE,
            max_tokens=WRITE_MAX_TOKENS,
            timeout=WRITE_TIMEOUT,
        )
    )
    edges = {edge.id: edge for edge in world.edges}
    roundup = components([edges[eid] for eid in plan.edge_ids]) > 1
    messages = build_messages(
        plan.doc_type, plan.lang, plan.year, render_facts(plan, world), roundup
    )
    missing: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        text = write(messages)
        missing = [form for form in plan.surface_forms.values() if form not in text]
        if not missing:
            return text
    raise DocGenError(f"{plan.doc_id}: missing surface forms after {MAX_ATTEMPTS} tries: {missing}")


def _title(text: str, plan: DocPlan) -> str:
    first = next((line for line in text.splitlines() if line.strip()), "")
    return first.lstrip("# ").strip().replace("\n", " ") or plan.doc_id


def render_markdown(plan: DocPlan, text: str) -> str:
    front = [
        "---",
        f"doc_id: {plan.doc_id}",
        f"doc_type: {plan.doc_type}",
        f"lang: {plan.lang}",
        f"year: {plan.year}",
        f"title: {json.dumps(_title(text, plan), ensure_ascii=False)}",
        "---",
        "",
    ]
    return "\n".join(front) + text.strip() + "\n"


def parse_front_matter(text: str) -> tuple[dict[str, str | int], str]:
    match = re.match(r"---\n(.*?)\n---\n\n?(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError("missing front matter")
    meta: dict[str, str | int] = {}
    for line in match[1].splitlines():
        key, _, raw = line.partition(": ")
        meta[key] = json.loads(raw) if key == "title" else int(raw) if key == "year" else raw
    return meta, match[2]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)


def generate_docs(
    world: World,
    plans: list[DocPlan],
    docs_dir: Path,
    facts_path: Path,
    llm: LLM | None = None,
    force: bool = False,
) -> tuple[int, dict[str, str]]:
    written = 0
    failures: dict[str, str] = {}
    for plan in plans:
        path = docs_dir / f"{plan.doc_id}.md"
        if force or not path.exists():
            try:
                text = write_document(plan, world, llm)
            except (DocGenError, GatewayError) as error:
                failures[plan.doc_id] = str(error)
                continue
            _atomic_write(path, render_markdown(plan, text))
            written += 1
        # Rewritten after every doc so an interrupted run leaves a valid, resumable file.
        done = {p.doc_id: p.edge_ids for p in plans if (docs_dir / f"{p.doc_id}.md").exists()}
        _atomic_write(facts_path, json.dumps(done, indent=2) + "\n")
    return written, failures
