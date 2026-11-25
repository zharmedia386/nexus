from collections.abc import Callable
from dataclasses import dataclass

import psycopg
from pydantic import BaseModel

from nexus.config import get_settings
from nexus.db import repo
from nexus.eval.metrics import normalize
from nexus.graph.neo4j_store import FrontierEdge, GraphPath, GraphStore, make_path
from nexus.llm import GatewayError, chat_json
from nexus.retrieval.modes import RERANK_POOL_FACTOR, Reranker, rerank_hits
from nexus.vector.milvus_store import ChunkStore, Hit

PINNED_SCORE = 1.0
HOP_SYSTEM = (
    "You walk a knowledge graph of Indonesian companies, people and groups to answer a "
    "question. You see the path followed so far and the numbered relationships touching the "
    "current entities. Choose at most {beam} relationship ids that lead toward the answer "
    "(empty list if none do). Set done=true when the followed relationships already reach "
    "the answer. If a followed relationship already names the answer entity, return "
    "follow=[] and done=true."
)


class Hop(BaseModel):
    follow: list[str]
    done: bool


@dataclass(frozen=True)
class TraversalStep:
    hop: int
    from_id: str
    to_id: str
    edge: FrontierEdge


def link_entities(question: str, lexicon: dict[str, str]) -> list[str]:
    tokens = normalize(question).split()
    longest = max((len(form.split()) for form in lexicon), default=0)
    matches = [
        (end - start, start, lexicon[form])
        for start in range(len(tokens))
        for end in range(start + 1, min(start + longest, len(tokens)) + 1)
        if (form := " ".join(tokens[start:end])) in lexicon
    ]
    taken: set[int] = set()
    linked: list[str] = []
    for length, start, entity_id in sorted(matches, key=lambda match: (-match[0], match[1])):
        span = set(range(start, start + length))
        if span & taken:
            continue
        taken |= span
        if entity_id not in linked:
            linked.append(entity_id)
    return linked


def describe_edge(label: str, edge: FrontierEdge) -> str:
    attrs = {
        "role": edge.role,
        "relation": edge.relation,
        "pct": edge.pct,
        "since": edge.since,
        "until": edge.until,
    }
    shown = "".join(f" {name}={value}" for name, value in attrs.items() if value is not None)
    return f"{label}: {edge.src_name} -[{edge.type}{shown}]-> {edge.dst_name}"


def traverse(
    question: str,
    tenant: str,
    start_ids: list[str],
    graph: GraphStore,
    *,
    llm: Callable[..., Hop] = chat_json,
    max_hops: int = 4,
    beam: int = 3,
) -> tuple[list[TraversalStep], int]:
    steps: list[TraversalStep] = []
    visited = set(start_ids)
    frontier = list(start_ids)
    calls = 0
    for hop in range(1, max_hops + 1):
        followed = sorted({step.edge.key for step in steps})
        edges = [
            edge
            for edge in graph.frontier_edges(tenant, frontier, exclude=followed)
            if not (edge.src_id in visited and edge.dst_id in visited)
        ]
        if not edges:
            break
        # Short labels instead of Neo4j element ids: fewer tokens, fewer copy errors.
        labelled = {f"E{index}": edge for index, edge in enumerate(edges, 1)}
        so_far = "\n".join(describe_edge(f"hop {s.hop}", s.edge) for s in steps) or "(start)"
        messages = [
            {"role": "system", "content": HOP_SYSTEM.format(beam=beam)},
            {
                "role": "user",
                "content": f"Question: {question}\n\nFollowed so far:\n{so_far}\n\n"
                "Relationships:\n"
                + "\n".join(describe_edge(label, edge) for label, edge in labelled.items()),
            },
        ]
        # Counts gateway calls made by traverse; chat_json's internal JSON retry is not counted.
        calls += 1
        try:
            choice = llm(messages, Hop, temperature=0.0, timeout=120)
        except GatewayError:
            break
        chosen = [labelled[key] for key in dict.fromkeys(choice.follow) if key in labelled]
        next_frontier: list[str] = []
        for edge in chosen[:beam]:
            from_id = edge.src_id if edge.src_id in frontier else edge.dst_id
            to_id = edge.dst_id if from_id == edge.src_id else edge.src_id
            steps.append(TraversalStep(hop, from_id, to_id, edge))
            if to_id not in visited:
                visited.add(to_id)
                next_frontier.append(to_id)
        if choice.done or not next_frontier:
            break
        frontier = next_frontier
    return steps, calls


def traversal_paths(steps: list[TraversalStep]) -> list[GraphPath]:
    reached: dict[str, TraversalStep] = {}
    for step in steps:
        reached.setdefault(step.to_id, step)
    continued = {(step.from_id, step.hop) for step in steps}
    paths = []
    for leaf in steps:
        if (leaf.to_id, leaf.hop + 1) in continued and reached[leaf.to_id] is leaf:
            continue
        chain = [leaf]
        # hop strictly decreases along the walk back, so this terminates.
        while chain[-1].hop > 1 and chain[-1].from_id in reached:
            chain.append(reached[chain[-1].from_id])
        chain.reverse()

        def name(entity_id: str, edge: FrontierEdge) -> str:
            return edge.src_name if entity_id == edge.src_id else edge.dst_name

        paths.append(
            make_path(
                [chain[0].from_id, *(step.to_id for step in chain)],
                [name(chain[0].from_id, chain[0].edge), *(name(s.to_id, s.edge) for s in chain)],
                [step.edge.type for step in chain],
                [step.edge.chunk_ids for step in chain],
                [step.edge.quotes for step in chain],
                [step.edge.doc_ids for step in chain],
                [step.edge.src_id for step in chain],
            )
        )
    return paths


def retrieve_graph_local(
    question: str,
    tenant: str,
    *,
    store: ChunkStore,
    graph: GraphStore,
    conn: psycopg.Connection,
    embedder: Callable[[list[str]], list[list[float]]],
    reranker: Reranker,
    llm: Callable[..., Hop] = chat_json,
) -> tuple[list[Hit], list[GraphPath], int]:
    settings = get_settings()
    limit = settings.RERANKER_TOP_N
    vector = embedder([question])[0]
    hybrid = store.hybrid_search(tenant, question, vector, settings.RETRIEVAL_TOP_K)
    linked = link_entities(question, graph.entity_lexicon(tenant)) or graph.entities_in_chunks(
        tenant, [hit.chunk_id for hit in hybrid]
    )
    paths = graph.paths_between(tenant, linked) if len(linked) >= 2 else []
    steps, calls = traverse(question, tenant, linked, graph, llm=llm) if linked else ([], 0)
    paths += traversal_paths(steps)
    neighbours = graph.neighbourhood(tenant, linked) if linked else []
    # First chunk of every followed edge first, so deep hops survive the top-N cut.
    followed_ids = [s.edge.chunk_ids[0] for s in steps if s.edge.chunk_ids] + [
        chunk for step in steps for chunk in step.edge.chunk_ids[1:]
    ]
    graph_ids = [chunk for path in paths + neighbours for chunk in path.chunk_ids]
    known = {hit.chunk_id: hit for hit in hybrid}
    missing = [chunk for chunk in dict.fromkeys(followed_ids + graph_ids) if chunk not in known]
    # Graph chunk ids absent from Postgres are dropped, so every hit is real evidence.
    texts = known | {
        row.id: Hit(row.id, row.doc_id, row.text, 0.0)
        for row in repo.get_chunks(conn, tenant, missing)
    }
    # Followed-edge provenance is pinned: it is the evidence the traversal chose.
    pinned = [
        Hit(hit.chunk_id, hit.doc_id, hit.text, PINNED_SCORE)
        for chunk in dict.fromkeys(followed_ids)
        if (hit := texts.get(chunk))
    ][:limit]
    pinned_ids = {hit.chunk_id for hit in pinned}
    candidates = [
        texts[chunk]
        for chunk in dict.fromkeys(graph_ids + list(known))
        if chunk in texts and chunk not in pinned_ids
    ][: limit * RERANK_POOL_FACTOR]
    rest = rerank_hits(question, candidates, reranker) if len(pinned) < limit else []
    return (pinned + rest)[:limit], paths, calls
