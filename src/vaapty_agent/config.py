"""Configuração central. Campos snake_case mapeiam automaticamente p/ env UPPER."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # OpenAI
    openai_api_key: str
    openai_model_updater: str = "gpt-4o"
    openai_model_responder: str = "gpt-4o"

    # GoHighLevel
    ghl_pit_token: str
    ghl_location_id: str
    ghl_api_host: str = "https://services.leadconnectorhq.com"
    ghl_api_version: str = "2021-07-28"

    # Custom Fields
    cf_status_ia: str
    cf_localizacao: str
    cf_veiculo_modelo: str
    cf_veiculo_ano: str
    cf_motivo_venda: str

    # FAQ Custom Value
    cv_faq: str

    # Gate
    tag_agent_ia: str = "agent-ia"
    tag_agent_ia_id: str = ""

    # Workflows
    workflow_qualificado_id: str = ""
    workflow_desqualificado_id: str = ""

    # Calendars
    calendar_adriano: str = ""
    calendar_dario: str = ""
    ghl_appointment_duration_min: int = 60

    # Webhook
    webhook_secret: str

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_timezone: str = "America/Sao_Paulo"

    # Postgres
    database_url: str = "postgresql+asyncpg://vaapty:vaapty@localhost:5432/vaapty"

    # Tuning
    faq_cache_ttl_seconds: int = 300
    conversation_history_limit: int = 100
    responder_max_bubbles: int = 4
    responder_sleep_min: float = 1.2
    responder_sleep_max: float = 2.8
    human_request_threshold: int = 3

    # Raio de qualificação (csv minúsculo, sem acento)
    qualify_cities: str = "guarulhos"

    # Logs / métricas
    log_level: str = "INFO"
    log_format: str = "json"
    metrics_enabled: bool = True

    @property
    def qualify_cities_set(self) -> set[str]:
        return {c.strip().lower() for c in self.qualify_cities.split(",") if c.strip()}


settings = Settings()  # singleton
