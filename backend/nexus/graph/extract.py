import re
from typing import Protocol

from nexus.graph.prompts import EXTRACT_SYSTEM_PROMPT
from nexus.graph.schema import ChunkExtraction, ExtractionResult, VerifiedRelation
from nexus.llm import chat_json

EXTRACT_PROMPT_VERSION = "v2"
EXTRACT_TIMEOUT = 300
MAX_QUOTE_CHARS = 300


class ExtractLLM(Protocol):
    def __call__(
        self,
        messages: list[dict[str, str]],
        schema: type[ChunkExtraction],
        *,
        temperature: float,
        timeout: float,
    ) -> ChunkExtraction: ...


def _locate(quote: str, text: str) -> tuple[int, int] | None:
    if not quote.strip() or len(quote) > MAX_QUOTE_CHARS:
        return None
    start = text.find(quote)
    if start >= 0:
        return start, start + len(quote)
    tokens = quote.split()
    # Models often reflow line breaks; match the same tokens across any whitespace run.
    match = re.search(r"\s+".join(map(re.escape, tokens)), text)
    return (match.start(), match.end()) if match else None


def extract_chunk(text: str, *, llm: ExtractLLM = chat_json) -> ExtractionResult:
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    # Long chunks with many relations exceed the default 120s gateway timeout.
    extraction = llm(messages, ChunkExtraction, temperature=0.0, timeout=EXTRACT_TIMEOUT)
    names = {entity.name for entity in extraction.entities}
    kept: list[VerifiedRelation] = []
    dropped_unverified = dropped_unknown_entity = 0
    for relation in extraction.relations:
        span = _locate(relation.quote, text)
        if span is None:
            dropped_unverified += 1
        elif relation.src not in names or relation.dst not in names:
            dropped_unknown_entity += 1
        else:
            kept.append(VerifiedRelation(relation=relation, quote_start=span[0], quote_end=span[1]))
    return ExtractionResult(
        entities=extraction.entities,
        relations=kept,
        dropped_unverified=dropped_unverified,
        dropped_unknown_entity=dropped_unknown_entity,
    )
