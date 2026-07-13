"""MathForge 配置管理。

从环境变量（.env 文件）加载配置，提供类型安全的访问入口。
"""
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
STATIC_DIR = PROJECT_ROOT / "app" / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False

    database_path: str = "data/vault.db"

    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "deepseek-chat"

    paddleocr_api_url: str = ""
    paddleocr_token: SecretStr = SecretStr("")

    prompts_dir: str = "prompts"

    @property
    def db_path(self) -> Path:
        return PROJECT_ROOT / self.database_path

    @property
    def prompts_path(self) -> Path:
        return PROJECT_ROOT / self.prompts_dir

    @property
    def raw_path(self) -> Path:
        return PROJECT_ROOT / "raw"

    @property
    def outputs_path(self) -> Path:
        return PROJECT_ROOT / "outputs"

    @property
    def backups_path(self) -> Path:
        return PROJECT_ROOT / ".backups"

    @property
    def uploads_path(self) -> Path:
        return PROJECT_ROOT / "data" / "uploads"

    def get_llm_api_key(self) -> str:
        """取 LLM API Key 明文（仅在调用 LLM 时使用）。"""
        return self.llm_api_key.get_secret_value()

    def get_paddleocr_token(self) -> str:
        """取 PaddleOCR Token 明文（仅在调用 OCR 时使用）。"""
        return self.paddleocr_token.get_secret_value()


settings = Settings()
