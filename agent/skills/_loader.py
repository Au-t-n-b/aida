"""
SKILL.md frontmatter loader · A+B 架构的单向同步

SKILL.md 是 source of truth。BaseSkill 在初始化时读 frontmatter，
把 name / description / 触发词等元数据注入 self.metadata，
后端 LangGraph 侧不再写 metadata 文本，只写 step 实现。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class SkillMetadata:
    name: str = ""
    description: str = ""
    version: str = ""               # 语义化版本（manifest，热加载/兼容判断用）
    enabled: bool = True            # 软开关：false 则前端不挂入口（不删目录即可下线）
    ui: dict = field(default_factory=dict)        # 导航元数据：label/group/order/icon/route_key
    runtime: dict = field(default_factory=dict)   # 运行声明：workspace_env/tools
    source_path: str = ""           # 绝对路径，方便调试
    raw_frontmatter: dict = field(default_factory=dict)
    body_excerpt: str = ""          # SKILL.md 正文前 800 字（用于路由提示）

    def short(self) -> dict:
        """渐进式暴露的「门面」：name + description + manifest 元数据（不暴露正文）。

        P1：扩展为 driving 前端导航/部署的元数据载体（`/agent/skills` 返回此结构）。
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "ui": self.ui,
            "runtime": self.runtime,
        }


def _coerce(v: str):
    """标量值归一：行内列表 ``[a, b]`` → list；``true/false`` → bool；纯整数 → int；其余 str。"""
    s = v.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if s.lstrip("-").isdigit():
        try:
            return int(s)
        except ValueError:
            pass
    return s.strip('"').strip("'")


def _parse_yaml_lite(text: str) -> dict:
    """最小化 YAML 解析（零三方依赖，刻意不引 PyYAML）。

    支持：
      - 顶层 ``key: value``（单行标量；空值后跟无冒号缩进行 → 续行拼接，保留历史行为）
      - 顶层 ``key:`` 空值后跟一级缩进 ``  subkey: subval`` → 解析为嵌套 dict（P1 新增，ui/runtime 用）
      - 行内列表 ``key: [a, b]`` → list
    不支持：两级以上嵌套 / 缩进列表项（如 device_install.idle_screen.steps[]）——
    仅保证遇到时不抛异常（忽略或不污染目标字段），因为这些块不经本 loader 消费。
    """
    out: dict = {}
    current_key = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        if raw[:1] in (" ", "\t") and current_key is not None:
            cur = out.get(current_key)
            is_kv = (":" in stripped) and not stripped.startswith("-")
            if is_kv and (cur == "" or isinstance(cur, dict)):
                # 一级嵌套 mapping：把空值顶层 key 提升为 dict
                if not isinstance(cur, dict):
                    out[current_key] = {}
                k, _, v = stripped.partition(":")
                out[current_key][k.strip()] = _coerce(v)
                continue
            if isinstance(cur, str):
                # 续行：拼到上一个标量 key（历史行为）
                out[current_key] = (cur + " " + stripped).strip()
            # dict 下的列表项 / 更深层嵌套：忽略，不抛
            continue
        if ":" not in stripped:
            continue
        k, _, v = stripped.partition(":")
        current_key = k.strip()
        v = v.strip()
        out[current_key] = _coerce(v) if v != "" else ""
    return out


def load_skill_md(skill_md_path: Path) -> SkillMetadata:
    """
    从 SKILL.md 解析元数据。
    找不到文件 / 无 frontmatter 时返回空 metadata（不抛异常），让 Skill 退化为「代码自描述」模式。
    """
    p = Path(skill_md_path)
    if not p.exists():
        return SkillMetadata(source_path=str(p))

    text = p.read_text(encoding="utf-8", errors="replace")
    m = _FM_RE.match(text)
    if not m:
        return SkillMetadata(source_path=str(p), body_excerpt=text[:800])

    fm = _parse_yaml_lite(m.group(1))
    body = text[m.end():].lstrip()
    name = fm.get("name", "")
    return SkillMetadata(
        name=name,
        description=fm.get("description", ""),
        version=str(fm.get("version", "") or ""),
        enabled=_as_bool(fm.get("enabled", True)),
        ui=_normalize_ui(fm.get("ui"), name),
        runtime=fm.get("runtime") if isinstance(fm.get("runtime"), dict) else {},
        source_path=str(p),
        raw_frontmatter=fm,
        body_excerpt=body[:800],
    )


def _as_bool(v) -> bool:
    """frontmatter enabled 归一：缺省/真值 → True；显式 false/0/no/off → False。"""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("false", "0", "no", "off", "")


def _normalize_ui(ui, name: str) -> dict:
    """补齐导航默认值，使未写 manifest 的 skill 也能被 `/agent/skills` 安全消费。

    label/route_key 缺省回退到 skill name；order 缺省置末（999）。
    """
    out = dict(ui) if isinstance(ui, dict) else {}
    out.setdefault("label", name)
    out.setdefault("route_key", name)
    out.setdefault("group", "")
    out.setdefault("icon", "")
    if not isinstance(out.get("order"), int):
        try:
            out["order"] = int(out.get("order", 999))
        except (TypeError, ValueError):
            out["order"] = 999
    return out


def default_skill_md_path(skill_name: str) -> Path:
    """SKILL.md 路径解析（A 层唯一真相）。

    优先级（就近 > 部署副本 > 历史布局）：
      1. **就近** ``agent/skills/<name>/SKILL.md``（A/B 同目录·推荐新约定，单一真相、易管理）
      2. 部署副本 ``~/.claude/skills/<name>/SKILL.md``（Claude Code 运行时约定）
      3. 历史 A 层 ``skills/<name>/SKILL.md``（尚未就近化的 skill，如 xtsj / software_deployment）
    任一存在即返回；都不存在时回退部署副本路径（交由上层报「缺 SKILL.md」）。
    """
    colocated = Path(__file__).resolve().parent / skill_name / "SKILL.md"
    if colocated.exists():
        return colocated
    deployed = Path.home() / ".claude" / "skills" / skill_name / "SKILL.md"
    if deployed.exists():
        return deployed
    repo_copy = Path(__file__).resolve().parents[2] / "skills" / skill_name / "SKILL.md"
    return repo_copy if repo_copy.exists() else deployed
