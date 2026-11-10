"""Tests for bounded monitoring and safe audit reports."""

from __future__ import annotations

import csv
import io
import zipfile
from xml.etree import ElementTree

from starlette.testclient import TestClient

import ec_mcp.admin as admin
import ec_mcp.system_monitor as monitor
from ec_mcp.audit_reports import csv_report, pdf_report, xlsx_report


def test_cpu_requires_two_real_samples(tmp_path, monkeypatch):
    path = tmp_path / "stat"
    monkeypatch.setattr(monitor, "_CPU_PREVIOUS", None)
    path.write_text("cpu 100 0 100 800 0 0 0 0\n")
    assert monitor._cpu_sample(path) is None
    path.write_text("cpu 150 0 150 900 0 0 0 0\n")
    assert monitor._cpu_sample(path) == 50.0


def test_exports_are_bounded_and_safe():
    events = [{"ts_iso": "2026-11-09T00:00:00Z", "tool": "=SUM(1,2)",
               "action": "GET https://user:secret@example.test/api?token=private", "user": "analyst"}] * 510
    data = csv_report(events).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(data)))
    assert len(rows) == 501
    assert rows[1][2].startswith("'=")
    assert "private" not in data
    assert "user:secret" not in data
    with zipfile.ZipFile(io.BytesIO(xlsx_report(events))) as archive:
        root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert root.tag.endswith("worksheet")
        assert b"private" not in archive.read("xl/worksheets/sheet1.xml")
    pdf = pdf_report(events)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf
    assert b"private" not in pdf


def test_reports_and_host_metrics_require_admin(monkeypatch):
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "viewer", "role": "viewer"})
    with TestClient(admin.build_admin_app()) as client:
        assert client.get("/api/monitor/host").status_code == 403
        assert client.get("/api/audit/report?format=csv").status_code == 403
