import json

import httpx
import pytest
from pydantic import BaseModel

from nexus import llm


class Answer(BaseModel):
    text: str


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "BACKOFF_SECONDS", 0)


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def chat_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_embed_batches_and_preserves_order() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["input"]
        batch_sizes.append(len(inputs))
        data = [
            {"index": i, "embedding": [float(text.removeprefix("t"))]}
            for i, text in enumerate(inputs)
        ]
        data.reverse()
        return httpx.Response(200, json={"data": data})

    vectors = llm.embed([f"t{i}" for i in range(70)], client=make_client(handler))
    assert batch_sizes == [32, 32, 6]
    assert len(vectors) == 70
    assert vectors[0] == [0.0]
    assert vectors[69] == [69.0]


def test_rerank_parses_results_sorted() -> None:
    body = {
        "results": [{"index": 1, "relevance_score": 0.2}, {"index": 0, "relevance_score": 0.96}]
    }
    client = make_client(lambda request: httpx.Response(200, json=body))
    assert llm.rerank("q", ["a", "b"], 2, client=client) == [(0, 0.96), (1, 0.2)]


def test_chat_json_retries_once_on_invalid() -> None:
    replies = iter(["not json", '{"text": "ok"}'])
    client = make_client(lambda request: chat_reply(next(replies)))
    assert llm.chat_json([{"role": "user", "content": "x"}], Answer, client=client) == Answer(
        text="ok"
    )


def test_chat_json_raises_when_always_invalid() -> None:
    client = make_client(lambda request: chat_reply("nope"))
    with pytest.raises(llm.GatewayError):
        llm.chat_json([{"role": "user", "content": "x"}], Answer, client=client)


def test_chat_text_returns_content() -> None:
    client = make_client(lambda request: chat_reply("hi"))
    assert llm.chat_text([{"role": "user", "content": "x"}], client=client) == "hi"


def test_http_500_raises_gateway_error_after_retries() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    with pytest.raises(llm.GatewayError):
        llm.embed(["a"], client=make_client(handler))
    assert len(calls) == 3


def test_http_400_is_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400)

    with pytest.raises(llm.GatewayError):
        llm.embed(["a"], client=make_client(handler))
    assert len(calls) == 1


class Item(BaseModel):
    name: str


class Bag(BaseModel):
    items: list[Item]


def test_chat_json_closes_nested_objects() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return chat_reply('{"items": []}')

    llm.chat_json([{"role": "user", "content": "x"}], Bag, client=make_client(handler))
    schema = bodies[0]["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["items"]
    assert schema["$defs"]["Item"]["additionalProperties"] is False
    assert schema["$defs"]["Item"]["required"] == ["name"]


def test_html_200_body_raises_gateway_error() -> None:
    client = make_client(lambda request: httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(llm.GatewayError):
        llm.chat_text([{"role": "user", "content": "x"}], client=client)


def test_missing_keys_raise_gateway_error() -> None:
    client = make_client(lambda request: httpx.Response(200, json={}))
    with pytest.raises(llm.GatewayError):
        llm.rerank("q", ["a"], 1, client=client)


def test_embed_without_data_raises_gateway_error() -> None:
    client = make_client(lambda request: httpx.Response(200, json={}))
    with pytest.raises(llm.GatewayError):
        llm.embed(["a"], client=client)


def test_embed_wrong_vector_count_raises_gateway_error() -> None:
    client = make_client(lambda request: httpx.Response(200, json={"data": []}))
    with pytest.raises(llm.GatewayError):
        llm.embed(["a"], client=client)


def test_429_is_retried() -> None:
    replies = iter([httpx.Response(429), chat_reply("ok")])
    client = make_client(lambda request: next(replies))
    assert llm.chat_text([{"role": "user", "content": "x"}], client=client) == "ok"


def test_rerank_empty_docs_makes_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert llm.rerank("q", [], 3, client=make_client(handler)) == []


@pytest.mark.live
def test_live_roundtrip() -> None:
    assert len(llm.embed(["tes"])[0]) == 1024


def test_chat_strips_think_blocks() -> None:
    client = make_client(lambda request: chat_reply("<think>hmm\nlines</think>\n\n  hi  "))
    assert llm.chat_text([{"role": "user", "content": "x"}], client=client) == "hi"


def test_chat_text_passes_timeout() -> None:
    seen: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions["timeout"]["read"])
        return chat_reply("ok")

    llm.chat_text([{"role": "user", "content": "x"}], timeout=300, client=make_client(handler))
    llm.chat_text([{"role": "user", "content": "x"}], client=make_client(handler))
    assert seen == [300, 120]


def test_chat_json_passes_timeout() -> None:
    seen: list[object] = []

    class Reply(BaseModel):
        ok: bool

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions["timeout"]["read"])
        return chat_reply('{"ok": true}')

    messages = [{"role": "user", "content": "x"}]
    llm.chat_json(messages, Reply, timeout=300, client=make_client(handler))
    llm.chat_json(messages, Reply, client=make_client(handler))
    assert seen == [300, 120]


def test_rerank_applies_qwen3_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANKER_TEMPLATE", "qwen3")
    llm.get_settings.cache_clear()
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.9}]})

    llm.rerank("siapa direktur?", ["Budi adalah Direktur Utama"], 1, client=make_client(handler))
    body = sent[0]
    assert body["query"].startswith("<|im_start|>system")
    assert "<Query>: siapa direktur?" in body["query"]
    assert body["documents"] == [f"<Document>: Budi adalah Direktur Utama{llm.QWEN3_RERANK_SUFFIX}"]


def test_rerank_raw_when_template_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANKER_TEMPLATE", "none")
    llm.get_settings.cache_clear()
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.9}]})

    try:
        llm.rerank("q", ["d"], 1, client=make_client(handler))
    finally:
        llm.get_settings.cache_clear()
    assert sent[0]["query"] == "q" and sent[0]["documents"] == ["d"]
