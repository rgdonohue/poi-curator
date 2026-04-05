import io
import zipfile

from poi_curator_enrichment.xlsx_reader import best_sheet_by_headers, read_workbook_rows


def test_read_workbook_rows_parses_simple_shared_string_sheet() -> None:
    workbook_bytes = build_test_workbook()

    rows = read_workbook_rows(workbook_bytes)

    assert "Registers" in rows
    assert rows["Registers"][0]["Property Name"] == "Palace of the Governors"
    assert rows["Registers"][0]["City"] == "Santa Fe"


def test_best_sheet_by_headers_prefers_register_sheet() -> None:
    rows = {
        "Notes": [{"Foo": "bar"}],
        "Registers": [
            {
                "Property Name": "Palace of the Governors",
                "City": "Santa Fe",
                "County": "Santa Fe",
            }
        ],
    }

    best = best_sheet_by_headers(
        rows,
        required_header_sets=(
            {"property name", "name"},
            {"city"},
            {"county"},
        ),
    )

    assert best is not None
    assert best[0] == "Registers"


def build_test_workbook() -> bytes:
    content_types = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
            (
                '  <Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            ),
            '  <Default Extension="xml" ContentType="application/xml"/>',
            (
                '  <Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            ),
            (
                '  <Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            ),
            (
                '  <Override PartName="/xl/sharedStrings.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            ),
            "</Types>",
        ]
    )
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets>
  <sheet name="Registers" sheetId="1" r:id="rId1"/>
 </sheets>
</workbook>"""
    workbook_rels = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            (
                '  <Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
            ),
            "</Relationships>",
        ]
    )
    shared_strings = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="6">
  <si><t>Property Name</t></si>
  <si><t>City</t></si>
  <si><t>County</t></si>
  <si><t>Palace of the Governors</t></si>
  <si><t>Santa Fe</t></si>
  <si><t>Santa Fe</t></si>
</sst>"""
    sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
      <c r="C1" t="s"><v>2</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>3</v></c>
      <c r="B2" t="s"><v>4</v></c>
      <c r="C2" t="s"><v>5</v></c>
    </row>
  </sheetData>
</worksheet>"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/sharedStrings.xml", shared_strings)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()
