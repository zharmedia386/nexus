import re

from nexus.datagen.planner import Lang
from nexus.vector.milvus_store import CHUNK_ID_BODY

ABSTAIN_ID = "Informasi tidak ditemukan dalam dokumen."
ABSTAIN_EN = "The documents do not contain this information."
ABSTAIN: dict[Lang, str] = {"id": ABSTAIN_ID, "en": ABSTAIN_EN}
CITATION_PATTERN = re.compile(rf"\[({CHUNK_ID_BODY})\]")


def is_abstain(text: str) -> bool:
    return text.strip().startswith((ABSTAIN_ID, ABSTAIN_EN))


# Guards overlong chunks from blowing the context budget.
MAX_CHUNK_CHARS = 2500

SYSTEM_PROMPT = (
    "You answer questions using ONLY the document excerpts provided in the user message.\n"
    "Rules:\n"
    "- Excerpts may be in a different language from the question; answer in the question's "
    "language.\n"
    "- Cite every factual sentence with the id of the excerpt that supports it, written as "
    "[chunk_id], one id per bracket, e.g. [doc_000:0000]. Use only ids shown in the excerpts; "
    "never invent ids.\n"
    "- Do not use outside knowledge.\n"
    "- A company may appear under a shortened name (without PT/Tbk), a ticker code, or its "
    "group's name, and excerpts may be in another language; treat these as the same entity "
    "and answer from them.\n"
    "- If the excerpts answer only part of the question, answer that part.\n"
    "- Only if no excerpt states the requested fact, reply with exactly this "
    "sentence and nothing else: {abstain}"
)

USER_TEMPLATE = "Excerpts:\n{context}\n\nQuestion: {question}"


def build_messages(question: str, hit_texts: list[tuple[str, str]], lang: Lang) -> list[dict]:
    context = "\n\n".join(f"[{chunk_id}] {text[:MAX_CHUNK_CHARS]}" for chunk_id, text in hit_texts)
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(abstain=ABSTAIN[lang])},
        {"role": "user", "content": USER_TEMPLATE.format(context=context, question=question)},
    ]
