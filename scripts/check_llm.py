"""Check that the configured models work with the API key in THIS environment.

Replaces the old root-level test_llm.py, which printed the API key into the terminal and imported
a module that no longer exists.

The point of running it is the environment it runs in. A model confirmed on a laptop still failed
in production on 13 Sept with `model_not_found`, because the deployed key was not the local one.
So run it where the key you care about lives:

    python scripts/check_llm.py                     # the key in your .env
    railway run python scripts/check_llm.py         # the key production uses

Each tier costs one tiny request. Exits non-zero if anything failed, so CI can use it too.
"""
from __future__ import annotations

import sys

# The DB column both chunk tables use — an embedding model of a different width cannot be stored,
# and one of the same width from a different provider stores fine but makes search meaningless.
_EXPECTED_EMBEDDING_DIMENSIONS = 1536


def main() -> int:
    from backend.core import llm
    from backend.core.config import get_settings

    settings = get_settings()
    # Presence only. The value never reaches the terminal.
    present = {
        "OPENAI_API_KEY": bool(settings.openai_api_key),
        "GROQ_API_KEY": bool(settings.groq_api_key),
        "GEMINI_API_KEY": bool(settings.gemini_api_key),
    }
    print("keys configured:", ", ".join(f"{name}={'yes' if ok else 'NO'}" for name, ok in present.items()))
    print()

    failures = 0
    tiers = (
        ("reasoning", settings.llm_reasoning_model),
        ("fast", settings.llm_fast_model),
        ("case_reasoning", settings.llm_case_reasoning_model),
    )
    for tier, model in tiers:
        try:
            answer = llm.complete(
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                tier=tier,
            )
            print(f"  OK      {tier:15} {model} -> {answer.strip()[:40]!r}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAILED  {tier:15} {model} -> {type(exc).__name__}: {str(exc)[:200]}")

    try:
        vectors = llm.embed(["hello world"])
        width = len(vectors[0])
        print(f"  OK      {'embeddings':15} {settings.llm_embedding_model} -> {width} dimensions")
        if width != _EXPECTED_EMBEDDING_DIMENSIONS:
            failures += 1
            print(f"  FAILED  embeddings are {width}-dimensional but the chunks tables are "
                  f"vector({_EXPECTED_EMBEDDING_DIMENSIONS}) — indexing will fail.")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        print(f"  FAILED  {'embeddings':15} {settings.llm_embedding_model} -> "
              f"{type(exc).__name__}: {str(exc)[:200]}")

    print()
    if failures:
        print(f"{failures} check(s) failed.")
    else:
        print("All checks passed. Note: changing the embedding MODEL (not just its width) makes "
              "every document indexed under the old one unsearchable until it is re-extracted.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
