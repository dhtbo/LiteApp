import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    LiteApp Studio 全局配置模型，自动从环境变量读取并注入默认值
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ADMIN_PASSWORD: str = "admin888"
    DATA_DIR: str = os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent.parent / "data"))
    DEFAULT_OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    DEFAULT_OPENAI_API_KEY: str = ""
    DEFAULT_OPENAI_MODEL: str = "gpt-4o"
    MAX_UPLOAD_SIZE_MB: int = 50
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # NOTE: n8n 工作流引擎与开放 API 集成配置
    N8N_BASE_URL: str = "https://ai.ljcode.cn"
    N8N_API_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyODY0ZDgxZS0xNzdiLTRmOTMtYTY5ZC1jYTBiNTRlMTE5ZWMiLCJpc3MiOiJuOG4iLCJqdGkiOiJhNzkyYzFhMy05M2E5LTRhOWMtOTRjNy0xMzFkYTVlY2NjMTUiLCJpYXQiOjE3OTMxNzU0OTAsImF1ZCI6InB1YmxpYy1hcGkifQ.HwI8LMd9ef7p-lPkQUGwahm185wIPub5RygeEFw9PEI"

    @property
    def data_path(self) -> Path:
        """获取并自动创建数据根目录"""
        path = Path(self.DATA_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        """获取 SQLite 数据库文件绝对路径"""
        return self.data_path / "studio.db"

    @property
    def sites_path(self) -> Path:
        """获取托管静态站点文件夹绝对路径"""
        path = self.data_path / "sites"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def backups_path(self) -> Path:
        """获取应用历史版本备份文件夹绝对路径"""
        path = self.data_path / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

# NOTE: 单例配置对象，供全局各层注入调用
settings: Settings = Settings()
