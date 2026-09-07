from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "SentinelOps AI Engine"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    DEFAULT_TARGET_REPO: str = "C:/pythonlogger"

    # Ollama / LLM Configuration (runs locally — no API key needed)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # Chat model backing the reasoning/tool-calling nodes (repro, triage, code fix).
    # "ollama" (default, fully local) or "gemini" (needs GOOGLE_API_KEY).
    # Embeddings always stay on Ollama regardless of this setting — see app/ai/llm.py.
    LLM_PROVIDER: str = "ollama"
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Database Settings (Postgres + pgvector)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/triage_db"

    # GitHub Credentials (Mandatory for PR generation)
    GITHUB_TOKEN: str 
    GITHUB_REPO: str 

    # Slack Integration (Optional: App might only use GitHub/Jira)
    SLACK_BOT_TOKEN: str | None = None
    SLACK_SIGNING_SECRET: str | None = None
    
    # Jira Integration (Optional)
    JIRA_DOMAIN: str | None = None
    JIRA_EMAIL: str | None = None
    JIRA_API_TOKEN: str | None = None
    JIRA_PROJECT_KEY: str = "BUG" # Safe to keep a default string if Jira is used

    # FastMCP Server / Sandbox Configuration
    MCP_SERVER_HOST: str = "0.0.0.0"
    MCP_SERVER_PORT: int = 8001

    # Webhook Authentication
    # Shared-secret header required on /api/webhook/bug_report (see app/api/webhooks.py).
    WEBHOOK_SECRET: str

    # GitHub PR defaults
    GITHUB_BASE_BRANCH: str = "main"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()