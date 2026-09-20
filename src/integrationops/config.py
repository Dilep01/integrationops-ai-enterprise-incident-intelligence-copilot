from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTEGRATIONOPS_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./.data/integrationops.db"
    checkpoint_path: str = ".data/checkpoints.sqlite3"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "integrationops_knowledge"
    retrieval_backend: str = "hybrid_local"
    embedding_provider: str = "hashing"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_provider: str = "lexical"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieval_candidate_limit: int = 12
    retrieval_max_chunks_per_document: int = 1
    default_tenant_id: str = "demo-enterprise"
    default_roles: str = "integration-engineer,support-engineer"
    knowledge_dir: str = "data/demo/knowledge"
    llm_provider: str = "mock"
    llm_model: str = "deterministic-phase-3"
    llm_base_url: str = "http://localhost:11434/v1"
    ollama_base_url: str = "http://localhost:11434"
    llm_api_key: SecretStr | None = None
    llm_timeout_seconds: float = 30.0
    auth_mode: str = "headers"
    telemetry_service_name: str = "integrationops-api"
    remediation_provider: str = "sandbox"
    remediation_base_url: str = "http://127.0.0.1:8081"
    remediation_api_key: SecretStr | None = None
    remediation_timeout_seconds: float = 2.0
    remediation_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
