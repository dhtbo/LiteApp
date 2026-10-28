from dataclasses import dataclass
from typing import Optional

@dataclass
class AppModel:
    """
    微应用数据实体定义
    """
    id: Optional[int]
    slug: str
    title: str
    description: str
    category: str
    icon: str
    entry_type: str
    view_count: int
    created_at: str
    updated_at: str

@dataclass
class LLMProviderModel:
    """
    大语言模型兼容提供商数据实体定义
    """
    id: Optional[int]
    name: str
    base_url: str
    api_key: str
    model_name: str
    is_active: int
    created_at: str
    updated_at: str

@dataclass
class AppVersionModel:
    """
    微应用历史版本快照实体定义
    """
    id: Optional[int]
    app_slug: str
    version_num: int
    entry_type: str
    description: str
    storage_path: str
    created_at: str

@dataclass
class FormSubmissionModel:
    """
    表单采集数据提交记录实体定义
    """
    id: Optional[int]
    form_slug: str
    data_json: str
    ip_address: str
    user_agent: str
    created_at: str

# NOTE: SQLite 核心表结构与索引定义语句
CREATE_APPS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT '通用',
    icon TEXT DEFAULT '🚀',
    entry_type TEXT DEFAULT 'html',
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_apps_slug ON apps(slug);
CREATE INDEX IF NOT EXISTS idx_apps_category ON apps(category);
"""

CREATE_LLM_PROVIDERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT NOT NULL,
    model_name TEXT NOT NULL,
    is_active INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_llm_is_active ON llm_providers(is_active);
"""

CREATE_APP_VERSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_slug TEXT NOT NULL,
    version_num INTEGER NOT NULL,
    entry_type TEXT DEFAULT 'html',
    description TEXT DEFAULT '',
    storage_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_versions_slug ON app_versions(app_slug);
CREATE INDEX IF NOT EXISTS idx_versions_created ON app_versions(created_at);
"""

CREATE_FORM_SUBMISSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS form_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_slug TEXT NOT NULL,
    data_json TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_form_slug ON form_submissions(form_slug);
CREATE INDEX IF NOT EXISTS idx_form_created ON form_submissions(created_at);
"""
