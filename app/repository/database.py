import sqlite3
from pathlib import Path
from typing import Generator
from app.core.config import settings
from app.core.logger import logger
from app.model.models import (
    CREATE_APPS_TABLE_SQL,
    CREATE_LLM_PROVIDERS_TABLE_SQL,
    CREATE_APP_VERSIONS_TABLE_SQL,
    CREATE_FORM_SUBMISSIONS_TABLE_SQL,
)

def get_connection() -> sqlite3.Connection:
    """
    获取 SQLite 数据库连接并配置 Row Factory 和 WAL 模式
    
    :returns: sqlite3.Connection 实例
    """
    conn = sqlite3.connect(
        database=str(settings.db_path),
        check_same_thread=False,
        timeout=30.0
    )
    conn.row_factory = sqlite3.Row
    # NOTE: 开启 WAL (Write-Ahead Logging) 模式以获得最佳的高并发读写性能
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db() -> None:
    """
    初始化数据库表结构与默认种子数据
    """
    logger.info(f"正在初始化数据库：{settings.db_path}")
    conn = get_connection()
    try:
        with conn:
            conn.executescript(CREATE_APPS_TABLE_SQL)
            conn.executescript(CREATE_LLM_PROVIDERS_TABLE_SQL)
            conn.executescript(CREATE_APP_VERSIONS_TABLE_SQL)
            conn.executescript(CREATE_FORM_SUBMISSIONS_TABLE_SQL)

            # NOTE: 若 LLM 提供商列表为空，根据环境变量注入默认兼容配置
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS cnt FROM llm_providers")
            row = cursor.fetchone()
            if row and row["cnt"] == 0 and settings.DEFAULT_OPENAI_BASE_URL:
                cursor.execute(
                    """
                    INSERT INTO llm_providers (name, base_url, api_key, model_name, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (
                        "默认大模型接口",
                        settings.DEFAULT_OPENAI_BASE_URL,
                        settings.DEFAULT_OPENAI_API_KEY,
                        settings.DEFAULT_OPENAI_MODEL,
                    )
                )
                logger.info(f"已自动注入默认大模型配置: {settings.DEFAULT_OPENAI_MODEL}")

            # NOTE: 若微应用列表为空，注入一个开箱即用的官方 Demo 应用
            cursor.execute("SELECT COUNT(*) AS cnt FROM apps")
            app_row = cursor.fetchone()
            if app_row and app_row["cnt"] == 0:
                demo_slug = "welcome-timer"
                demo_dir = settings.sites_path / demo_slug
                demo_dir.mkdir(parents=True, exist_ok=True)
                demo_html_path = demo_dir / "index.html"
                
                demo_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LiteApp Studio 官方示例应用</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    @keyframes pulse-subtle {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.02); }
    }
    .animate-subtle { animation: pulse-subtle 4s ease-in-out infinite; }
  </style>
</head>
<body class="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-slate-100 min-h-screen flex flex-col items-center justify-center p-6 selection:bg-indigo-500 selection:text-white">
  <div class="max-w-xl w-full bg-slate-800/80 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 shadow-2xl animate-subtle">
    <div class="flex items-center gap-4 mb-6">
      <div class="w-14 h-14 rounded-2xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-3xl shadow-lg shadow-indigo-500/20">
        🚀
      </div>
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          LiteApp Studio
          <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">运行正常</span>
        </h1>
        <p class="text-sm text-slate-400">单文件轻量级微应用演示沙箱</p>
      </div>
    </div>

    <!-- 交互计数器与专注计时器 -->
    <div class="bg-slate-900/60 rounded-2xl p-6 border border-slate-700/50 mb-6 text-center">
      <p class="text-xs uppercase tracking-widest text-slate-400 font-semibold mb-2">专注倒计时</p>
      <div id="timerDisplay" class="text-5xl font-mono font-extrabold text-indigo-400 tracking-wider mb-4">
        25:00
      </div>
      <div class="flex justify-center gap-3">
        <button id="toggleBtn" onclick="toggleTimer()" class="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition text-sm font-semibold flex items-center gap-2 shadow-lg shadow-indigo-600/30">
          <i data-lucide="play" class="w-4 h-4"></i> 开始专注
        </button>
        <button onclick="resetTimer()" class="px-4 py-2.5 rounded-xl bg-slate-700 hover:bg-slate-600 active:scale-95 transition text-sm font-medium text-slate-300 flex items-center gap-2">
          <i data-lucide="rotate-ccw" class="w-4 h-4"></i> 重置
        </button>
      </div>
    </div>

    <!-- 快速待办笔记 -->
    <div class="space-y-3">
      <div class="flex items-center justify-between text-xs text-slate-400 font-medium px-1">
        <span>快速便签 (数据存储于本地 localStorage)</span>
        <span id="savedTag" class="text-emerald-400 opacity-0 transition-opacity">已自动保存</span>
      </div>
      <textarea id="quickNotes" oninput="saveNote()" rows="3" placeholder="随手记下当下的灵感..." class="w-full bg-slate-900/50 border border-slate-700 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none text-slate-200 placeholder-slate-500"></textarea>
    </div>

    <div class="mt-6 pt-4 border-t border-slate-700/50 flex items-center justify-between text-xs text-slate-500">
      <span>微应用标识: welcome-timer</span>
      <a href="/" target="_top" class="text-indigo-400 hover:text-indigo-300 transition flex items-center gap-1">
        返回工作台门户 <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
      </a>
    </div>
  </div>

  <script>
    lucide.createIcons();
    let timeLeft = 25 * 60;
    let timerId = null;

    function updateDisplay() {
      const minutes = Math.floor(timeLeft / 60).toString().padStart(2, '0');
      const seconds = (timeLeft % 60).toString().padStart(2, '0');
      document.getElementById('timerDisplay').innerText = `${minutes}:${seconds}`;
    }

    function toggleTimer() {
      const btn = document.getElementById('toggleBtn');
      if (timerId) {
        clearInterval(timerId);
        timerId = null;
        btn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i> 继续专注';
      } else {
        timerId = setInterval(() => {
          if (timeLeft > 0) {
            timeLeft--;
            updateDisplay();
          } else {
            clearInterval(timerId);
            timerId = null;
            alert('🎉 专注时间结束，休息一下吧！');
            resetTimer();
          }
        }, 1000);
        btn.innerHTML = '<i data-lucide="pause" class="w-4 h-4"></i> 暂停专注';
      }
      lucide.createIcons();
    }

    function resetTimer() {
      if (timerId) clearInterval(timerId);
      timerId = null;
      timeLeft = 25 * 60;
      updateDisplay();
      document.getElementById('toggleBtn').innerHTML = '<i data-lucide="play" class="w-4 h-4"></i> 开始专注';
      lucide.createIcons();
    }

    function saveNote() {
      const val = document.getElementById('quickNotes').value;
      localStorage.setItem('liteapp_demo_notes', val);
      const tag = document.getElementById('savedTag');
      tag.classList.remove('opacity-0');
      clearTimeout(window._saveTimer);
      window._saveTimer = setTimeout(() => tag.classList.add('opacity-0'), 1500);
    }

    const saved = localStorage.getItem('liteapp_demo_notes');
    if (saved) document.getElementById('quickNotes').value = saved;
  </script>
</body>
</html>
"""
                demo_html_path.write_text(demo_content, encoding="utf-8")

                cursor.execute(
                    """
                    INSERT INTO apps (slug, title, description, category, icon, entry_type, view_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        demo_slug,
                        "欢迎体验番茄钟便签",
                        "LiteApp Studio 官方预置的开箱即用微应用，包含专注倒计时与本地便签持久化功能。",
                        "效率工具",
                        "🍅",
                        "html",
                        1,
                    )
                )
                logger.info(f"已创建官方初始 Demo 微应用: {demo_slug}")
    except Exception as e:
        logger.error(f"数据库初始化异常: {e}")
        raise
    finally:
        conn.close()
