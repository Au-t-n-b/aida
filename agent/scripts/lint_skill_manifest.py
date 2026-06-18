"""
skill-manifest · SKILL.md frontmatter manifest 完整性守门（规范 5 守门 · P1 元数据驱动）

背景：P1 起 SKILL.md frontmatter 升级为「skill 自描述清单（manifest）」，驱动前端导航与
未来热加载/部署。每个已注册 skill 的 frontmatter 必须声明：
  version（语义化）· enabled（bool）· ui{label,group,order:int,icon,route_key} · runtime{workspace_env}
并保证 enabled skill 间 route_key 全局唯一（前端 /module/<route_key> 不冲突）。

不一致即阻断（与 lint_skill_contract 同款守门）。

设计：纯 stdlib，按文件加载 agent/skills/_loader.py 与 discovery.py（不 import agent.skills 包，
免触发 _register_all 的重依赖），因此**无需 venv** 即可运行。skill 名单来自 discovery
（与运行时同一套目录发现，契约≡代码；P3 起 __init__.py 不再有 _specs）。

退出码：违规 → 1；干净 → 0。

用法：
    python agent/scripts/lint_skill_manifest.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，✓/❌/中文会 UnicodeEncodeError → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # aida/
AGENT_SKILLS = PROJECT_ROOT / "agent" / "skills"

_SEMVER_RE = re.compile(r"^\d+\.\d+(\.\d+)?([-+.].+)?$")
_VALID_GROUPS = {"ops", "design", "early"}


# ─── 纯逻辑核心（无 IO / 无 agent import，便于单测）───

def skill_names(specs) -> list[str]:
    """从 discovery.discover_skill_specs() 结果取 skill 名（去重保序）。"""
    out: list[str] = []
    for s in specs:
        if s.name not in out:
            out.append(s.name)
    return out


def check_manifest(name: str, meta) -> list[str]:
    """单 skill manifest 校验，返回违规信息列表（空 = 通过）。meta 为 SkillMetadata。"""
    v: list[str] = []

    if not meta.version:
        v.append("缺 version（frontmatter 顶层 `version: x.y.z`）")
    elif not _SEMVER_RE.match(str(meta.version)):
        v.append(f"version `{meta.version}` 非语义化版本（应形如 1.0.0 / 0.1.0）")

    ui = meta.ui if isinstance(meta.ui, dict) else {}
    for key in ("label", "group", "route_key"):
        if not str(ui.get(key, "")).strip():
            v.append(f"ui.{key} 缺失或空（frontmatter `ui:` 下声明）")
    group = str(ui.get("group", "")).strip()
    if group and group not in _VALID_GROUPS:
        v.append(f"ui.group `{group}` 不在允许集 {sorted(_VALID_GROUPS)}")
    if not isinstance(ui.get("order"), int):
        v.append(f"ui.order 缺失或非整数（当前: {ui.get('order')!r}）")

    rt = meta.runtime if isinstance(meta.runtime, dict) else {}
    if not str(rt.get("workspace_env", "")).strip():
        v.append("runtime.workspace_env 缺失（声明工作区根环境变量，如 ZHGK_ROOT）")

    return v


def check_route_key_uniqueness(metas: dict) -> list[str]:
    """enabled skill 间 route_key 须唯一（前端入口键不冲突）。"""
    seen: dict[str, str] = {}
    v: list[str] = []
    for name, meta in metas.items():
        if not meta.enabled:
            continue
        rk = str((meta.ui or {}).get("route_key", "")).strip()
        if not rk:
            continue
        if rk in seen:
            v.append(f"route_key `{rk}` 冲突：{seen[rk]} 与 {name}（enabled skill 间须唯一）")
        else:
            seen[rk] = name
    return v


# ─── IO 外壳 ───

def _resolve_skill_md(name: str) -> Path | None:
    """A 层 SKILL.md 解析（lint 版）：兼容就近放（agent/skills/<name>/）与历史布局。

    顺序对齐运行时 default_skill_md_path：就近(B 层目录) → 部署副本 → 历史仓库 A 层。
    """
    for cand in (
        AGENT_SKILLS / name / "SKILL.md",
        Path.home() / ".claude" / "skills" / name / "SKILL.md",
        PROJECT_ROOT / "skills" / name / "SKILL.md",
    ):
        if cand.exists():
            return cand
    return None


def _load_standalone(mod_name: str, file_name: str):
    """按文件加载 agent/skills 下的纯 stdlib 模块（不触发 agent.skills 包 import）。"""
    import importlib.util
    path = AGENT_SKILLS / file_name
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    # 注册到 sys.modules：@dataclass 内部会按 cls.__module__ 反查模块命名空间（Py3.12+ 必需）
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_loader_module():
    """按文件加载 _loader.py（不触发 agent.skills 包 import）。"""
    return _load_standalone("_aida_skill_loader", "_loader.py")


def _load_discovery_module():
    """按文件加载 discovery.py（不触发 agent.skills 包 import）。"""
    return _load_standalone("_aida_skill_discovery", "discovery.py")


def main() -> int:
    loader = _load_loader_module()
    discovery = _load_discovery_module()
    names = skill_names(discovery.discover_skill_specs())
    if not names:
        sys.stdout.write("[skill-manifest] ⚠ discovery 未发现任何 skill（目录结构变了？）\n")
        return 1

    metas: dict = {}
    violations: list[tuple[str, str]] = []
    for name in names:
        md_path = _resolve_skill_md(name)
        if md_path is None:
            violations.append((name, "找不到 SKILL.md（A 层门面缺失）"))
            continue
        meta = loader.load_skill_md(md_path)
        metas[name] = meta
        for msg in check_manifest(name, meta):
            violations.append((name, msg))

    for msg in check_route_key_uniqueness(metas):
        violations.append(("*", msg))

    if not violations:
        sys.stdout.write(
            f"[skill-manifest] OK · {len(names)} 个 skill manifest 完整（{', '.join(names)}）\n"
        )
        return 0

    sys.stdout.write(f"[skill-manifest] ❌ 发现 {len(violations)} 处 manifest 问题：\n\n")
    for name, msg in violations:
        sys.stdout.write(f"  [{name}] {msg}\n")
    sys.stdout.write(
        "\n说明：P1 起 SKILL.md frontmatter 须声明 version/enabled/ui/runtime（驱动前端导航与部署）。\n"
        "  模板见 skills/_template/SKILL.md。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
