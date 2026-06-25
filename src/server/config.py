# -*- coding: utf-8 -*-
"""
全局配置（极简）

公开接口：
- `global_config`: 全局配置实例

内部方法：
- 无

说明：
- 支持 .env 与 .env.{APP_ENV} 加载
- 提供 CORS 允许源解析
"""

import json
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TEST_MOCK_PROVIDERS = [
    "github_oauth",
    "google_oauth",
    "turnstile",
    "mail",
    "example_external_api",
]

# 先加载 .env 和 .env.{APP_ENV}
load_dotenv(".env")
app_env = os.getenv("APP_ENV", "dev")
load_dotenv(f".env.{app_env}", override=True)


class GlobalConfig(BaseSettings):
    """全局配置"""

    app_env: str = Field(default="dev", title="应用环境")

    database_protocol: str = Field(default="sqlite", title="数据库协议")

    database_path: Path = Field(
        default=Path("data") / "database.db",
        title="数据库路径",
        description="相对项目根目录的相对路径",
    )

    app_secret_key: str = Field(
        default="dev_secret_key_for_testing_only",
        title="应用密钥",
        description="用于会话/签名等场景（可选）",
    )

    app_domain: str = Field(
        default="",
        title="应用域名",
        description="用于生成对外访问的链接（例如重置密码链接）",
    )

    project_root: Path = Field(
        default=Path.cwd(),
        title="项目根目录",
        description="相对项目根目录的相对路径",
    )

    log_level: str = Field(default="info", title="日志级别")

    log_dir: Path = Field(
        default=Path("logs"),
        title="日志目录",
        description="相对项目根目录的相对路径",
    )

    log_rotation: str = Field(
        default="20 MB",
        title="日志轮转策略",
        description="Loguru rotation 配置",
    )

    log_retention: str = Field(
        default="14 days",
        title="日志保留策略",
        description="Loguru retention 配置",
    )

    log_serialize: bool = Field(
        default=False,
        title="是否输出 JSON 日志",
    )

    def _parse_env_list(self, env_name: str, default: list[str]) -> list[str]:
        """解析环境变量列表，支持 JSON、逗号分隔或单值。"""
        env_value = os.getenv(env_name)
        if not env_value:
            return default
        try:
            parsed = json.loads(env_value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        if "," in env_value:
            return [item.strip() for item in env_value.split(",") if item.strip()]
        return [env_value.strip()] if env_value.strip() else default

    @property
    def allowed_origins(self) -> List[str]:
        """允许的跨域来源

        支持格式：
        1. JSON：ALLOWED_ORIGINS='["http://localhost:5173"]'
        2. 逗号分隔：ALLOWED_ORIGINS="http://localhost:5173,https://example.com"
        3. 单个值：ALLOWED_ORIGINS="*"
        4. 未设置：默认为 ["*"]
        """
        return self._parse_env_list("ALLOWED_ORIGINS", ["*"])

    @property
    def oauth_list(self) -> list[str]:
        """启用的 OAuth 渠道列表，格式同 ALLOWED_ORIGINS。"""
        return [
            provider.strip().upper()
            for provider in self._parse_env_list("OAUTH_LIST", [])
            if provider.strip()
        ]

    @property
    def external_provider_mock_list(self) -> list[str]:
        """使用 mock service 的外部 provider 列表，格式同 ALLOWED_ORIGINS。"""
        default = DEFAULT_TEST_MOCK_PROVIDERS if self.app_env == "test" else []
        return [
            provider.strip().lower()
            for provider in self._parse_env_list("EXTERNAL_PROVIDER_MOCK_LIST", default)
            if provider.strip()
        ]

    example_external_api_base_url: str = Field(
        default="",
        title="示例外部 API Base URL",
    )

    info_distribution_base_url: str = Field(
        default="",
        title="Info Distribution Base URL",
    )

    info_distribution_api_key: str = Field(
        default="",
        title="Info Distribution API Key",
    )

    info_distribution_verify_ssl: bool = Field(
        default=True,
        title="Info Distribution 是否校验 SSL",
    )

    info_distribution_timeout_seconds: float = Field(
        default=60,
        ge=1,
        title="Info Distribution API 超时时间",
    )

    info_distribution_public_asset_base_url: str = Field(
        default="",
        title="Info Distribution 可访问的当前系统图片 Base URL",
    )

    interactive_movie_s3_endpoint_url: str = Field(
        default="",
        title="互动电影 S3 Endpoint",
    )

    interactive_movie_s3_region_name: str = Field(
        default="",
        title="互动电影 S3 Region",
    )

    interactive_movie_s3_bucket: str = Field(
        default="",
        title="互动电影 S3 Bucket",
    )

    interactive_movie_s3_access_key_id: str = Field(
        default="",
        title="互动电影 S3 Access Key ID",
    )

    interactive_movie_s3_secret_access_key: str = Field(
        default="",
        title="互动电影 S3 Secret Access Key",
    )

    interactive_movie_s3_prefix: str = Field(
        default="interactive-movie",
        title="互动电影 S3 对象前缀",
    )

    interactive_movie_s3_public_base_url: str = Field(
        default="",
        title="互动电影 S3 公开访问 Base URL",
    )

    interactive_movie_s3_presign_expires_seconds: int = Field(
        default=3600,
        ge=60,
        title="互动电影 S3 预签名 URL 有效秒数",
    )

    interactive_movie_max_video_upload_mb: int = Field(
        default=200,
        ge=1,
        title="互动电影视频上传大小限制 MB",
    )

    chat_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        title="Chat API Base URL",
        description="OpenAI-compatible API base URL",
    )

    chat_api_key: str = Field(
        default="",
        title="Chat API Key",
    )

    chat_model: str = Field(
        default="gpt-4o-mini",
        title="Chat 默认模型",
    )

    chat_system_prompt: str = Field(
        default=(
            "你是中影广告的互动影游创作助手，擅长把用户想法整理成"
            "剧本、分镜、角色、选择节点和可进入工作空间执行的下一步。"
        ),
        title="Chat 系统提示词",
    )

    chat_temperature: float = Field(
        default=0.7,
        ge=0,
        le=2,
        title="Chat 默认 temperature",
    )

    chat_max_tokens: int = Field(
        default=1200,
        ge=1,
        title="Chat 默认最大输出 token",
    )

    chat_timeout_seconds: float = Field(
        default=45,
        ge=1,
        title="Chat API 超时时间",
    )

    aiwiki_opencode_command: str = Field(
        default="opencode",
        title="AI Wiki OpenCode 命令",
    )

    aiwiki_opencode_model: str = Field(
        default="",
        title="AI Wiki OpenCode 模型",
    )

    aiwiki_opencode_agent: str = Field(
        default="",
        title="AI Wiki OpenCode Agent",
    )

    aiwiki_opencode_extra_args: str = Field(
        default="",
        title="AI Wiki OpenCode 额外参数",
    )

    aiwiki_opencode_config_path: str = Field(
        default="config/config.json",
        title="AI Wiki OpenCode 配置文件路径",
    )

    aiwiki_max_concurrent: int = Field(
        default=5,
        ge=1,
        le=20,
        title="AI Wiki 最大并发任务数",
    )

    aiwiki_task_timeout_seconds: int = Field(
        default=1800,
        ge=30,
        title="AI Wiki 任务超时时间",
    )

    aiwiki_max_upload_mb: int = Field(
        default=25,
        ge=1,
        title="AI Wiki 单任务最大上传大小",
    )

    model_config = SettingsConfigDict(
        env_file=None, env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


global_config = GlobalConfig()
