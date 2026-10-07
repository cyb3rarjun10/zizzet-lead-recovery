from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Zizzet AI Lead Recovery Engine"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./lead_recovery.db"
    LLM_PROVIDER: str = "gemini"  # "gemini" or "openai"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()