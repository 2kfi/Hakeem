# Arkan Fakoseh -  @2kfi on github
import asyncio
import ast
import logging
import operator
from datetime import datetime, timezone
from typing import Any

from core.schemas import ToolCallResult

logger = logging.getLogger(__name__)


async def run_internal_tool(tool_name: str, params: dict[str, Any], timeout: float = 10.0) -> ToolCallResult:
    start = asyncio.get_event_loop().time()
    try:
        if tool_name == "get_time":
            result = await _get_time(params)
        elif tool_name == "get_weather":
            result = await _get_weather(params)
        elif tool_name == "calculator":
            result = await _calculator(params)
        else:
            return ToolCallResult(tool_name=tool_name, success=False, error=f"Unknown tool: {tool_name}", duration_ms=0)

        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        return ToolCallResult(tool_name=tool_name, success=True, result=result, duration_ms=duration)
    except Exception as e:
        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        logger.error(f"Internal tool {tool_name} failed: {e}")
        return ToolCallResult(tool_name=tool_name, success=False, error=str(e), duration_ms=duration)


async def _get_time(params: dict[str, Any]) -> dict[str, Any]:
    await asyncio.sleep(0.01)
    tz = params.get("tz", "UTC")
    now = datetime.now(timezone.utc)
    return {
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "iso": now.isoformat(),
        "timezone": tz,
    }


async def _get_weather(params: dict[str, Any]) -> dict[str, Any]:
    location = params.get("location", "unknown")
    await asyncio.sleep(0.05)
    return {
        "location": location,
        "temperature": 22,
        "condition": "partly cloudy",
        "humidity": 65,
        "wind_speed": 12,
        "units": "metric",
    }


_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> float | int:
    node = ast.parse(expr.strip(), mode="eval")
    return _eval_node(node.body)


def _eval_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {type(node.value).__name__}")
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    raise ValueError(f"Unsupported expression: {type(node).__name__}")


async def _calculator(params: dict[str, Any]) -> dict[str, Any]:
    expression = params.get("expression", "0")
    result = _safe_eval(expression)
    return {"expression": expression, "result": result, "type": type(result).__name__}