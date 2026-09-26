"""Run the MiMo pilot with explicit model routing and local embeddings."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
PROFILE = ROOT / "configs" / "mimo-flash.json"
BASE_URL = "https://api.xiaomimimo.com/v1"


def configure(env_file: Path | None = None) -> dict:
    from dotenv import load_dotenv

    load_dotenv(env_file or ROOT / ".env", override=False)
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    # This entry point deliberately overrides any inherited GPT/default routing.
    profile["EMBEDDING_KWARGS"]["cache_dir"] = str(ROOT / ".cache" / "fastembed")
    for key, value in profile.items():
        os.environ[key] = json.dumps(value) if isinstance(value, (dict, list, bool)) else str(value)
    for legacy in ("LLM_PROVIDER", "FAST_LLM_MODEL", "SMART_LLM_MODEL", "EMBEDDING_PROVIDER"):
        os.environ.pop(legacy, None)
    os.environ["OPENAI_BASE_URL"] = BASE_URL
    os.environ["OPENAI_API_KEY"] = os.environ.get("MIMO_API_KEY", "")
    os.environ["CONFIG_PATH"] = str(PROFILE)
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    return profile


def estimate_cny(usage: dict | None) -> float | None:
    """MiMo Flash CNY price, verified 2026-09-26; tokens come from the API."""
    if not usage or "input_tokens" not in usage or "output_tokens" not in usage:
        return None
    cached = (usage.get("input_token_details") or {}).get("cache_read", 0) or 0
    incoming = usage["input_tokens"]
    cached = min(max(cached, 0), incoming)
    return ((incoming - cached) + cached * 0.02 + usage["output_tokens"] * 2) / 1_000_000


async def probe(profile: dict) -> None:
    from gpt_researcher.utils.llm import get_llm

    provider = get_llm(
        "openai", model="mimo-v2.6-flash", max_tokens=400,
        temperature=0.2, verbose=False, **profile["LLM_KWARGS"],
    )
    prompt = [
        {"role": "system", "content": "Return only valid JSON with keys summary and source_id. Do not invent facts."},
        {"role": "user", "content": "Summarize in Chinese: Source S1 describes a laboratory battery experiment; no commercial validation is reported. Preserve source_id S1."},
    ]
    result = await provider.get_chat_response(
        prompt, stream=False, response_format={"type": "json_object"},
    )
    parsed = json.loads(result)
    if parsed.get("source_id") != "S1" or not isinstance(parsed.get("summary"), str) or not parsed["summary"].strip():
        raise RuntimeError("Structured-output/source-id check failed.")
    first_usage = provider.last_usage_metadata
    streamed = await provider.get_chat_response(
        [{"role": "user", "content": "Reply with the single word OK."}], stream=True,
    )
    if not streamed.strip():
        raise RuntimeError("Streaming response was empty.")
    output = {
        "model": "mimo-v2.6-flash", "structured_output": parsed,
        "streaming": streamed.strip(),
        "usage": [first_usage, provider.last_usage_metadata],
        "estimated_cny": [estimate_cny(first_usage), estimate_cny(provider.last_usage_metadata)],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


async def research(query: str, keywords: str | None = None) -> None:
    from pilot_ext.abstract_research import run_abstract_research

    await run_abstract_research(query, ROOT / "outputs", keywords)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "probe", "embeddings", "research", "serve"])
    parser.add_argument("--query", help="Research question; English search terms help OpenAlex retrieval.")
    parser.add_argument("--keywords", help="Optional 2-12 English search words; otherwise MiMo plans a short query.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    profile = configure()
    if args.command == "check":
        print(json.dumps({
            "base_url": BASE_URL, "model": profile["SMART_LLM"],
            "embedding": profile["EMBEDDING"], "retriever": profile["RETRIEVER"],
            "mimo_key_present": bool(os.environ.get("MIMO_API_KEY")),
            "openalex_key_present": bool(os.environ.get("OPENALEX_API_KEY")),
            "thinking": "disabled", "config": str(PROFILE),
        }, indent=2))
        return 0
    if args.command == "embeddings":
        from gpt_researcher.memory.embeddings import Memory

        provider, model = profile["EMBEDDING"].split(":", 1)
        embeddings = Memory(provider, model, **profile["EMBEDDING_KWARGS"]).get_embeddings()
        vector = embeddings.embed_query("battery manufacturing")
        print(f"Local CPU embedding ready: {len(vector)} dimensions")
        return 0
    if not os.environ.get("MIMO_API_KEY", "").strip():
        print("Missing MIMO_API_KEY. Set it in the repository .env (do not send keys in chat).", file=sys.stderr)
        return 2
    os.chdir(APP)
    if args.command == "probe":
        asyncio.run(asyncio.wait_for(probe(profile), timeout=150))
    elif args.command == "research":
        if not args.query:
            parser.error("research requires --query")
        # Elapsed-time limit only; this is NOT a monetary spend cap.
        asyncio.run(asyncio.wait_for(research(args.query, args.keywords), timeout=600))
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("main:app", host="127.0.0.1", port=args.port, workers=1)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Provider exceptions can contain request data; avoid echoing credentials.
        print(f"MiMo check failed ({type(exc).__name__}). Check network, API balance, model access, and dependencies.", file=sys.stderr)
        raise SystemExit(1)
