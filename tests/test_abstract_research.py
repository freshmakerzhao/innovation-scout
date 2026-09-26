import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from pilot_ext import abstract_research as flow


def source():
    return {"source_id": "S1", "openalex_id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/example",
            "url": "https://doi.org/10.1/example", "title": "Battery manufacture", "publication_date": "2025-01-01",
            "authors": ["A. Author"], "abstract": "A laboratory study of batteries. " * 6}


def test_fetch_discards_missing_abstracts_and_deduplicates(monkeypatch):
    words = source()["abstract"].split()
    inverted = {}
    for position, word in enumerate(words):
        inverted.setdefault(word, []).append(position)
    work = {"id": "https://openalex.org/W1", "doi": source()["doi"], "title": "Battery manufacture", "abstract_inverted_index": inverted}
    other = dict(work, id="https://openalex.org/W2", doi="https://doi.org/10.1/second")
    monkeypatch.setattr(flow.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: {"results": [work, work, {"id": "missing-abstract"}, other]}))
    result = flow.fetch_sources("sulfide solid-state batteries")
    assert len(result) == 2
    assert [s["source_id"] for s in result] == ["S1", "S2"]
    assert result[0]["abstract"] == " ".join(words)


def test_insufficient_sources_fail_before_writing(monkeypatch):
    monkeypatch.setattr(flow.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: {"results": []}))
    with pytest.raises(RuntimeError, match="Fewer than two"):
        flow.fetch_sources("battery manufacturing")


def test_document_loader_preserves_citable_url():
    from gpt_researcher.document.langchain_document import LangChainDocumentLoader

    docs = flow.source_documents([source()])
    loaded = asyncio.run(LangChainDocumentLoader(docs).load())
    assert loaded[0]["url"] == source()["url"]
    assert "ABSTRACT ONLY" in loaded[0]["raw_content"]


def test_citations_must_belong_to_evidence():
    content = "This remains preliminary evidence. " * 10
    assert flow.validate_report(content + f"[study]({source()['url']})", [source()]) == [source()["url"]]
    with pytest.raises(RuntimeError, match="citations"):
        flow.validate_report(content, [source()])
    with pytest.raises(RuntimeError, match="outside the evidence"):
        flow.validate_report(content + "[invented](https://doi.org/10.1/invented)", [source()])
    assert flow.validate_report(content + f"来源：`{source()['url']}`；", [source()]) == [source()["url"]]


def test_empty_context_cannot_be_saved_as_success(monkeypatch, tmp_path):
    class EmptyResearcher:
        def __init__(self, **kwargs):
            self.cfg = SimpleNamespace(llm_kwargs={})

        async def conduct_research(self):
            return []

        async def write_report(self, **kwargs):
            pytest.fail("Must not generate a report without evidence")

    monkeypatch.setattr(flow, "GPTResearcher", EmptyResearcher)
    monkeypatch.setattr(flow, "fetch_sources", lambda *a: [source()])
    with pytest.raises(RuntimeError, match="No source context"):
        asyncio.run(flow.run_abstract_research("battery question", tmp_path, "battery manufacturing"))
    assert not list(tmp_path.glob("*.md"))
    manifest = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"


def test_long_question_is_not_sent_as_search():
    with pytest.raises(ValueError):
        flow.normalize_keywords("What manufacturing challenges are reported for sulfide solid state batteries please cite all sources and distinguish validation")


def test_prefetched_plan_never_repeats_web_search(monkeypatch):
    from gpt_researcher.skills import researcher as upstream

    async def unexpected(*args, **kwargs):
        pytest.fail("Prefetched abstracts must not trigger another web search")

    monkeypatch.setattr(upstream, "get_search_results", unexpected)
    assert asyncio.run(flow.AbstractConductor(SimpleNamespace()).plan_research("long original question")) == []
