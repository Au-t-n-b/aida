"""设备安装模块引导文案（启动屏 · 会话首条，不进右侧 SDUI）。"""

MODULE_INTRO_TITLE = "设备安装 · 流程说明"

MODULE_INTRO_MD = (
    "**主建设流程（点击「启动设备安装」启动）：**\n\n"
    "1. **接收实施计划** — 从上游读取自包含《设备安装实施计划》（含 SN Sheet）\n"
    "2. **计划下发** — 勾选《实施计划》条目后下发\n"
    "3. **SN扫码表生成** — 按勾选管理单元过滤，按机房+设备大类生成 SN 扫码表\n"
    "4. **ESN信息填写** — 大盘内逐台填写 ESN，生成完工清单/报告\n\n"
    "**辅助流（command 路由）：** 进展反馈 / 进展查询 / 计划查询 / 计划调整 / 设备总览。"
)


def chat_intro_payload() -> dict:
    """供 idle_screen.chat_intro · 中间对话框首条（once）。"""
    return {
        "title": MODULE_INTRO_TITLE,
        "body": MODULE_INTRO_MD,
        "once": True,
    }
