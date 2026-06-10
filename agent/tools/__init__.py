"""桥接 & 工具集

通用工具框架（《交付 Claw/Agent 工程范式》§4 / 铁律⑤）：
  - Tool          工具基类（JSON Schema + cast + validate + OpenAI schema）
  - ToolRegistry  工具注册表（受控执行 + 自纠提示 + 白名单）
  - DEFAULT_TOOLS 进程级默认注册表（已挂内置工具，供 step / 会话 ReAct 共享）

用法：
    from agent.tools import DEFAULT_TOOLS
    out = DEFAULT_TOOLS.execute("read_file", {"path": "x.txt", "max_bytes": "2000"})
    schemas = DEFAULT_TOOLS.get_definitions(allowed=["read_file"])  # 喂会话 ReAct
"""
from .base import Tool
from .registry import ToolRegistry
from .read_file import ReadFileTool
from .send_mail import SendMailTool
from .send_welink import SendWelinkTool
from .present_choices import PresentChoicesTool
from .run_survey import RunSurveyTool
from .doc_read_xlsx import DocReadXlsxTool
from .doc_write_docx import DocWriteDocxTool
from .web_fetch import WebFetchTool
from .web_search import WebSearchTool

# 进程级默认注册表 —— step 与会话 ReAct 共享同一份工具能力库
DEFAULT_TOOLS = ToolRegistry()
DEFAULT_TOOLS.register(ReadFileTool())
DEFAULT_TOOLS.register(SendMailTool())        # 邮件统一走 mailer.py（规范4），默认 dry-run
DEFAULT_TOOLS.register(SendWelinkTool())      # IM 统一走 notifier.py（规范4），默认 dry-run
DEFAULT_TOOLS.register(PresentChoicesTool())  # 发信/发IM前确认；chat_engine 拦截，不真执行
DEFAULT_TOOLS.register(RunSurveyTool())       # skill-as-tool：会话唤起智慧工勘
DEFAULT_TOOLS.register(DocReadXlsxTool())     # 读 Excel 工作表（CSV 或 JSON）
DEFAULT_TOOLS.register(DocWriteDocxTool())    # 写 Word 文档（Markdown→docx）
DEFAULT_TOOLS.register(WebFetchTool())        # 抓取指定 URL 的网页正文
DEFAULT_TOOLS.register(WebSearchTool())       # DuckDuckGo 搜索（无需 API Key）

__all__ = [
    "Tool", "ToolRegistry",
    "ReadFileTool", "SendMailTool", "SendWelinkTool", "PresentChoicesTool", "RunSurveyTool",
    "DocReadXlsxTool", "DocWriteDocxTool", "WebFetchTool", "WebSearchTool",
    "DEFAULT_TOOLS",
]
