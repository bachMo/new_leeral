import logging

import pytest

from app.core.errors import AppError, ErrorCode
from app.core.logging import log_step

logger = logging.getLogger("leeral.tests.logging")


def test_log_step_success_logs_started_and_finished(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=logger.name), log_step(
        logger, "widget_built", widget="gizmo"
    ) as out:
        out["count"] = 3

    started = next(r for r in caplog.records if r.message == "widget_built_started")
    finished = next(r for r in caplog.records if r.message == "widget_built_finished")
    assert started.widget == "gizmo"
    assert finished.widget == "gizmo"
    assert finished.count == 3
    assert isinstance(finished.duration_ms, int)
    assert finished.levelname == "INFO"


def test_log_step_app_error_logs_warning_with_code(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.INFO, logger=logger.name),
        pytest.raises(AppError),
        log_step(logger, "widget_built", widget="gizmo"),
    ):
        raise AppError(ErrorCode.VALIDATION_FAILED)

    failed = next(r for r in caplog.records if r.message == "widget_built_failed")
    assert failed.levelname == "WARNING"
    assert failed.code == ErrorCode.VALIDATION_FAILED.value
    assert failed.exc_info is None
    assert isinstance(failed.duration_ms, int)


def test_log_step_unexpected_error_logs_exception_with_trace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        caplog.at_level(logging.INFO, logger=logger.name),
        pytest.raises(ValueError),
        log_step(logger, "widget_built", widget="gizmo"),
    ):
        raise ValueError("boom")

    failed = next(r for r in caplog.records if r.message == "widget_built_failed")
    assert failed.levelname == "ERROR"
    assert failed.exc_info is not None
    assert isinstance(failed.duration_ms, int)
