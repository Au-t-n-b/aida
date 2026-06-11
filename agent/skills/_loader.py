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
    source_path: str = ""           # 绝对路径，方便调试
    raw_frontmatter: dict = field(default_factory=dict)
    body_excerpt: str = ""          # SKILL.md 正文前 800 字（用于路由提示）

    def short(self) -> dict:
        """渐进式暴露的「门面」：只暴露 name + description，不暴露正文"""
        return {"name": self.name, "description": self.description}


def _parse_yaml_lite(text: str) -> dict:
    """
    最小化 YAML 解析（只支持 key: value 形式，单行字符串）。
    SKILL.md 的 frontmatter 通常很简单，不引 PyYAML 减少依赖。
    """
    out: dict = {}
    current_key = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")) and current_key:
            # 续行：拼到上一个 key
            out[current_key] = (out[current_key] + " " + raw.strip()).strip()
            continue
        if ":" not in raw:
            continue
        k, _, v = raw.partition(":")
        current_key = k.strip()
        out[current_key] = v.strip().strip('"').strip("'")
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
    return SkillMetadata(
        name=fm.get("name", ""),
        description=fm.get("description", ""),
        source_path=str(p),
        raw_frontmatter=fm,
        body_excerpt=body[:800],
    )


def default_skill_md_path(skill_name: str) -> Path:
    """SKILL.md 路径解析（A 层唯一真相）。

    优先用部署副本 ``~/.claude/skills/<name>/SKILL.md``（Claude Code 运行时约定）；
    部署副本不存在时回退到仓库内 ``skills/<name>/SKILL.md``——开发机 / CI / lint
    未部署副本时也总能命中 A 层契约（修复 lint_skill_contract「找不到 SKILL.md」）。
    """
    deployed = Path.home() / ".claude" / "skills" / skill_name / "SKILL.md"
    if deployed.exists():
        return deployed
    repo_copy = Path(__file__).resolve().parents[2] / "skills" / skill_name / "SKILL.md"
    return repo_copy if repo_copy.exists() else deployed
