import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.local_model_gateway_ru import (
    GatewayLimits,
    _is_reasoning_model,
    _managed_reasoning_options,
    _parse_sse_event,
    _validate_effort,
    _validate_messages,
)


def _event(delta: dict[str, object]) -> list[str]:
    return [json.dumps({"choices": [{"index": 0, "delta": delta, "finish_reason": None}]})]


def test_invalid_effort_falls_back_to_off():
    assert _validate_effort("unsupported") == "off"
    assert _validate_effort(None) == "off"
    assert _validate_effort("high") == "high"


def test_managed_opaque_model_ids_keep_reasoning_channel():
    assert _is_reasoning_model("custom-hf-e7cb624491843a8f27cac1e728539ed6bc64e7dbca8f8c373eb53dc4b4a602ff", "managed-llama-cpp")
    assert _is_reasoning_model("qwen3.8-27b", "openai-compatible-local")
    assert not _is_reasoning_model("qwen2.5-1.5b", "openai-compatible-local")


def test_qwen_reasoning_options_map_effort_to_supported_template_values():
    assert _managed_reasoning_options("off") == {"chat_template_kwargs": {"enable_thinking": False}}
    assert _managed_reasoning_options("low") == {"chat_template_kwargs": {"reasoning_effort": "low"}}
    assert _managed_reasoning_options("medium") == {"chat_template_kwargs": {"reasoning_effort": "medium"}}
    assert _managed_reasoning_options("high") == {"chat_template_kwargs": {"reasoning_effort": "xhigh"}}


def test_reasoning_content_is_kept_in_a_separate_channel():
    delta, tool_calls, done = _parse_sse_event(
        _event({"reasoning_content": "internal step"}),
        include_reasoning=True,
    )
    assert str(delta) == "internal step"
    assert delta.stream_channel == "reasoning"
    assert tool_calls == []
    assert done is False


def test_content_delta_remains_content_channel():
    delta, tool_calls, done = _parse_sse_event(_event({"content": "visible"}), include_reasoning=True)
    assert str(delta) == "visible"
    assert delta.stream_channel == "content"
    assert tool_calls == []
    assert done is False


def test_done_event_preserves_legacy_three_tuple_contract():
    delta, tool_calls, done = _parse_sse_event(["[DONE]"], include_reasoning=True)
    assert str(delta) == ""
    assert delta.stream_channel == "content"
    assert tool_calls == []
    assert done is True


def test_plain_assistant_history_is_allowed_without_tools():
    _validate_messages(
        (
            {"role": "user", "content": "Первый вопрос"},
            {"role": "assistant", "content": "Первый ответ"},
        ),
        GatewayLimits(),
        tools_enabled=False,
    )

def test_common_provider_finish_reasons_are_accepted():
    """incident.013: managed llama.cpp / external backends emit non-OpenAI finish
    reasons during reasoning+tool-call; they must not fail the stream."""
    for reason in ("function_call", "end_turn", "max_tokens", "stop_sequence", "eos", "pause"):
        delta, tc, done = _parse_sse_event(
            [json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": reason}]})],
            tools_enabled=True,
            include_reasoning=True,
        )
        assert done is False


def test_unknown_finish_reason_still_rejected():
    """fail-closed preserved: a truly unknown finish reason is still rejected."""
    try:
        _parse_sse_event(
            [json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": "bogus_xyz"}]})],
            tools_enabled=True,
        )
    except Exception:
        pass
    else:
        raise AssertionError("unknown finish_reason must be rejected")

