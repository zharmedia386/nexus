from collections import Counter
from dataclasses import dataclass

import igraph
import leidenalg


@dataclass(frozen=True)
class Community:
    id: str
    level: int
    parent_id: str | None
    member_ids: list[str]


def _partition(
    members: list[str], pair_weights: Counter[tuple[int, int]], seed: int
) -> list[list[str]]:
    graph = igraph.Graph(n=len(members), edges=list(pair_weights), directed=False)
    graph.es["weight"] = list(pair_weights.values())
    partition = leidenalg.find_partition(
        graph, leidenalg.ModularityVertexPartition, weights="weight", seed=seed
    )
    return [sorted(members[index] for index in cluster) for cluster in partition]


def _pair_weights(members: list[str], edges: list[tuple[str, str]]) -> Counter[tuple[int, int]]:
    # Multi-edges collapse to one undirected pair weighted by relationship count.
    index = {node: position for position, node in enumerate(members)}
    weights: Counter[tuple[int, int]] = Counter()
    for src, dst in edges:
        if src in index and dst in index and src != dst:
            weights[tuple(sorted((index[src], index[dst])))] += 1  # type: ignore[index]
    return weights


def _ranked(groups: list[list[str]]) -> list[list[str]]:
    return sorted((group for group in groups if len(group) > 1), key=lambda g: (-len(g), g[0]))


def detect_communities(
    nodes: list[str],
    edges: list[tuple[str, str]],
    *,
    seed: int = 42,
    max_size: int = 25,
) -> list[Community]:
    ordered = sorted(set(nodes))
    top = _ranked(_partition(ordered, _pair_weights(ordered, edges), seed))
    communities = [Community(f"c0_{index}", 0, None, members) for index, members in enumerate(top)]
    children: list[tuple[str, list[str]]] = []
    for parent in communities:
        if len(parent.member_ids) <= max_size:
            continue
        inner = _partition(parent.member_ids, _pair_weights(parent.member_ids, edges), seed)
        children += [(parent.id, members) for members in _ranked(inner)]
    children.sort(key=lambda child: (-len(child[1]), child[1][0]))
    communities += [
        Community(f"c1_{index}", 1, parent_id, members)
        for index, (parent_id, members) in enumerate(children)
    ]
    return communities
