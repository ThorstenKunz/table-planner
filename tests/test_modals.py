import asyncio
from unittest.mock import AsyncMock, Mock

from table_planner.modals import _cleanup_orphaned_table_message


def test_orphaned_table_message_is_disabled_and_deleted() -> None:
    message = Mock()
    message.id = 123
    message.edit = AsyncMock()
    message.delete = AsyncMock()

    asyncio.run(_cleanup_orphaned_table_message(message, "table-1"))

    message.edit.assert_awaited_once_with(view=None)
    message.delete.assert_awaited_once_with()
