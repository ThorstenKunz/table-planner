import asyncio
from unittest.mock import AsyncMock, Mock

from table_planner.discord_utils import safe_response_defer, safe_response_send


def _interaction(response_done: bool) -> Mock:
    interaction = Mock()
    interaction.response.is_done.return_value = response_done
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def test_safe_response_defer_acknowledges_pending_interaction() -> None:
    interaction = _interaction(response_done=False)

    result = asyncio.run(safe_response_defer(interaction))

    assert result is True
    interaction.response.defer.assert_awaited_once_with()


def test_safe_response_send_uses_followup_after_defer() -> None:
    interaction = _interaction(response_done=True)

    result = asyncio.run(safe_response_send(interaction, "Done", ephemeral=True))

    assert result is True
    interaction.response.send_message.assert_not_awaited()
    interaction.followup.send.assert_awaited_once_with("Done", ephemeral=True)
