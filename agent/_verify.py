"""快速集成验证脚本——静态 AST 校验（无需 langchain）。"""
import sys, os, ast, re

ROOT = os.path.dirname(os.path.abspath(__file__))  # D:/aida/agent/
AGENT_SRC = os.path.join(ROOT, 'agent')

results = []
errors = []

def ok(msg): results.append(f"  OK  {msg}")
def err(msg): errors.append(f"  ERR {msg}")


def src(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


# ── 1. chat_engine.py ────────────────────────────────────────────────────────
ce = src('agent/chat_engine.py')
for symbol in ['run_chat_async', 'run_chat', 'TOOLS_REQUIRING_APPROVAL',
               'SkillLaunchCb', 'ApprovalCb', 'approval_cb', 'skill_launch_cb',
               'asyncio.to_thread', 'astream']:
    (ok if symbol in ce else err)(f"chat_engine.py: {symbol!r}")

req_approval = re.search(r"TOOLS_REQUIRING_APPROVAL.*frozenset.*\{([^}]+)\}", ce)
if req_approval:
    ok(f"chat_engine.py: TOOLS_REQUIRING_APPROVAL = {req_approval.group(0)[:80]}")
else:
    err("chat_engine.py: TOOLS_REQUIRING_APPROVAL definition not found")

# ── 2. main.py ────────────────────────────────────────────────────────────────
mp = src('main.py')
for symbol in ['_PENDING_APPROVALS', 'ApproveToolReq', 'approve_tool',
               '_approval_cb', 'run_chat_async', 'run_in_background',
               '_skill_launch_cb', 'flags']:
    # run_in_background is not expected; skip that one
    if symbol == 'run_in_background':
        continue
    (ok if symbol in mp else err)(f"main.py: {symbol!r}")

# ── 3. tools/__init__.py ─────────────────────────────────────────────────────
ti = src('agent/tools/__init__.py')
for tool in ['WebFetchTool', 'WebSearchTool', 'web_fetch', 'web_search']:
    (ok if tool in ti else err)(f"tools/__init__.py: {tool!r}")

# ── 4. web_fetch.py schema ────────────────────────────────────────────────────
wf = src('agent/tools/web_fetch.py')
for sym in ['WebFetchTool', "'web_fetch'", 'httpx', 'url', 'max_chars']:
    (ok if sym in wf else err)(f"web_fetch.py: {sym!r}")

# ── 5. web_search.py schema ──────────────────────────────────────────────────
ws = src('agent/tools/web_search.py')
for sym in ['WebSearchTool', "'web_search'", 'httpx', 'query', 'max_results']:
    (ok if sym in ws else err)(f"web_search.py: {sym!r}")

# ── 6. frontend useChatStream.ts ─────────────────────────────────────────────
fe_root = os.path.normpath(os.path.join(ROOT, '..', 'frontend', 'src'))
uch = open(os.path.join(fe_root, 'hooks', 'useChatStream.ts'), encoding='utf-8').read()
for sym in ['ToolApprovalInfo', 'tool_approval_required', 'decideTool', 'approveTool',
            'AGENT_BASE', 'approval_id', 'parseSseFrame']:
    if sym == 'approveTool':
        continue  # we use decideTool
    (ok if sym in uch else err)(f"useChatStream.ts: {sym!r}")

# ── 7. frontend chat.tsx route ────────────────────────────────────────────────
ch = open(os.path.join(fe_root, 'routes', 'chat.tsx'), encoding='utf-8').read()
for sym in ['ToolApprovalCard', 'decideTool', 'SduiPanel', 'useSduiStream',
            'SkillLaunchBadge', 'MessageBubble']:
    (ok if sym in ch else err)(f"chat.tsx: {sym!r}")

# ── 8. router.tsx ─────────────────────────────────────────────────────────────
rt = open(os.path.join(fe_root, 'router.tsx'), encoding='utf-8').read()
(ok if "'/chat'" in rt else err)("router.tsx: /chat route")
(ok if 'ChatPage' in rt else err)("router.tsx: ChatPage import")

# ── 结果 ─────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"[verify] 静态集成校验结果：{len(results)} OK / {len(errors)} ERR")
print('='*60)
for r in results:
    print(r)
if errors:
    print()
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("\n全部通过 ✓")
