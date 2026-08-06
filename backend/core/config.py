"""Central configuration. All secrets come from environment / .env — never hardcoded.

We deliberately keep ONE source of settings so every module (db, ade, llm, pipeline)
reads the same values. Uses pydantic-settings so the .env your colleague already
defined (.env.example) loads automatically.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Supabase (Postgres + Storage + pgvector, all in one managed service) ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""          # service role — backend only, NEVER ship to the dashboard
    storage_bucket: str = "evidence"

    # --- Supabase Auth (server-side JWT verification) ---
    # Find in: Supabase Dashboard → Project Settings → API → JWT Settings → JWT Secret
    supabase_jwt_secret: str = ""

    # --- LandingAI ADE ---
    landingai_api_key: str = ""
    # Set MOCK_ADE=true to skip real API calls and return plausible fake extraction data.
    # Use this when the LandingAI account is on the free plan or during UI/pipeline testing.
    mock_ade: bool = False

    # --- LLM routing (LiteLLM model strings). Swap freely; agents don't care. ---
    llm_reasoning_model: str = "groq/llama-3.3-70b-versatile"  # summaries, anomaly reasoning, chat
    llm_fast_model: str = "groq/llama-3.1-8b-instant"          # classification, cheap calls
    llm_embedding_model: str = "gemini/gemini-embedding-001" # RAG embeddings (Gemini)
    # Whole-case cross-document reasoning (entities/relationships/timeline/findings LLM pass).
    # Separate from the "reasoning" tier above so it can be tuned independently (bigger prompts,
    # different model) even though both currently point at the same Groq model.
    llm_case_reasoning_model: str = "groq/llama-3.3-70b-versatile"

    # --- API Keys (LiteLLM reads these from os.environ) ---
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # RAG
    rag_top_k: int = 8

    # --- CORS ---
    # Comma-separated list of browser origins allowed to call the API. Defaults to "*"
    # (permissive — fine for local dev). Set CORS_ALLOW_ORIGINS to the real dashboard origin(s)
    # before any deployment, e.g. "https://app.example.com,https://staging.example.com".
    cors_allow_origins: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()] or ["*"]

    # --- Multi-tenancy ---
    # Comma-separated list of emails that have platform admin access (NextGen Spark team).
    # Stored as str (same pattern as cors_allow_origins) so pydantic_settings never tries to
    # JSON-parse it — avoids a crash when the env var is empty or missing.
    platform_admin_emails_raw: str = Field(
        default="nextgenspark2025@gmail.com,hello@nextgenspark.solutions",
        alias="PLATFORM_ADMIN_EMAILS",
    )

    @property
    def platform_admin_emails(self) -> list[str]:
        return [e.strip() for e in self.platform_admin_emails_raw.split(",") if e.strip()]

    # --- Email (Resend) ---
    # Leave empty to disable email sending (invitations will still work via copy-link).
    resend_api_key: str = ""
    # Sender address. Use onboarding@resend.dev for testing without a domain.
    # Switch to noreply@yourdomain.com once a domain is verified in Resend dashboard.
    resend_from_email: str = "onboarding@resend.dev"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # The agentic-doc SDK reads VISION_AGENT_API_KEY from the environment.
    # We bridge the colleague's variable name (LANDINGAI_API_KEY) to it so there is
    # a single key to manage in .env.
    if s.landingai_api_key and not os.getenv("VISION_AGENT_API_KEY"):
        os.environ["VISION_AGENT_API_KEY"] = s.landingai_api_key
    # LiteLLM reads provider keys directly from os.environ — bridge from pydantic settings.
    if s.groq_api_key and not os.getenv("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = s.groq_api_key
    if s.gemini_api_key and not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = s.gemini_api_key
    return s
