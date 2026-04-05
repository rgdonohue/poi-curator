import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True)
class WorkbookSheet:
    name: str
    path: str


def fetch_xlsx_bytes(url: str, *, timeout_seconds: int = 90) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "poi-curator/0.1.0",
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def read_workbook_rows(data: bytes) -> dict[str, list[dict[str, str]]]:
    workbook = zipfile.ZipFile(io.BytesIO(data))
    shared_strings = read_shared_strings(workbook)
    sheets = read_workbook_sheets(workbook)
    return {
        sheet.name: read_sheet_rows(workbook, sheet.path, shared_strings)
        for sheet in sheets
    }


def read_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for node in root.findall(f"{{{MAIN_NS}}}si"):
        strings.append(
            "".join(
                text_node.text or ""
                for text_node in node.iterfind(f".//{{{MAIN_NS}}}t")
            )
        )
    return strings


def read_workbook_sheets(workbook: zipfile.ZipFile) -> list[WorkbookSheet]:
    root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    sheets: list[WorkbookSheet] = []
    for sheet in root.findall(f".//{{{MAIN_NS}}}sheet"):
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        if rel_id is None or rel_id not in rel_map:
            continue
        target = rel_map[rel_id]
        if not target.startswith("worksheets/"):
            continue
        sheets.append(WorkbookSheet(name=sheet.attrib.get("name", target), path=f"xl/{target}"))
    return sheets


def read_sheet_rows(
    workbook: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[dict[str, str]]:
    root = ET.fromstring(workbook.read(sheet_path))
    row_nodes = root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row")
    parsed_rows = [parse_row(row_node, shared_strings) for row_node in row_nodes]
    parsed_rows = [row for row in parsed_rows if any(value for value in row.values())]
    if not parsed_rows:
        return []
    headers = [value.strip() for _, value in sorted(parsed_rows[0].items())]
    data_rows: list[dict[str, str]] = []
    for row in parsed_rows[1:]:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            column = excel_column_name(index)
            record[header] = row.get(column, "").strip()
        if any(value for value in record.values()):
            data_rows.append(record)
    return data_rows


def parse_row(row_node: ET.Element, shared_strings: list[str]) -> dict[str, str]:
    cells: dict[str, str] = {}
    for cell in row_node.findall(f"{{{MAIN_NS}}}c"):
        reference = cell.attrib.get("r", "")
        column = "".join(char for char in reference if char.isalpha())
        if not column:
            continue
        cells[column] = cell_value(cell, shared_strings)
    return cells


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iterfind(f".//{{{MAIN_NS}}}t"))

    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""
    raw_value = value_node.text
    if cell_type == "s":
        return shared_strings[int(raw_value)]
    return raw_value


def excel_column_name(index: int) -> str:
    result = ""
    current = index + 1
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result


def best_sheet_by_headers(
    workbook_rows: dict[str, list[dict[str, str]]],
    required_header_sets: Iterable[set[str]],
) -> tuple[str, list[dict[str, str]]] | None:
    best: tuple[str, list[dict[str, str]], int] | None = None
    for sheet_name, rows in workbook_rows.items():
        if not rows:
            continue
        headers = {normalize_header(header) for header in rows[0]}
        score = sum(1 for required_set in required_header_sets if required_set & headers)
        if best is None or score > best[2]:
            best = (sheet_name, rows, score)
    if best is None:
        return None
    return best[0], best[1]


def normalize_header(header: str) -> str:
    return " ".join(header.strip().lower().split())
