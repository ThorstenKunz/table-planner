import io
import logging

from table_planner.logging_config import ColorFormatter, _colors_enabled


def _record(level: int) -> logging.LogRecord:
    return logging.LogRecord(
        name="table_planner.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg="Example",
        args=(),
        exc_info=None,
    )


def test_color_formatter_colors_warning_and_logger_name() -> None:
    output = ColorFormatter(use_color=True).format(_record(logging.WARNING))

    assert "\x1b[33mWARNING\x1b[0m" in output
    assert "\x1b[35mtable_planner.test\x1b[0m" in output


def test_color_formatter_can_emit_plain_text() -> None:
    output = ColorFormatter(use_color=False).format(_record(logging.ERROR))

    assert "\x1b[" not in output
    assert "ERROR - table_planner.test - Example" in output


def test_color_mode_can_be_disabled() -> None:
    stream = io.StringIO()
    assert _colors_enabled("never", stream=stream) is False
    assert _colors_enabled("always", stream=stream) is True
    assert _colors_enabled("auto", stream=stream) is False
