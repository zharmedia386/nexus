import re
from collections.abc import Callable

from pydantic import BaseModel

from nexus.ingest.chunker import WORD, sentence_boundaries
from nexus.llm import GatewayError, chat_json
from nexus.retrieval.prompts import CITATION_PATTERN, is_abstain

VERIFY_TIMEOUT = 120
VERIFY_CHUNK_CHARS = 2500
LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
PUNCT_GAP = re.compile(r"\s+([.,;:!?])")
HEADING = re.compile(r"^\s*#+\s")
LEADING_CITATIONS = re.compile(rf"^(?:\s*{CITATION_PATTERN.pattern})+")
CLAIM_SPLIT_VERSION = "v2"
# A leading step label is dropped and the rest of the sentence is judged on its own.
STEP_LABEL = re.compile(
    r"^(?:conclusion|kesimpulan|identify|identifikasi|step|langkah)\b[^:.]{0,80}:\s*", re.IGNORECASE
)
# Uncited sentences that announce a step or restate the question; they assert no fact.
META_PREFIX = re.compile(
    r"^(?:berikut|here (?:is|are)|to answer|untuk menjawab|let'?s|let us|mari kita|"
    r"the question asks|pertanyaan(?:nya)?\b)",
    re.IGNORECASE,
)
NO_INFO = re.compile(
    r"not found|no information|not (?:explicitly )?(?:stated|mentioned)|"
    r"(?:does|do) not (?:explicitly )?(?:state|mention|contain)|none of the (?:provided )?excerpts|"
    r"tidak (?:dapat )?ditemukan|tidak disebutkan|tidak menyebutkan|"
    r"tidak (?:ada|terdapat) informasi",
    re.IGNORECASE,
)
# A no-info sentence that also asserts something is still a claim.
POSITIVE_CLAUSE = re.compile(
    r", di mana| adalah | is | holds |memegang|menjabat|\d|%", re.IGNORECASE
)

VERIFY_SYSTEM_PROMPT = (
    "You are a strict fact-checker. You get numbered claims, each followed by the source "
    "excerpts it cites. For every claim decide whether it is FULLY supported by those excerpts "
    "alone: every fact, name, number and date in the claim must be stated or directly implied "
    "by them. Claims and excerpts may be in different languages (Indonesian or English); judge "
    "the meaning, not the wording. Do not use outside knowledge. Return one verdict per claim, "
    "using the claim's number as index."
)


class Claim(BaseModel):
    text: str
    chunk_ids: list[str]
    supported: bool | None = None


class Verdict(BaseModel):
    index: int
    supported: bool


class Verdicts(BaseModel):
    items: list[Verdict]


def _sentences(line: str) -> list[str]:
    spans = [match.span() for match in WORD.finditer(line)]
    starts = sorted({0, *sentence_boundaries(line, spans)[0]})
    return [
        line[spans[start][0] : spans[end - 1][1]]
        for start, end in zip(starts, [*starts[1:], len(spans)])
    ]


def _is_claim(text: str, cited: bool) -> bool:
    # A sentence ending in ":" introduces a list or step; it states no fact itself.
    if not text.strip(" .,;:!?") or text.endswith(":"):
        return False
    no_info = NO_INFO.search(text) and not POSITIVE_CLAUSE.search(text)
    return cited or not (is_abstain(text) or META_PREFIX.match(text) or no_info)


def split_claims(answer_text: str) -> list[Claim]:
    if is_abstain(answer_text):
        return []
    pieces: list[tuple[str, list[str]]] = []
    for line in answer_text.splitlines():
        if not line.strip() or HEADING.match(line):
            continue
        line_first = len(pieces)
        for sentence in _sentences(LIST_MARKER.sub("", line)):
            # Markers with no sentence after them cite the previous one; otherwise the next one.
            trailing = LEADING_CITATIONS.match(sentence)
            if trailing and len(pieces) > line_first and not sentence[trailing.end() :].strip():
                pieces[-1][1].extend(CITATION_PATTERN.findall(trailing.group()))
                continue
            if sentence.strip():
                pieces.append((sentence, CITATION_PATTERN.findall(sentence)))
    claims = []
    for sentence, chunk_ids in pieces:
        text = " ".join(CITATION_PATTERN.sub("", sentence).replace("**", "").split())
        text = STEP_LABEL.sub("", PUNCT_GAP.sub(r"\1", text))
        if _is_claim(text, bool(chunk_ids)):
            claims.append(
                Claim(text=text, chunk_ids=list(dict.fromkeys(chunk_ids)), supported=False)
            )
    return claims


def _build_messages(claims: list[tuple[int, Claim]], chunk_text: dict[str, str]) -> list[dict]:
    blocks = []
    for index, claim in claims:
        excerpts = "\n".join(
            f"  [{chunk_id}] {chunk_text[chunk_id][:VERIFY_CHUNK_CHARS]}"
            for chunk_id in claim.chunk_ids
        )
        blocks.append(f"Claim {index}: {claim.text}\nCited excerpts:\n{excerpts}")
    return [
        {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(blocks)},
    ]


def verify_claims(
    claims: list[Claim],
    chunk_text: dict[str, str],
    *,
    llm: Callable[..., Verdicts] = chat_json,
) -> tuple[list[Claim], int]:
    results = [claim.model_copy() for claim in claims]
    to_check: list[tuple[int, Claim]] = []
    for index, claim in enumerate(results):
        if not claim.chunk_ids or any(cid not in chunk_text for cid in claim.chunk_ids):
            claim.supported = False
        else:
            to_check.append((index, claim))
    if not to_check:
        return results, 0
    try:
        verdicts = llm(
            _build_messages(to_check, chunk_text), Verdicts, temperature=0.0, timeout=VERIFY_TIMEOUT
        )
    except GatewayError:
        for _, claim in to_check:
            claim.supported = None
        return results, 1
    verdict_by_index = {verdict.index: verdict.supported for verdict in verdicts.items}
    for index, claim in to_check:
        claim.supported = verdict_by_index.get(index)
    return results, 1
