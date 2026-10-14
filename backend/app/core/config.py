"""
核心配置模块：从环境变量或 .env 文件加载应用、数据库及 LLM 配置。
支持通过修改 DATABASE_URL 在 SQLite 与 PostgreSQL 之间无缝切换。
"""
import os
from pathlib import Path
from typing import Optional

# 尝试加载 python-dotenv（若存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    def __init__(self) -> None:
        self.APP_NAME: str = os.getenv("APP_NAME", "EduGrade AI 教学作业上传与自动评分系统")
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.SECRET_KEY: str = os.getenv(
            "SECRET_KEY", "edugrade-super-secret-jwt-key-change-in-production"
        )
        self.ALGORITHM: str = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )

        # 数据库连接 URL：默认 SQLite，可切换为 postgresql+psycopg2://...
        base_dir = Path(__file__).resolve().parent.parent.parent
        default_sqlite_path = base_dir / "edugrade.db"
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL", f"sqlite:///{default_sqlite_path}"
        )
        self.SQLITE_FILE_PATH: str = str(default_sqlite_path)

        # LLM Provider 抽象层配置
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

        # 文件上传目录
        upload_dir_env = os.getenv("UPLOAD_DIR", str(base_dir / "uploads"))
        self.UPLOAD_DIR: Path = Path(upload_dir_env)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))


settings = Settings()
