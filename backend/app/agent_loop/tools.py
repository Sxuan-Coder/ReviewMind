"""Tool 抽象层：定义 LLM 可调用的工具契约。

Agent Loop 的核心机制是「LLM 在循环中自主选择调用哪个工具」。本模块提供：
- ``Tool``：单个工具的抽象基类（名称 + 描述 + JSON Schema 参数 + async 执行）
- ``ToolRegistry``：工具集注册表，负责按名查找、导出 OpenAI 兼容的工具清单
- ``ToolCall`` / ``ToolResult``：调用与结果的标准载体

设计原则：
1. 工具是「描述 + 实现」的统一体，避免散落的 if/else 分发。
2. 参数校验通过 pydantic 模型，JSON Schema 自动生成，与 OpenAI tools API 对齐。
3. 工具实现是 async 的（本项目所有 I/O 都是异步），但调用方在 Loop 内统一 await。

注意：本文件只定义抽象与载体，**具体工具实例在后续模块注册**（planner/executor）。
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 载体类型
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """LLM 发起的一次工具调用。

    ``id`` 承载 OpenAI 原生 ``tool_call_id``，多轮回灌时必需
    （回灌 ``role:"tool"`` 消息时必须带上对应的 tool_call_id）。
    文本解析兜底路径下 id 可能为空。
    """

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    id: str = ""


class ToolResult(BaseModel):
    """工具执行结果，会回灌给 LLM 作为「观察」。"""

    name: str
    success: bool = True
    # 结构化结果（必须是 JSON 可序列化的，因为要序列化后塞回 prompt）
    output: Any = None
    # 失败时的错误描述
    error: str = ""

    def to_llm_friendly(self) -> str:
        """转换为给 LLM 看的文本（作为 observation 注入下一轮 prompt）。"""
        if self.success:
            import json

            try:
                rendered = json.dumps(self.output, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                rendered = str(self.output)
            return f"[tool:{self.name}] OK\n{rendered}"
        return f"[tool:{self.name}] ERROR: {self.error}"


# ---------------------------------------------------------------------------
# Tool 基类
# ---------------------------------------------------------------------------

# pydantic 参数模型的类型变量
ArgsT = TypeVar("ArgsT", bound=BaseModel)


class Tool(abc.ABC, Generic[ArgsT]):
    """单个工具的抽象基类。

    子类需提供：
    - ``name``：唯一工具名（LLM 通过它引用）
    - ``description``：给 LLM 看的功能描述
    - ``args_model``：参数的 pydantic 模型类（用于校验 + 生成 JSON Schema）
    - ``_run``：实际执行逻辑（async）

    调用方通过 ``invoke(arguments_dict)`` 触发，基类负责参数校验与异常捕获，
    确保单个工具失败不会让整个 Loop 崩溃。
    """

    name: str = ""
    description: str = ""
    args_model: type[BaseModel] = BaseModel

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        """执行工具，统一处理参数校验与异常。"""
        try:
            validated: ArgsT = self.args_model.model_validate(arguments)
            output = await self._run(validated)
            return ToolResult(name=self.name, success=True, output=output)
        except ValidationError as exc:
            logger.warning("[TOOL:%s] invalid args: %s", self.name, exc)
            return ToolResult(name=self.name, success=False, error=f"invalid args: {exc}")
        except Exception as exc:  # noqa: BLE001 — 工具失败必须降级为 ToolResult
            logger.exception("[TOOL:%s] execution failed", self.name)
            return ToolResult(name=self.name, success=False, error=str(exc))

    @abc.abstractmethod
    async def _run(self, args: ArgsT) -> Any:
        """子类实现的实际执行逻辑。"""

    def to_openai_schema(self) -> dict[str, Any]:
        """导出 OpenAI 兼容的 tools 清单项。

        形如：
        {
          "type": "function",
          "function": {
            "name": ...,
            "description": ...,
            "parameters": {JSON Schema}
          }
        }
        """
        schema = self.args_model.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


# ---------------------------------------------------------------------------
# 工具注册表
# ---------------------------------------------------------------------------


class ToolRegistry:
    """工具集注册表：按名查找 + 导出 OpenAI 工具清单。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any]] = {}

    def register(self, tool: Tool[Any]) -> Tool[Any]:
        if not tool.name:
            raise ValueError("Tool must have a non-empty name")
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool[Any] | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def to_openai_schemas(self) -> list[dict[str, Any]]:
        """导出所有工具的 OpenAI tools 清单（传给 LLM 的 tools 字段）。"""
        return [t.to_openai_schema() for t in self._tools.values()]
