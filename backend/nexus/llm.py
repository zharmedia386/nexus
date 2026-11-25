import re
import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from pydantic import BaseModel, ValidationError

from nexus.config import get_settings

EMBED_BATCH_SIZE = 32
MAX_RETRIES = 2
BACKOFF_SECONDS = 0.5
DEFAULT_TIMEOUT = 120
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class GatewayError(Exception):
    pass


_default_client: httpx.Client | None = None


def _get_default_client() -> httpx.Client:
    global _default_client
    if _default_client is None:
        _default_client = httpx.Client(timeout=120)
    return _default_client


@contextmanager
def _parsing(path: str) -> Iterator[None]:
    try:
        yield
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise GatewayError(f"{path} returned an unexpected body") from exc


def _close_objects(node: object) -> None:
    # Strict mode needs every object closed with all properties required.
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        for value in node.values():
            _close_objects(value)
    elif isinstance(node, list):
        for item in node:
            _close_objects(item)


def _post(
    path: str, body: dict, client: httpx.Client | None, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    settings = get_settings()
    client = client or _get_default_client()
    url = f"{settings.LLM_BASE_URL.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    last_error: str
    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            time.sleep(BACKOFF_SECONDS * attempt)
        try:
            response = client.post(url, json=body, headers=headers, timeout=timeout)
        except httpx.TransportError as exc:
            last_error = f"transport error: {type(exc).__name__}"
            continue
        if response.status_code >= 500 or response.status_code == 429:
            last_error = f"HTTP {response.status_code}"
            continue
        if response.status_code >= 400:
            raise GatewayError(f"{path} failed: HTTP {response.status_code}")
        with _parsing(path):
            return response.json()
    raise GatewayError(f"{path} failed after {MAX_RETRIES} retries: {last_error}")


def _chat(body: dict, client: httpx.Client | None, timeout: float = DEFAULT_TIMEOUT) -> str:
    payload = {"model": get_settings().LLM_MODEL, **body}
    data = _post("/v1/chat/completions", payload, client, timeout)
    with _parsing("/v1/chat/completions"):
        content = data["choices"][0]["message"]["content"]
    # Reasoning models can leak <think> blocks into content.
    return THINK_BLOCK.sub("", content).strip()


def chat_json[T: BaseModel](
    messages: list[dict[str, str]],
    schema: type[T],
    *,
    temperature: float = 0.0,
    timeout: float = DEFAULT_TIMEOUT,
    client: httpx.Client | None = None,
) -> T:
    json_schema = schema.model_json_schema()
    _close_objects(json_schema)
    body = {
        "messages": messages,
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "strict": True, "schema": json_schema},
        },
    }
    for attempt in range(2):
        try:
            return schema.model_validate_json(_chat(body, client, timeout))
        except ValidationError as exc:
            if attempt:
                raise GatewayError(f"invalid {schema.__name__} JSON after retry") from exc
    raise AssertionError("unreachable")


def chat_text(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout: float = DEFAULT_TIMEOUT,
    client: httpx.Client | None = None,
) -> str:
    body = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    return _chat(body, client, timeout)


def embed(texts: list[str], *, client: httpx.Client | None = None) -> list[list[float]]:
    model = get_settings().EMBEDDING_MODEL
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        data = _post("/v1/embeddings", {"model": model, "input": batch}, client)
        with _parsing("/v1/embeddings"):
            batch_vectors = [
                item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])
            ]
        if len(batch_vectors) != len(batch):
            raise GatewayError("/v1/embeddings returned a wrong number of vectors")
        vectors.extend(batch_vectors)
    return vectors


QWEN3_RERANK_PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query "
    'and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n'
    "<|im_start|>user\n"
)
QWEN3_RERANK_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
QWEN3_RERANK_INSTRUCT = (
    "Given a question about Indonesian companies, retrieve passages that contain the answer"
)


def _rerank_inputs(query: str, docs: list[str]) -> tuple[str, list[str]]:
    # qwen3-reranker scores raw text poorly; it expects its instruction chat template.
    if get_settings().RERANKER_TEMPLATE != "qwen3":
        return query, docs
    templated_query = (
        f"{QWEN3_RERANK_PREFIX}<Instruct>: {QWEN3_RERANK_INSTRUCT}\n<Query>: {query}\n"
    )
    return templated_query, [f"<Document>: {doc}{QWEN3_RERANK_SUFFIX}" for doc in docs]


def rerank(
    query: str, docs: list[str], top_n: int, *, client: httpx.Client | None = None
) -> list[tuple[int, float]]:
    if not docs:
        return []
    templated_query, templated_docs = _rerank_inputs(query, docs)
    body = {
        "model": get_settings().RERANKER_MODEL,
        "query": templated_query,
        "documents": templated_docs,
        "top_n": top_n,
    }
    data = _post("/rerank", body, client)
    with _parsing("/rerank"):
        scored = [(item["index"], item["relevance_score"]) for item in data["results"]]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
