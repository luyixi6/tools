import os
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

CONFIG_FILENAME = "config.yaml"
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / CONFIG_FILENAME


class ApiConfig(BaseModel):
    provider: str = "anthropic"
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    max_tokens: int = 8192
    extra_headers: Dict[str, str] = Field(default_factory=dict)

    def effective_model(self) -> str:
        if self.model:
            return self.model
        from .llm.client_factory import SUPPORTED_PROVIDERS
        info = SUPPORTED_PROVIDERS.get(self.provider, {})
        return info.get("default_model", "gpt-4o")


class ProjectConfig(BaseModel):
    root: str = ""
    compile_commands: str = ""
    exclude_dirs: List[str] = Field(default_factory=lambda: [
        "build", "third_party", ".git", "node_modules",
        "cmake-build-debug", "cmake-build-release"
    ])
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        "*.pb.h", "*.pb.cc", "moc_*", "ui_*.h"
    ])


class ToolsConfig(BaseModel):
    clang_tidy: bool = True
    cppcheck: bool = True


class AnalysisConfig(BaseModel):
    static_check: bool = True
    dynamic_check: bool = True
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    rules: List[str] = Field(default_factory=lambda: [
        "memory_safety", "concurrency", "exception_safety",
        "modern_cpp", "code_style"
    ])


class ChunkingConfig(BaseModel):
    strategy: str = "auto"
    max_tokens_per_batch: int = 80000
    max_file_tokens: int = 30000


class BatchConfig(BaseModel):
    concurrent_modules: int = 2
    rate_limit_rpm: int = 50


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class AppConfig(BaseModel):
    language: str = "en"
    api: ApiConfig = Field(default_factory=ApiConfig)
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    batch: BatchConfig = Field(default_factory=BatchConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def _resolve_config_path(config_path: Optional[str] = None) -> Path:
    if config_path:
        return Path(config_path)
    return _DEFAULT_CONFIG_PATH


def load_config(config_path: Optional[str] = None) -> AppConfig:
    path = _resolve_config_path(config_path)
    if not path.exists():
        return AppConfig()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return AppConfig()
        return AppConfig(**data)
    except (UnicodeDecodeError, yaml.YAMLError, Exception):
        return AppConfig()


def save_config(config: AppConfig, config_path: Optional[str] = None) -> Path:
    path = _resolve_config_path(config_path)
    data = config.model_dump(exclude_defaults=False)
    yaml_data = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)

    tmp_path = path.with_suffix(".yaml.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(yaml_data)
    os.replace(str(tmp_path), str(path))
    return path


_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Optional[str] = None) -> AppConfig:
    global _config
    _config = load_config(config_path)
    return _config
