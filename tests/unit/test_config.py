"""Unit-Tests für TOML-Konfiguration."""

from __future__ import annotations

from pathlib import Path

import pytest

from spock2.app import create_transport
from spock2.config.loader import load_config, load_config_result, save_config
from spock2.config.models import AppConfig, PollingConfig, PrintConfig
from spock2.domain.print_job import PrinterRole, PrintJob, PrintJobStatus, SourceType
from spock2.printing.file_transport import FileTransport


def test_example_toml_loads() -> None:
    example = Path(__file__).resolve().parents[2] / "config" / "spock2.example.toml"
    cfg = load_config(example)
    assert isinstance(cfg, AppConfig)
    assert cfg.polling.interval_s > 0
    assert cfg.polling.riker_interval_s > 0
    assert cfg.polling.picard_interval_s > 0
    assert cfg.print.transport in {"auto", "cups", "winspool", "file"}
    assert cfg.routing.station_role in {"kitchen", "counter"}
    assert "kitchen" in {p.role for p in cfg.printers.values()} or cfg.printers == {}
    if cfg.printers:
        first = next(iter(cfg.printers.values()))
        assert first.queue


def test_defaults() -> None:
    cfg = AppConfig()
    assert cfg.print.auto_complete_after_print is False
    assert cfg.print.transport == "auto"
    assert cfg.tls.ssl_verify is True
    assert cfg.polling.riker_interval_s == 3.0
    assert cfg.polling.picard_interval_s == 3.0


def test_polling_legacy_interval_alias() -> None:
    polling = PollingConfig.model_validate({"interval_s": 5.0})
    assert polling.riker_interval_s == 5.0
    assert polling.picard_interval_s == 5.0
    assert polling.interval_s == 5.0


def test_polling_separate_intervals() -> None:
    polling = PollingConfig.model_validate(
        {"riker_interval_s": 2.0, "picard_interval_s": 7.0}
    )
    assert polling.riker_interval_s == 2.0
    assert polling.picard_interval_s == 7.0
    assert polling.interval_s == 2.0  # Legacy spiegelt RIKER


def test_save_config_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "spock2.toml"
    cfg = AppConfig(
        print=PrintConfig(
            auto_print_new_orders=False,
            auto_print_new_notes=True,
            auto_complete_after_print=True,
            transport="file",
        ),
        polling=PollingConfig(riker_interval_s=2.5, picard_interval_s=4.0),
    )
    cfg.riker.base_url = "http://example.test:3000"
    cfg.picard.base_url = "http://example.test:5000"
    saved = save_config(path, cfg)
    assert saved == path
    assert path.is_file()

    loaded = load_config_result(path)
    assert loaded.path == path
    assert loaded.config.riker.base_url == "http://example.test:3000"
    assert loaded.config.picard.base_url == "http://example.test:5000"
    assert loaded.config.print.transport == "file"
    assert loaded.config.print.auto_complete_after_print is True
    assert loaded.config.print.auto_print_new_orders is False
    assert loaded.config.polling.riker_interval_s == 2.5
    assert loaded.config.polling.picard_interval_s == 4.0


def test_create_transport_file_mode() -> None:
    cfg = AppConfig(print=PrintConfig(transport="file"))
    transport = create_transport(cfg)
    assert isinstance(transport, FileTransport)


def test_auto_complete_hook_conditions() -> None:
    """Spiegel der Guard-Bedingungen aus ApplicationController._on_job_updated."""
    job = PrintJob(
        source_type=SourceType.RIKER_ORDER,
        source_id="42",
        target_role=PrinterRole.KITCHEN,
        profile_name="tsp100",
        payload_json="{}",
        payload_hash="abc",
        status=PrintJobStatus.COMPLETED,
    )
    cfg = AppConfig(print=PrintConfig(auto_complete_after_print=True))
    assert cfg.print.auto_complete_after_print
    assert job.source_type == SourceType.RIKER_ORDER
    assert job.status == PrintJobStatus.COMPLETED
    assert int(job.source_id) == 42

    note_job = job.model_copy(
        update={"source_type": SourceType.PICARD_NOTE, "source_id": "n1"}
    )
    assert note_job.source_type != SourceType.RIKER_ORDER


@pytest.mark.parametrize(
    ("flag", "status", "source", "expect"),
    [
        (False, PrintJobStatus.COMPLETED, SourceType.RIKER_ORDER, False),
        (True, PrintJobStatus.FAILED, SourceType.RIKER_ORDER, False),
        (True, PrintJobStatus.COMPLETED, SourceType.PICARD_NOTE, False),
        (True, PrintJobStatus.COMPLETED, SourceType.MANUAL_TEST, False),
        (True, PrintJobStatus.COMPLETED, SourceType.RIKER_ORDER, True),
    ],
)
def test_auto_complete_should_trigger(
    flag: bool,
    status: PrintJobStatus,
    source: SourceType,
    expect: bool,
) -> None:
    should = (
        flag
        and source == SourceType.RIKER_ORDER
        and status == PrintJobStatus.COMPLETED
    )
    assert should is expect
