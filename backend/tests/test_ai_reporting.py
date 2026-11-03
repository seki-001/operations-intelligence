import json

import httpx

from app.services.ai_reporting import (OpenAICompatibleProvider, Summary, TemplateProvider,
                                       check_against_facts, summarise)

FACTS = {
    "period": "2026-10-26 to 2026-11-01 compared with 2026-10-19 to 2026-10-25",
    "facts": [
        {"id": "P2", "text": "Portfolio collection rate: 87.0% (previous period 92.3%)."},
        {"id": "F1", "text": "Lakeshore: average uptime 84.9% (target 95%), 19 outage events."},
        {"id": "F2", "text": "Market Town: collected 72.1% of billed revenue (below the 75% critical line)."},
    ],
}


def fake_llm(content: str, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        sent = json.loads(request.content)
        assert "Lakeshore" in sent["messages"][1]["content"]  # facts are sent, nothing else
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def provider(content, status=200):
    return OpenAICompatibleProvider("https://llm.example/v1", "m", "k", client=fake_llm(content, status))


def test_template_is_labelled_not_ai():
    s = summarise(FACTS, TemplateProvider())
    assert s.is_ai_generated is False and s.provider == "template"
    assert s.observations[0]["fact_ids"] == ["F1"]
    assert s.unverified_numbers == []


def test_ai_output_with_supported_numbers_passes():
    out = json.dumps({
        "observations": [{"text": "Lakeshore uptime was 84.9% with 19 outage events.", "fact_ids": ["F1"]}],
        "hypotheses": [{"text": "Possibly a battery fault.", "fact_ids": ["F1"]}],
        "suggested_checks": ["Ask the site team about battery health."],
    })
    s = summarise(FACTS, provider(out))
    assert s.is_ai_generated is True
    assert s.unverified_numbers == [] and s.unknown_fact_ids == []


def test_invented_numbers_and_fact_ids_are_flagged():
    out = json.dumps({
        "observations": [{"text": "Revenue fell by 2,450.75 USD, about 31% lower.", "fact_ids": ["F9"]}],
        "hypotheses": [], "suggested_checks": [],
    })
    s = summarise(FACTS, provider(out))
    assert s.unverified_numbers == ["2450.75", "31"]
    assert s.unknown_fact_ids == ["F9"]


def test_model_failure_falls_back_to_labelled_template():
    s = summarise(FACTS, provider("{}", status=500))
    assert s.is_ai_generated is False
    assert "AI call failed" in s.fallback_reason


def test_malformed_json_falls_back():
    s = summarise(FACTS, provider("not json at all"))
    assert s.is_ai_generated is False


def test_code_fenced_json_is_accepted():
    out = "```json\n" + json.dumps({"observations": [{"text": "ok", "fact_ids": ["P2"]}]}) + "\n```"
    s = summarise(FACTS, provider(out))
    assert s.is_ai_generated is True and s.observations[0]["text"] == "ok"


def test_small_counts_are_not_claims():
    s = Summary([{"text": "3 sites need attention", "fact_ids": []}], [], [], "x", None, True)
    assert check_against_facts(s, FACTS).unverified_numbers == []


def test_retries_without_json_mode_when_model_rejects_it():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "json mode not supported"})
        content = json.dumps({"observations": [{"text": "ok", "fact_ids": ["F1"]}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    p = OpenAICompatibleProvider("https://llm.example/v1", "m", "k",
                                 client=httpx.Client(transport=httpx.MockTransport(handler)))
    s = summarise(FACTS, p)
    assert calls == [True, False] and s.is_ai_generated is True
