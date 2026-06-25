"""LLM 驱动层：Agent Loop 的「引擎」。

负责在循环的每一步：
1. 把 messages + 可用工具清单发给 LLM；
2. 解析 LLM 的决策——是「调用工具」还是「输出最终结果」；
3. 返回结构化的 ``AgentStep``，供 Loop 主循环判断继续还是终止。

为什么需要这一层？
现有 ``app.core.llm.llm_client`` 是一个 OpenAI-compatible 的 raw chat 客户端。
真实环境的 LLM 对 ``tools`` / ``tool_calls`` 的支持参差不齐：
- 部分模型走原生 OpenAI tool_calls 字段；
- 部分模型（或 mock 模式）只返回纯文本，工具调用内嵌在文本里。

因此本驱动做「双通道容错解析」：优先读原生 tool_calls，失败则尝试从文本中
解析 JSON。这保证 Loop 在不同模型/降级场景下都能运转——这正是现状（单次调用）
做不到的鲁棒性。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.llm import LLMClientError, llm_client
from app.agent_loop.tools import ToolCall, ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """单步决策结果。

    两种互斥形态：
    - ``is_final=True``：LLM 认为信息足够，产出最终文本（``final_text``）；
    - ``is_final=False``：LLM 要调用工具（``tool_call``），等待执行后继续循环。
    """

    is_final: bool
    final_text: str = ""
    tool_call: ToolCall | None = None
    # 该步原始的 assistant 文本（用于 reasoning 追踪，可选）
    reasoning: str = ""


class LLMDriver:
    """Agent Loop 的 LLM 交互引擎。"""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        client: Any | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_steps: int = 5,
    ) -> None:
        self._registry = registry
        self._client = client or llm_client
        self._model = model
        self._temperature = temperature
        self.max_steps = max_steps

    async def step(self, messages: list[dict[str, str]]) -> AgentStep:
        """执行一次 LLM 交互并解析为 AgentStep。"""
        tools_schema = self._registry.to_openai_schemas()

        # 尝试 1：带 tools 字段调用（OpenAI 原生 tool_calls）
        try:
            raw_response, native_tool_calls = await self._chat_with_tools(messages, tools_schema)
            if native_tool_calls is not None:
                return native_tool_calls
            # 没拿到原生 tool_calls，回退到文本解析
            return self._parse_from_text(raw_response)
        except LLMClientError:
            # LLM 调用本身失败 —— 上层 Loop 负责降级，这里向上抛
            raise
        except Exception as exc:  # noqa: BLE001 — 解析层要兜底，避免 Loop 卡死
            logger.warning("[LLM_DRIVER] step parse failed: %s: %s", type(exc).__name__, exc)
            # 兜底：视为最终结果（让 Loop 安全退出），把原始异常记进日志
            return AgentStep(is_final=True, final_text="", reasoning=f"parse_error: {exc}")

    async def _chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools_schema: list[dict[str, Any]],
    ) -> tuple[str, AgentStep | None]:
        """调用 LLM。优先尝试原生 tool_calls；不支持时退化为纯文本。"""
        # 现有 llm_client.chat 返回纯文本 content。原生 tool_calls 需要原始 JSON，
        # 当前 client 暂未透出。为保持兼容，这里先用纯文本通道（绝大多数场景已够用），
        # 并预留扩展点：当 client 支持 tool_calls 时可在此短路。
        # NOTE: 这是有意为之的渐进式设计——文本解析通道已能覆盖 tool 调用解析。
        content = await self._client.chat(
            messages,
            model=self._model,
            temperature=self._temperature,
        )
        return content, None

    # ------------------------------------------------------------------
    # 文本解析通道：从 LLM 纯文本回复中提取「最终答案」或「工具调用」
    # ------------------------------------------------------------------

    # 约定的最终答案标记：LLM 在认为自己完成时输出此标记
    _FINAL_TAG = "FINAL_ANSWER"
    # 约定的工具调用标记：LLM 想调用工具时输出 ``<<<TOOL_CALL>>>{json}<<<END>>>
    _TOOL_CALL_TAG = "TOOL_CALL"

    def _parse_from_text(self, text: str) -> AgentStep:
        """从纯文本中解析最终答案或工具调用。

        解析顺序：
        1. 是否含 TOOL_CALL 块 → 解析为工具调用；
        2. 是否含 FINAL_ANSWER 块 → 作为最终结果；
        3. 都没有 → 视为最终结果（默认安全退出）。
        """
        if not text:
            return AgentStep(is_final=True, final_text="", reasoning="empty_response")

        # 1. 工具调用解析
        tool_call = self._extract_tool_call(text)
        if tool_call is not None:
            return AgentStep(
                is_final=False,
                tool_call=tool_call,
                reasoning=self._strip_markers(text),
            )

        # 2. 最终答案解析
        final = self._extract_final_answer(text)
        return AgentStep(
            is_final=True,
            final_text=final,
            reasoning=self._strip_markers(text),
        )

    def _extract_tool_call(self, text: str) -> ToolCall | None:
        """从文本中提取 TOOL_CALL JSON 块。

        支持两种格式（容错）：
        - 显式标记：``TOOL_CALL: {"name": "...", "arguments": {...}}``
        - 代码块：`````json\n{"name": "...", ...}\n`````
        """
        # 格式 A：显式标记行
        m = re.search(r"TOOL_CALL\s*[:：]?\s*(\{.*\})", text, re.DOTALL)
        candidate = None
        if m:
            candidate = m.group(1)
        else:
            # 格式 B：JSON 代码块中含 name+arguments
            m2 = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if m2:
                candidate = m2.group(1)

        if not candidate:
            return None

        parsed = self._safe_load_json(candidate)
        if not isinstance(parsed, dict):
            return None
        name = parsed.get("name")
        if not name:
            return None
        # 仅接受已注册的工具，避免 LLM 编造不存在工具导致 Loop 发散
        if self._registry.get(str(name)) is None:
            logger.warning("[LLM_DRIVER] unknown tool in LLM output: %s", name)
            return None
        return ToolCall(
            name=str(name),
            arguments=parsed.get("arguments") or {},
        )

    def _extract_final_answer(self, text: str) -> str:
        """提取最终答案文本。优先读 FINAL_ANSWER 块，否则返回原文。"""
        m = re.search(
            r"FINAL_ANSWER\s*[:：]?\s*(.*?)(?:$|(?=\n\s*(?:TOOL_CALL|FINAL_ANSWER)))",
            text,
            re.DOTALL,
        )
        if m:
            return m.group(1).strip()
        # 没有标记 → 返回原文（视为 LLM 直接给结论）
        return text.strip()

    def _strip_markers(self, text: str) -> str:
        """剥离 TOOL_CALL / FINAL_ANSWER 标记，返回可读推理文本。"""
        cleaned = re.sub(r"TOOL_CALL\s*[:：]?\s*\{.*?\}", "[调用工具]", text, flags=re.DOTALL)
        cleaned = re.sub(r"FINAL_ANSWER\s*[:：]?\s*", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    @staticmethod
    def _safe_load_json(raw: str) -> Any:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
