import re
from dataclasses import dataclass

# shortcut: words ≈ tokens for bge-m3 budget; switch to tokenizer counts if chunks exceed 512 tokens.

WORD = re.compile(r"\S+")
PARAGRAPH_GAP = re.compile(r"\n\s*\n")
SENTENCE_END = re.compile(r"[.!?]+[\"')\]]*$")
ABBREVIATIONS = {
    "tbk", "pt", "rp", "no", "dkk", "dll", "dsb", "tn", "ny", "dr", "ir", "prof", "hj",
    "inc", "ltd", "corp", "co", "mr", "mrs", "ms", "vs", "etc", "jl", "u.s", "e.g", "i.e",
}  # fmt: skip


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    start: int
    end: int
    text: str


def chunk_id(doc_id: str, ordinal: int) -> str:
    return f"{doc_id}:{ordinal:04d}"


def _is_sentence_end(word: str) -> bool:
    if not SENTENCE_END.search(word):
        return False
    return word.lstrip("(\"'[").rstrip(".!?\"')]").lower() not in ABBREVIATIONS


def sentence_boundaries(text: str, spans: list[tuple[int, int]]) -> tuple[set[int], set[int]]:
    """Word indexes where a new sentence / paragraph starts."""
    sentences: set[int] = set()
    paragraphs: set[int] = set()
    for index in range(1, len(spans)):
        gap = text[spans[index - 1][1] : spans[index][0]]
        if PARAGRAPH_GAP.search(gap):
            paragraphs.add(index)
            sentences.add(index)
        elif _is_sentence_end(text[spans[index - 1][0] : spans[index - 1][1]]):
            sentences.add(index)
    return sentences, paragraphs


def chunk_text(text: str, max_words: int = 300, overlap_words: int = 50) -> list[Chunk]:
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words // 2:
        raise ValueError("need max_words >= 1 and 0 <= overlap_words < max_words // 2")
    spans = [match.span() for match in WORD.finditer(text)]
    total = len(spans)
    sentences, paragraphs = sentence_boundaries(text, spans)
    chunks: list[Chunk] = []
    first = 0
    while first < total:
        limit = min(first + max_words, total)
        last_chunk = limit == total
        if last_chunk:
            stop = total
        else:
            # Only accept boundaries past the midpoint so chunks don't shrink to a few words.
            floor = first + max_words // 2
            stop = next(
                (b for b in range(limit, floor, -1) if b in paragraphs),
                next((b for b in range(limit, floor, -1) if b in sentences), limit),
            )
        chunks.append(
            Chunk(
                len(chunks),
                spans[first][0],
                spans[stop - 1][1],
                text[spans[first][0] : spans[stop - 1][1]],
            )
        )
        if last_chunk:
            break
        # Restart at a sentence boundary within the overlap window, else mid-sentence; always advance.
        lowest = max(stop - overlap_words, first + 1)
        first = next((b for b in range(lowest, stop) if b in sentences), lowest)
    return chunks
