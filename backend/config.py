"""Central configuration. All secrets come from environment / .env — never hardcoded.

We deliberately keep ONE source of settings so every module (db, ade, llm, pipeline)
reads the same values. Uses pydantic-settings so the .env your colleague already
defined (.env.example) loads automatically.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Supabase (Postgres + Storage + pgvector, all in one managed service) ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""          # service role — backend only, NEVER ship to the dashboard
    storage_bucket: str = "evidence"

    # --- LandingAI ADE ---
    landingai_api_key: str = ""

    # --- LLM routing (LiteLLM model strings). Swap freely; agents don't care. ---
    llm_reasoning_model: str = "anthropic/claude-sonnet-4-5"   # summaries, anomaly reasoning
    llm_fast_model: str = "anthropic/claude-haiku-4-5"         # classification, cheap calls
    llm_embedding_model: str = "openai/text-embedding-3-small" # RAG embeddings

    # RAG
    rag_top_k: int = 8


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # The agentic-doc SDK reads VISION_AGENT_API_KEY from the environment.
    # We bridge the colleague's variable name (LANDINGAI_API_KEY) to it so there is
    # a single key to manage in .env.
    if s.landingai_api_key and not os.getenv("VISION_AGENT_API_KEY"):
        os.environ["VISION_AGENT_API_KEY"] = s.landingai_api_key
    return s
