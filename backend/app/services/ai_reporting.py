"""Narrative summary of the period, written from pre-calculated facts only.

Guardrails:
  1. The model only sees aggregated facts (site-level totals and findings), never raw rows or
     customer data, and every fact has an ID it must cite.
  2. Output is split into observations (backed by facts) and hypotheses (possible explanations,
     clearly labelled as unconfirmed).
  3. Every number in the output is checked against the facts. Unmatched numbers are flagged.
  4. Reports are saved as "pending review" and need a named person to approve them.
  5. Without a configured model, a template summary is produced and labelled as NOT AI.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import Settings

log = logging.getLogger(__name__)


@dataclass
class Summary:
    observations: list[dict]
    hypotheses: list[dict]
    suggested_checks: list[str]
    provider: str
    model: str | None
    is_ai_generated: bool
    fallback_reason: str | None = None
    unverified_numbers: list[str] = field(default_factory=list)
    unknown_fact_ids: list[str] = field(default_factory=list)


class SummaryProvider(Protocol):
    def generate(self, facts: dict) -> Summary: ...


# --------------------------------------------------------------------------- facts

def build_facts(comparison: dict) -> dict:
    """Turn analytics output into a short list of citable facts."""
    if not comparison.get("portfolio"):
        return {"period": None, "facts": []}
    cur = comparison["portfolio"]["current"]
    prev = comparison["portfolio"]["previous"]
    facts = [
        {"id": "P1", "text": f"Portfolio energy sold: {cur['energy_sold_kwh']:,.1f} kWh "
                             f"(previous period {prev['energy_sold_kwh']:,.1f} kWh)."},
        {"id": "P2", "text": f"Portfolio collection rate: {cur['collection_rate_pct']}% "
                             f"(previous period {prev['collection_rate_pct']}%)."},
        {"id": "P3", "text": f"Portfolio collected revenue: ${cur['collected_usd']:,.2f} of "
                             f"${cur['billed_usd']:,.2f} billed."},
        {"id": "P4", "text": f"Portfolio average uptime: {cur['avg_uptime_pct']}% "
                             f"(previous period {prev['avg_uptime_pct']}%)."},
        {"id": "P5", "text": f"Portfolio unsold energy share: {cur['loss_pct']}% "
                             f"(previous period {prev['loss_pct']}%)."},
        {"id": "P6", "text": f"New connections this period: {cur['new_connections']}; "
                             f"active customers at period end: {cur['active_customers']}."},
    ]
    facts += [{"id": f["id"], "text": f["statement"], "severity": f["severity"]}
              for f in comparison.get("findings", []) if f["site_id"] != "ALL"]
    cp = comparison["current_period"]
    pp = comparison["previous_period"]
    return {"period": f"{cp['start']} to {cp['end']} compared with {pp['start']} to {pp['end']}",
            "facts": facts}


# --------------------------------------------------------------------------- guardrail

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalise(num: str) -> str:
    n = num.replace(",", "")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def _numbers_in(text: str) -> set[str]:
    return {_normalise(m) for m in _NUMBER.findall(text)}


def check_against_facts(summary: Summary, facts: dict) -> Summary:
    allowed: set[str] = set()
    for f in facts["facts"]:
        allowed |= _numbers_in(f["text"])
    allowed |= _numbers_in(facts.get("period") or "")
    known_ids = {f["id"] for f in facts["facts"]}

    unverified: set[str] = set()
    unknown_ids: set[str] = set()
    for item in summary.observations + summary.hypotheses:
        for num in _numbers_in(item.get("text", "")):
            # Small counts ("two sites", "3 checks") are not treated as claims.
            if num not in allowed and not (num.isdigit() and int(num) <= 10):
                unverified.add(num)
        for fid in item.get("fact_ids", []):
            if fid not in known_ids:
                unknown_ids.add(fid)
    summary.unverified_numbers = sorted(unverified)
    summary.unknown_fact_ids = sorted(unknown_ids)
    return summary


# --------------------------------------------------------------------------- providers

_HYPOTHESES = {
    "collection_rate_pct": "Collections may be lagging because of payment-channel issues, delayed "
                           "mobile-money settlement, or customers on credit.",
    "avg_uptime_pct": "Lower uptime may relate to battery or inverter faults, maintenance, or "
                      "weather reducing solar input.",
    "loss_pct": "A higher unsold share may reflect technical losses, meter faults, or "
                "unmetered consumption.",
    "energy_sold_kwh": "A change in energy sold may follow uptime changes, new connections, or "
                       "changes in customer demand.",
    "days_reported": "Missing days usually mean a reporting gap, not zero activity.",
}


class TemplateProvider:
    """Deterministic summary with no language model. Always labelled as not AI-generated."""

    def __init__(self, fallback_reason: str | None = None):
        self.fallback_reason = fallback_reason

    def generate(self, facts: dict) -> Summary:
        findings = [f for f in facts["facts"] if not f["id"].startswith("P")]
        observations = [{"text": f["text"], "fact_ids": [f["id"]]} for f in findings[:6]]
        if not observations:
            observations = [{"text": facts["facts"][1]["text"], "fact_ids": ["P2"]}] if facts["facts"] else []
        hypotheses, seen = [], set()
        for f in findings:
            metric = _metric_of(f["text"])
            if metric and metric not in seen:
                seen.add(metric)
                hypotheses.append({"text": _HYPOTHESES[metric], "fact_ids": [f["id"]]})
        checks = ["Confirm flagged sites with the site operations team before acting.",
                  "Review rejected rows in the data-quality panel and correct them in the source sheet."]
        return Summary(observations, hypotheses[:4], checks, provider="template", model=None,
                       is_ai_generated=False, fallback_reason=self.fallback_reason)


def _metric_of(text: str) -> str | None:
    t = text.lower()
    if "collect" in t:
        return "collection_rate_pct"
    if "uptime" in t:
        return "avg_uptime_pct"
    if "unsold" in t or "not sold" in t:
        return "loss_pct"
    if "energy sold" in t:
        return "energy_sold_kwh"
    if "no valid data" in t:
        return "days_reported"
    return None


SYSTEM_PROMPT = """You write short operational briefings for the leadership of a solar mini-grid operator.
Rules:
- Use ONLY the facts provided. Do not introduce any number that is not in the facts. Do not calculate new numbers.
- Every observation and hypothesis must cite the fact IDs it relies on.
- "observations" state what the facts show. "hypotheses" are possible explanations and must be worded as possibilities, never as conclusions.
- "suggested_checks" are concrete things a person should verify. Never suggest changing billing, tariffs or site controls directly.
- Be concise: at most 5 observations, 4 hypotheses, 4 checks.
Return JSON only, in this shape:
{"observations":[{"text":"...","fact_ids":["F1"]}],"hypotheses":[{"text":"...","fact_ids":["F1"]}],"suggested_checks":["..."]}"""


class OpenAICompatibleProvider:
    """Works with any OpenAI-compatible chat endpoint (e.g. Groq, Google AI Studio's
    OpenAI-compatible endpoint, OpenRouter, or a local Ollama server)."""

    def __init__(self, base_url: str, model: str, api_key: str, timeout: float = 30.0,
                 client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.client = client

    def generate(self, facts: dict) -> Summary:
        payload: dict = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code == 400:
                # Some models don't support JSON mode; the prompt still asks for JSON only.
                payload.pop("response_format", None)
                resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(_strip_fences(content))
        finally:
            if self.client is None:
                client.close()
        return Summary(
            observations=_clean_items(data.get("observations")),
            hypotheses=_clean_items(data.get("hypotheses")),
            suggested_checks=[str(c) for c in (data.get("suggested_checks") or [])][:4],
            provider="openai_compatible", model=self.model, is_ai_generated=True,
        )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text


def _clean_items(items) -> list[dict]:
    out = []
    for item in (items or [])[:5]:
        if isinstance(item, dict) and item.get("text"):
            out.append({"text": str(item["text"]), "fact_ids": [str(x) for x in item.get("fact_ids", [])]})
    return out


def build_provider(settings: Settings) -> SummaryProvider:
    if settings.ai_provider == "openai_compatible" and settings.ai_api_key:
        return OpenAICompatibleProvider(settings.ai_base_url, settings.ai_model, settings.ai_api_key,
                                        settings.ai_timeout_seconds)
    reason = "No AI provider configured" if settings.ai_provider == "openai_compatible" else None
    return TemplateProvider(fallback_reason=reason)


def summarise(facts: dict, provider: SummaryProvider) -> Summary:
    """Generate and check a summary. If the model call fails, fall back to the
    labelled template rather than showing nothing, and say why."""
    try:
        summary = provider.generate(facts)
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
        reason = (f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
                  else type(exc).__name__)
        log.warning("AI summary failed, using template: %s", reason)
        summary = TemplateProvider(fallback_reason=f"AI call failed ({reason})").generate(facts)
    return check_against_facts(summary, facts)
