import re
from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING

from nexus.datagen.models import World
from nexus.eval.questions import Question

if TYPE_CHECKING:
    # Type-only: answer -> neo4j_store -> metrics would otherwise be circular.
    from nexus.retrieval.answer import Answer

PUNCTUATION = re.compile(r"[^\w\s]")
LEGAL_TOKENS = frozenset({"pt", "tbk"})
NAMED_TYPES = frozenset({"Person", "Company", "Group"})


def normalize(text: str) -> str:
    tokens = PUNCTUATION.sub(" ", text.lower()).split()
    return " ".join(token for token in tokens if token not in LEGAL_TOKENS)


def _mentions(padded: str, form: str) -> bool:
    # Space padding turns substring search into whole-token matching.
    return bool(form) and f" {form} " in padded


def answer_match(answer_text: str, gold: list[list[str]]) -> float:
    if not gold:
        raise ValueError("answer_match needs at least one gold entity")
    padded = f" {normalize(answer_text)} "
    found = sum(any(_mentions(padded, normalize(form)) for form in forms) for forms in gold)
    return found / len(gold)


def entity_lexicon(world: World) -> dict[str, str]:
    return build_lexicon(
        (entity.id, [entity.name, *entity.aliases])
        for entity in world.entities
        if entity.type in NAMED_TYPES
    )


def build_lexicon(entries: Iterable[tuple[str, list[str]]]) -> dict[str, str]:
    pairs = {
        (normalize(form), entity_id)
        for entity_id, forms in entries
        for form in forms
        if normalize(form)
    }
    owners = Counter(form for form, _ in pairs)
    # A colliding form cannot be attributed to one entity, so it is never counted.
    return {form: entity_id for form, entity_id in pairs if owners[form] == 1}


def _entities(text: str, lexicon: dict[str, str]) -> set[str]:
    padded = f" {normalize(text)} "
    return {entity_id for form, entity_id in lexicon.items() if _mentions(padded, form)}


def extra_entities(
    answer_text: str,
    gold: list[list[str]],
    lexicon: dict[str, str],
    question_text: str = "",
    support: list[str] | None = None,
) -> int:
    gold_ids = {lexicon.get(normalize(form)) for forms in gold for form in forms}
    # Entities echoed from the question are context, not extra claims.
    allowed = gold_ids | _entities(question_text, lexicon) | set(support or [])
    return len(_entities(answer_text, lexicon) - allowed)


def recall_at_k(
    retrieved_doc_ids: list[str], gold_doc_ids: list[str], k: int | None = None
) -> float | None:
    if not gold_doc_ids:
        return None
    distinct = list(dict.fromkeys(retrieved_doc_ids))[:k]
    gold = set(gold_doc_ids)
    return len(gold.intersection(distinct)) / len(gold)


def abstain_correct(ans: "Answer", q: Question) -> bool:
    return ans.abstained == (not q.gold_answers)
