import logging

import pytest

from app.core.logging.structured_logger import get_logger


class Widget:
    def __init__(self, log):
        self._log = log

    def do_info(self):
        self._log.info("hello", x=1)

    def do_warning(self):
        self._log.warning("degraded", reason="redis down")

    def do_operation_success(self):
        with self._log.operation(tenant_id="agb"):
            pass

    def do_operation_failure(self):
        with self._log.operation(tenant_id="agb"):
            raise ValueError("boom")


LOGGER_NAME = "tests.structured_logger"


@pytest.fixture
def log(caplog):
    # get_logger() sets propagate=False (deliberately, so it doesn't double-
    # print via app/main.py's root logging.basicConfig) -- caplog's handler
    # is attached to root by default, so it never sees these records unless
    # we attach it directly to this logger too.
    structured_logger = get_logger(LOGGER_NAME)
    underlying = logging.getLogger(LOGGER_NAME)
    underlying.addHandler(caplog.handler)
    underlying.setLevel(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
    yield structured_logger
    underlying.removeHandler(caplog.handler)


def test_info_captures_caller_method_name_and_fields(log, caplog):
    Widget(log).do_info()

    record = caplog.records[0]
    assert record.tag == "INFO"
    assert record.func_name == "Widget.do_info"
    assert record.structured_fields == {"x": 1}
    assert record.getMessage() == "hello"


def test_warning_tag_and_level(log, caplog):
    Widget(log).do_warning()

    record = caplog.records[0]
    assert record.tag == "WARNING"
    assert record.levelname == "WARNING"
    assert record.structured_fields == {"reason": "redis down"}


def test_operation_logs_init_then_end_on_success(log, caplog):
    Widget(log).do_operation_success()

    tags = [r.tag for r in caplog.records]
    assert tags == ["INIT", "END"]
    assert all(r.func_name == "Widget.do_operation_success" for r in caplog.records)
    assert caplog.records[0].structured_fields == {"tenant_id": "agb"}
    assert "duration_ms" in caplog.records[1].structured_fields


def test_operation_logs_init_then_error_and_reraises_on_failure(log, caplog):
    with pytest.raises(ValueError, match="boom"):
        Widget(log).do_operation_failure()

    tags = [r.tag for r in caplog.records]
    assert tags == ["INIT", "ERROR"]
    error_fields = caplog.records[1].structured_fields
    assert error_fields["tenant_id"] == "agb"
    assert error_fields["error_type"] == "ValueError"
    assert "duration_ms" in error_fields


def test_plain_function_uses_function_name_without_class(log, caplog):
    def standalone():
        log.debug("tracing")

    standalone()

    assert caplog.records[0].func_name == "standalone"
    assert caplog.records[0].tag == "DEBUG"
