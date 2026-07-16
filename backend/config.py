from pathlib import Path
from urllib.parse import quote, quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = ""
    db_name: str = "gptenterprice"
    db_schema: str = "gptenterprice"
    salescloser_schema: str = "public"
    database_url: str | None = None

    # CRM (opcional — si no se define, se lee api-crm-admin-process/.env)
    crm_host: str | None = None
    crm_port: int | None = None
    crm_user: str | None = None
    crm_password: str | None = None
    crm_db: str | None = None

    vllm_url: str = "http://127.0.0.1:8002/v1"
    vllm_model: str = "Phi-3.5-mini-instruct"
    vllm_api_key: str | None = None
    hf_token: str | None = None

    @property
    def bearer_api_key(self) -> str | None:
        for candidate in (self.vllm_api_key, self.hf_token):
            if candidate and str(candidate).strip():
                return str(candidate).strip()
        return None
    agent_api_url: str = "http://127.0.0.1:8100"
    storage_dir: str = "storage"
    public_base_url: str = "http://localhost:8100"
    cors_origins: str = "http://localhost:3000"
    max_tool_iterations: int = 5
    vllm_tools_enabled: bool = False
    # Presenton (presentaciones PPTX/PDF self-hosted)
    presenton_url: str | None = None
    presenton_username: str | None = None
    presenton_password: str | None = None
    presenton_default_template: str = "neo-general"
    # Si true, no devolver editar_url de Presenton al usuario (solo backend habla con :5001).
    presenton_internal: bool = True
    # Si false, no intenta tool-calling nativo en vLLM (útil con parser hermes pendiente).
    vllm_native_tools: bool = True
    # Si false (default cuando vllm_tools_enabled=true), el LLM elige tools; no regex sync.
    sync_tools_enabled: bool | None = None

    @property
    def use_sync_tools(self) -> bool:
        if self.sync_tools_enabled is not None:
            return self.sync_tools_enabled
        return not self.vllm_tools_enabled

    @property
    def postgres_dsn(self) -> str:
        if self.database_url:
            return self.database_url

        password = quote_plus(self.db_password)
        user = quote_plus(self.db_user)
        return f"postgresql://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}?schema={self.db_schema}"

    @property
    def salescloser_dsn(self) -> str:
        """DSN para tablas de Qontrol/SalesCloser en schema public."""
        if self.database_url and "schema=" not in self.database_url:
            return self.database_url

        password = quote_plus(self.db_password)
        user = quote_plus(self.db_user)
        # quote (no quote_plus): libpq no decodifica '+' como espacio
        options = quote(f"-c search_path={self.salescloser_schema}")
        return (
            f"postgresql://{user}:{password}@{self.db_host}:{self.db_port}/"
            f"{self.db_name}?options={options}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def storage_path(self) -> Path:
        candidate = Path(self.storage_dir)
        if candidate.is_absolute():
            return candidate.resolve()
        return (_BACKEND_ROOT / candidate).resolve()


settings = Settings()
