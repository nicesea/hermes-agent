"""Stat-style Slack approvals belong to the teammate who requested the work."""

from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.base import ExecApprovalPrompt, SendResult
from plugins.platforms.slack.adapter import SlackAdapter


@pytest.mark.asyncio
async def test_slack_approval_only_requester_can_click():
    adapter = SlackAdapter(PlatformConfig(extra={"approval_requester_only": True}))
    adapter._app = object()
    adapter._send_interactive_prompt = AsyncMock(return_value=SendResult(
        success=True, message_id="123.456",
    ))
    adapter._finalize_interactive_message = AsyncMock()
    prompt = ExecApprovalPrompt(
        chat_id="C_GROWTH", session_key="session", text="Approve?",
        actions=[("Allow Once", "once", "primary")], command="run_analytics_sql",
        description="cohort table", smart_denied=False,
        metadata={"scope_id": "T_OWNER", "user_id": "U_REQUESTER"},
    )
    result = await adapter._send_exec_approval_prompt(prompt)
    assert result.success
    marker = ("T_OWNER", "123.456")
    assert adapter._approval_requesters[marker] == ("T_OWNER", "U_REQUESTER")
    adapter._approval_resolved[marker] = False

    adapter._begin_interaction = AsyncMock(return_value=(
        "T_OWNER", "hermes_approve_once", "session", {}, "123.456",
        "C_GROWTH", "other", "U_OTHER",
    ))
    with patch("tools.approval.resolve_gateway_approval") as resolve:
        await adapter._handle_approval_action(AsyncMock(), {}, {})
        resolve.assert_not_called()
    assert adapter._approval_resolved[marker] is False

    adapter._begin_interaction.return_value = (
        "T_OWNER", "hermes_approve_once", "session", {}, "123.456",
        "C_GROWTH", "requester", "U_REQUESTER",
    )
    with patch("tools.approval.resolve_gateway_approval", return_value=1) as resolve:
        await adapter._handle_approval_action(AsyncMock(), {}, {})
        resolve.assert_called_once_with("session", "once")
    assert marker not in adapter._approval_requesters
    adapter._finalize_interactive_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_slack_approval_requires_requester_metadata_before_posting():
    adapter = SlackAdapter(PlatformConfig(extra={"approval_requester_only": True}))
    adapter._app = object()
    adapter._send_interactive_prompt = AsyncMock()
    prompt = ExecApprovalPrompt(
        chat_id="C_GROWTH", session_key="session", text="Approve?",
        actions=[("Allow Once", "once", "primary")], command="run_analytics_sql",
        description="cohort table", smart_denied=False, metadata=None,
    )
    result = await adapter._send_exec_approval_prompt(prompt)
    assert not result.success
    adapter._send_interactive_prompt.assert_not_awaited()
