"""
Agent Tool 基类 · 统一工具规范（对应《交付 Claw/Agent 工程范式》§4 / 铁律⑤）

移植并适配自 nanobot（agent/tools/base.py）。本地化改造：
  - execute 改为**同步**：claw 的 step 是同步 LangGraph 节点，工具同步最匹配；
    未来会话 ReAct 若需异步，再加 async 变体。
  - 纯标准库，无外部依赖。

规范：
  - 每个工具继承 Tool，声明 name / description / parameters(JSON Schema) / execute()
  - 参数必须是 JSON Schema；Registry 调用前自动 cast（类型转换）+ validate（校验）
  - to_schema() 产出 OpenAI function-calling 格式，供会话 ReAct 喂给模型
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Agent 工具抽象基类。"""

    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    @staticmethod
    def _resolve_type(t: Any) -> str | None:
        """解析 JSON Schema type；支持联合类型 ["string","null"]，取首个非 null。"""
        if isinstance(t, list):
            for item in t:
                if item != "null":
                    return item
            return None
        return t

    # ── 工具自描述（子类必须实现）──
    @property
    @abstractmethod
    def name(self) -> str:
        """function call 里用的工具名。"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具用途描述（给模型看）。"""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """参数 JSON Schema。"""

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """执行工具，返回结果（字符串或结构化）。同步。"""

    # ── 参数类型转换（cast）──
    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            return params
        return self._cast_object(params, schema)

    def _cast_object(self, obj: Any, schema: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(obj, dict):
            return obj
        props = schema.get("properties", {})
        result: dict[str, Any] = {}
        for key, value in obj.items():
            result[key] = self._cast_value(value, props[key]) if key in props else value
        return result

    def _cast_value(self, val: Any, schema: dict[str, Any]) -> Any:
        target = self._resolve_type(schema.get("type"))
        if target == "boolean" and isinstance(val, bool):
            return val
        if target == "integer" and isinstance(val, int) and not isinstance(val, bool):
            return val
        if target in self._TYPE_MAP and target not in ("boolean", "integer", "array", "object"):
            if isinstance(val, self._TYPE_MAP[target]):
                return val
        if target == "integer" and isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                return val
        if target == "number" and isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return val
        if target == "string":
            return val if val is None else str(val)
        if target == "boolean" and isinstance(val, str):
            low = val.lower()
            if low in ("true", "1", "yes"):
                return True
            if low in ("false", "0", "no"):
                return False
            return val
        if target == "array" and isinstance(val, list):
            item = schema.get("items")
            return [self._cast_value(x, item) for x in val] if item else val
        if target == "object" and isinstance(val, dict):
            return self._cast_object(val, schema)
        return val

    # ── 参数校验（validate）──
    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """校验参数，返回错误列表（空表示通过）。"""
        if not isinstance(params, dict):
            return [f"parameters must be an object, got {type(params).__name__}"]
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            raise ValueError(f"Schema must be object type, got {schema.get('type')!r}")
        return self._validate(params, {**schema, "type": "object"}, "")

    def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
        raw = schema.get("type")
        nullable = (isinstance(raw, list) and "null" in raw) or schema.get("nullable", False)
        t, label = self._resolve_type(raw), path or "parameter"
        if nullable and val is None:
            return []
        if t == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
            return [f"{label} should be integer"]
        if t == "number" and (not isinstance(val, self._TYPE_MAP[t]) or isinstance(val, bool)):
            return [f"{label} should be number"]
        if t in self._TYPE_MAP and t not in ("integer", "number") and not isinstance(val, self._TYPE_MAP[t]):
            return [f"{label} should be {t}"]

        errors: list[str] = []
        if "enum" in schema and val not in schema["enum"]:
            errors.append(f"{label} must be one of {schema['enum']}")
        if t in ("integer", "number"):
            if "minimum" in schema and val < schema["minimum"]:
                errors.append(f"{label} must be >= {schema['minimum']}")
            if "maximum" in schema and val > schema["maximum"]:
                errors.append(f"{label} must be <= {schema['maximum']}")
        if t == "string":
            if "minLength" in schema and len(val) < schema["minLength"]:
                errors.append(f"{label} must be at least {schema['minLength']} chars")
            if "maxLength" in schema and len(val) > schema["maxLength"]:
                errors.append(f"{label} must be at most {schema['maxLength']} chars")
        if t == "object":
            props = schema.get("properties", {})
            for k in schema.get("required", []):
                if k not in val:
                    errors.append(f"missing required {path + '.' + k if path else k}")
            for k, v in val.items():
                if k in props:
                    errors.extend(self._validate(v, props[k], path + "." + k if path else k))
        if t == "array" and "items" in schema:
            for i, item in enumerate(val):
                errors.extend(self._validate(item, schema["items"], f"{path}[{i}]" if path else f"[{i}]"))
        return errors

    def to_schema(self) -> dict[str, Any]:
        """转 OpenAI function-calling 格式（供会话 ReAct 喂模型）。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ── 统一返回与成败契约 ──────────────────────────────────────────────────────────
#
# 工具 execute() 的返回有两种合法形态：
#   ① 字符串：成功是正文，失败用 ToolError（自动带 "Error: " 前缀）
#   ② dict：结构化结果，**失败必须显式置 ok=False 或带 error 字段**（mailer/notifier/run_survey 已遵守）
# 成败一律用 is_tool_error 判定 —— 取代历史上散落各处、只认字符串前缀的 startswith("Error")
# 嗅探（该嗅探对 dict 工具永远判成功，导致 run_survey 等返回 {ok:False} 仍被记为成功，
# 污染 session_tool_log 与评测的自纠率/重试率）。

class ToolError(str):
    """工具失败的显式标记。

    继承 str → 向后兼容：旧代码把工具结果当字符串拼接 / 回给模型仍工作；
    但带类型语义，is_tool_error 可精确识别（无需猜前缀）。构造时自动补 "Error: " 前缀，
    使其字符串形态同时满足既有 startswith("Error") 检测。

        return ToolError(f"文件不存在：{path}")   # → "Error: 文件不存在：..."
    """
    __slots__ = ()

    def __new__(cls, message: str = "") -> "ToolError":
        text = str(message)
        if not text.startswith("Error"):
            text = f"Error: {text}"
        return super().__new__(cls, text)


def is_tool_error(result: Any) -> bool:
    """统一的工具失败判定（registry 受控执行、trace 可观测、评测成败均用它）。

    判失败：
      - ToolError 实例（显式标记）
      - 以 "Error" 开头的字符串（向后兼容 read_file / doc_* 等 str 工具）
      - dict 且 ok is False，或 error 为真值（mailer / notifier / run_survey 等结构化工具）
    其余（成功 dict、普通文本、None）视为成功。
    """
    if isinstance(result, ToolError):
        return True
    if isinstance(result, str):
        return result.startswith("Error")
    if isinstance(result, dict):
        if result.get("ok") is False:
            return True
        if result.get("error"):
            return True
    return False
