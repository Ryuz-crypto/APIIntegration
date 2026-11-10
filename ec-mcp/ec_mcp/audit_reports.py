"""Bounded, sanitized export of audit rows without extra runtime dependencies."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from html import escape

from .security import redact_secrets

COLUMNS = ("ts_iso", "source", "tool", "action", "target", "result", "user")


def safe_cell(value: object) -> str:
    text = str(value if value is not None else "").replace("\r", " ").replace("\n", " ")[:500]
    # Prevent CSV/Excel formula interpretation even after leading whitespace.
    if text.lstrip().startswith(("=", "+", "-", "@", "\t")):
        text = "'" + text
    return text


def rows_for_export(events: list[dict]) -> list[list[str]]:
    return [[safe_cell(event.get(column, "")) for column in COLUMNS] for event in events[:500]]


def csv_report(events: list[dict]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(COLUMNS)
    writer.writerows(rows_for_export(events))
    return output.getvalue().encode("utf-8-sig")


def xlsx_report(events: list[dict]) -> bytes:
    rows = [list(COLUMNS), *rows_for_export(events)]
    xml_rows = []
    for row_number, row in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{chr(65 + i)}{row_number}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
            for i, value in enumerate(row)
        )
        xml_rows.append(f'<row r="{row_number}">{cells}</row>')
    sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>"
    files = {
        "[Content_Types].xml": '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Auditoria" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data.encode("utf-8"))
    return output.getvalue()


def pdf_report(events: list[dict]) -> bytes:
    """Produce a simple paginated text summary; long fields are abbreviated."""
    rows = rows_for_export(events)
    lines = ["AUDITORIA MCP - hasta 500 eventos", "UTC | origen | tool | accion | destino | resultado | usuario"]
    for row in rows:
        lines.append(" | ".join(value[:28] for value in row))
    pages = [lines[i:i + 45] for i in range(0, len(lines), 45)] or [lines]
    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    page_refs = []
    for page in pages:
        page_id = len(objects) + 1
        stream_id = page_id + 1
        page_refs.append(f"{page_id} 0 R")
        commands = ["BT /F1 7 Tf 25 805 Td 11 TL"]
        for line in page:
            encoded = line.encode("latin-1", "replace").decode("latin-1")
            encoded = encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({encoded}) Tj T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {stream_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(page_refs)}] >>".encode()
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)
