from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    vllm_url: str = "http://127.0.0.1:8002/v1"
    vllm_model: str = "Phi-3.5-mini-instruct"
    hf_token: str | None = None
    agent_api_url: str = "http://127.0.0.1:8100"
    storage_dir: str = "storage"
    public_base_url: str = "http://localhost:8100"
    cors_origins: str = "http://localhost:3000"
    max_tool_iterations: int = 5
    vllm_tools_enabled: bool = False

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
        options = f"-c search_path={self.salescloser_schema}"
        return (
            f"postgresql://{user}:{password}@{self.db_host}:{self.db_port}/"
            f"{self.db_name}?options={quote_plus(options)}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
