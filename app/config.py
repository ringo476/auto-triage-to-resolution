from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "SentinelOps AI Engine"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # OpenAI / LLM Credentials
    OPENAI_API_KEY: str  # No default = mandatory

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()