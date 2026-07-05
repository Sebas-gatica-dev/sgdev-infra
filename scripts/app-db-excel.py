#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def die(message):
    print(f"[sgdev-db-excel] ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def col_letter(index):
    value = ""
    while index:
        index, rem = divmod(index - 1, 26)
        value = chr(65 + rem) + value
    return value


def cell_ref(row_index, col_index):
    return f"{col_letter(col_index)}{row_index}"


def ref_to_col_index(ref):
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return 0
    index = 0
    for char in letters.group(1):
        index = index * 26 + (ord(char) - 64)
    return index


def xml_text(value):
    text = "" if value is None else str(value)
    attrs = ' xml:space="preserve"' if text != text.strip() or "\n" in text or "\r" in text or "\t" in text else ""
    return f"<t{attrs}>{escape(text)}</t>"


def normalize_cell_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return repr(value)
    return str(value)


def cell_xml(row_index, col_index, value):
    if value is None:
        return ""
    value = normalize_cell_value(value)
    return f'<c r="{cell_ref(row_index, col_index)}" t="inlineStr"><is>{xml_text(value)}</is></c>'


def sheet_xml(rows):
    max_row = max(len(rows), 1)
    max_col = max([len(row) for row in rows] + [1])
    if max_row > 1048576:
        die("Excel limit exceeded: more than 1,048,576 rows in one sheet")
    if max_col > 16384:
        die("Excel limit exceeded: more than 16,384 columns in one sheet")

    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{NS_MAIN}" xmlns:r="{NS_REL}">',
        f'<dimension ref="A1:{cell_ref(max_row, max_col)}"/>',
        "<sheetData>",
    ]
    for row_index, row in enumerate(rows, 1):
        cells = [cell_xml(row_index, col_index, value) for col_index, value in enumerate(row, 1)]
        out.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    out.extend(["</sheetData>", "</worksheet>"])
    return "".join(out)


def safe_sheet_name(name, used):
    base = re.sub(r"[\[\]:*?/\\]", "_", name or "table").strip() or "table"
    base = base[:31]
    candidate = base
    counter = 2
    while candidate.lower() in used:
        suffix = f"_{counter}"
        candidate = (base[: 31 - len(suffix)] + suffix) or f"sheet{counter}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def read_table_list(workdir):
    tables_path = workdir / "tables.tsv"
    if not tables_path.exists():
        die(f"missing {tables_path}")
    tables = []
    with tables_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            file_id = row.get("file") or ""
            table_name = row.get("table") or ""
            if not file_id or not table_name:
                continue
            columns_path = workdir / f"{file_id}.columns"
            if columns_path.exists():
                columns = [line.rstrip("\n") for line in columns_path.read_text(encoding="utf-8").splitlines()]
            else:
                columns = []
            tables.append({
                "file": file_id,
                "table": table_name,
                "scope": row.get("scope") or "full",
                "columns": columns,
            })
    return tables


def iter_json_rows(path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                die(f"expected JSON object in {path}")
            yield value


def workbook_xml(sheets):
    rows = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}">',
        "<sheets>",
    ]
    for index, sheet in enumerate(sheets, 1):
        state = ' state="hidden"' if sheet.get("hidden") else ""
        rows.append(
            f'<sheet name="{escape(sheet["name"])}" sheetId="{index}" r:id="rId{index}"{state}/>'
        )
    rows.extend(["</sheets>", "</workbook>"])
    return "".join(rows)


def workbook_rels_xml(sheets):
    rows = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<Relationships xmlns="{NS_PKG_REL}">',
    ]
    for index, _sheet in enumerate(sheets, 1):
        rows.append(
            f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        )
    rows.append("</Relationships>")
    return "".join(rows)


def root_rels_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{NS_PKG_REL}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def content_types_xml(sheets):
    rows = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for index, _sheet in enumerate(sheets, 1):
        rows.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    rows.append("</Types>")
    return "".join(rows)


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def core_xml():
    now = utc_now_iso()
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:creator>sgdev-infra</dc:creator>"
        "<cp:lastModifiedBy>sgdev-infra</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def app_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>sgdev-infra</Application>"
        "</Properties>"
    )


def pack(args):
    workdir = Path(args.workdir)
    output = Path(args.output)
    tables = read_table_list(workdir)
    used_names = set()
    manifest_rows = [
        ["sgdev_db_excel_version", "1"],
        ["app_slug", args.app_slug or ""],
        ["app_id", args.app_id or ""],
        ["engine", args.engine or ""],
        ["database", args.database or ""],
        ["service", args.service or ""],
        ["exported_at_utc", utc_now_iso()],
        [],
        ["table", "sheet", "scope", "columns_json", "row_count"],
    ]
    sheets = [{"name": "_sgdev_manifest", "rows": manifest_rows, "hidden": True}]

    for table in tables:
        sheet_name = safe_sheet_name(table["table"].split(".")[-1], used_names)
        columns = list(table["columns"])
        data_path = workdir / f"{table['file']}.jsonl"
        data_rows = list(iter_json_rows(data_path))
        if not columns and data_rows:
            seen = []
            for row in data_rows:
                for key in row:
                    if key not in seen:
                        seen.append(key)
            columns = seen
        rows = [columns]
        for data_row in data_rows:
            rows.append([data_row.get(column) for column in columns])
        table["sheet"] = sheet_name
        table["row_count"] = len(data_rows)
        manifest_rows.append([
            table["table"],
            sheet_name,
            table["scope"],
            json.dumps(columns, ensure_ascii=True, separators=(",", ":")),
            str(len(data_rows)),
        ])
        sheets.append({"name": sheet_name, "rows": rows, "hidden": False})

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml(sheets))
        archive.writestr("_rels/.rels", root_rels_xml())
        archive.writestr("docProps/core.xml", core_xml())
        archive.writestr("docProps/app.xml", app_xml())
        archive.writestr("xl/workbook.xml", workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml(sheets))
        for index, sheet in enumerate(sheets, 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(sheet["rows"]))

    print(str(output))


def parse_shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values = []
    for si in root.findall(f"{{{NS_MAIN}}}si"):
        parts = [node.text or "" for node in si.findall(f".//{{{NS_MAIN}}}t")]
        values.append("".join(parts))
    return values


def read_cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{{{NS_MAIN}}}t"))
    value_node = cell.find(f"{{{NS_MAIN}}}v")
    if value_node is None:
        return None
    value = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "true" if value == "1" else "false"
    return value


def sheet_rows(archive, path, shared_strings):
    root = ET.fromstring(archive.read(path))
    rows = []
    for row_node in root.findall(f".//{{{NS_MAIN}}}row"):
        values = []
        for cell in row_node.findall(f"{{{NS_MAIN}}}c"):
            col_index = ref_to_col_index(cell.attrib.get("r", "")) or (len(values) + 1)
            while len(values) < col_index - 1:
                values.append(None)
            values.append(read_cell_value(cell, shared_strings))
        rows.append(values)
    return rows


def workbook_sheet_map(archive):
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {}
    for rel in rels.findall(f"{{{NS_PKG_REL}}}Relationship"):
        target = rel.attrib.get("Target", "")
        if target.startswith("/"):
            target_path = target.lstrip("/")
        else:
            target_path = "xl/" + target
        rel_map[rel.attrib.get("Id", "")] = target_path

    sheets = {}
    for sheet in workbook.findall(f".//{{{NS_MAIN}}}sheet"):
        name = sheet.attrib.get("name", "")
        rel_id = sheet.attrib.get(f"{{{NS_REL}}}id", "")
        if name and rel_id in rel_map:
            sheets[name] = rel_map[rel_id]
    return sheets


def parse_manifest(rows):
    manifest = {"tables": []}
    table_header_index = None
    for index, row in enumerate(rows):
        if not row:
            continue
        key = row[0]
        if key == "table":
            table_header_index = index
            break
        if key:
            manifest[str(key)] = row[1] if len(row) > 1 else ""
    if table_header_index is None:
        die("workbook does not include a valid _sgdev_manifest sheet")
    for row in rows[table_header_index + 1:]:
        if not row or not row[0]:
            continue
        columns_json = row[3] if len(row) > 3 and row[3] else "[]"
        try:
            columns = json.loads(columns_json)
        except json.JSONDecodeError:
            columns = []
        manifest["tables"].append({
            "table": row[0],
            "sheet": row[1] if len(row) > 1 else "",
            "scope": row[2] if len(row) > 2 and row[2] else "full",
            "columns": columns,
        })
    return manifest


def write_table_files(workdir, manifest, sheets, archive, shared_strings):
    with (workdir / "tables.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=["file", "table", "scope"])
        writer.writeheader()
        for index, table in enumerate(manifest["tables"], 1):
            file_id = f"t{index:03d}"
            writer.writerow({"file": file_id, "table": table["table"], "scope": table["scope"]})
            sheet_name = table["sheet"]
            if sheet_name not in sheets:
                die(f"sheet not found in workbook: {sheet_name}")
            rows = sheet_rows(archive, sheets[sheet_name], shared_strings)
            header = [str(value) if value is not None else "" for value in (rows[0] if rows else [])]
            columns = [column for column in (table.get("columns") or header) if column]
            if header and header != columns:
                columns = [column for column in header if column]
            (workdir / f"{file_id}.columns").write_text("\n".join(columns) + ("\n" if columns else ""), encoding="utf-8")
            with (workdir / f"{file_id}.jsonl").open("w", encoding="utf-8") as data_file:
                for raw_row in rows[1:]:
                    if not raw_row:
                        continue
                    row = {}
                    has_value = False
                    for col_index, column in enumerate(columns):
                        value = raw_row[col_index] if col_index < len(raw_row) else None
                        row[column] = value
                        if value is not None:
                            has_value = True
                    if has_value:
                        data_file.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")


def unpack(args):
    input_path = Path(args.input)
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(input_path, "r") as archive:
        sheets = workbook_sheet_map(archive)
        if "_sgdev_manifest" not in sheets:
            die("workbook is missing _sgdev_manifest")
        shared_strings = parse_shared_strings(archive)
        manifest_rows = sheet_rows(archive, sheets["_sgdev_manifest"], shared_strings)
        manifest = parse_manifest(manifest_rows)
        expected_slug = args.app_slug or ""
        expected_app_id = args.app_id or ""
        found_slug = manifest.get("app_slug", "")
        found_app_id = manifest.get("app_id", "")
        if not args.allow_cross_app and expected_slug and found_slug and found_slug != expected_slug:
            die(f"workbook app_slug is {found_slug}, not {expected_slug}")
        if not args.allow_cross_app and expected_app_id and found_app_id and found_app_id != expected_app_id:
            die(f"workbook app_id is {found_app_id}, not {expected_app_id}")
        (workdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
        write_table_files(workdir, manifest, sheets, archive, shared_strings)
    print(str(workdir))


def quote_pg_ident(part):
    return '"' + part.replace('"', '""') + '"'


def quote_mysql_ident(part):
    return "`" + part.replace("`", "``") + "`"


def quote_table(name, dialect):
    parts = [part for part in name.split(".") if part]
    if dialect == "postgres":
        return ".".join(quote_pg_ident(part) for part in parts)
    return ".".join(quote_mysql_ident(part) for part in parts)


def quote_column(name, dialect):
    return quote_pg_ident(name) if dialect == "postgres" else quote_mysql_ident(name)


def sql_literal(value, dialect):
    if value is None:
        return "NULL"
    text = str(value)
    if dialect == "mysql":
        text = text.replace("\\", "\\\\")
    return "'" + text.replace("'", "''") + "'"


def sql(args):
    workdir = Path(args.workdir)
    output = Path(args.output)
    tables = read_table_list(workdir)
    manifest_path = workdir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    app_id = args.app_id or manifest.get("app_id") or ""
    dialect = "mysql" if args.dialect in ("mysql", "mariadb") else "postgres"
    app_id_column = args.app_id_column or "app_id"
    statements = ["BEGIN;"]
    if dialect == "mysql":
        statements.append("SET FOREIGN_KEY_CHECKS=0;")
    elif args.mode == "replace-project":
        statements.append("SET CONSTRAINTS ALL DEFERRED;")

    for table in tables:
        columns = table["columns"]
        if not columns:
            continue
        table_name = quote_table(table["table"], dialect)
        if args.mode == "replace-project" and app_id and app_id_column in columns:
            statements.append(
                f"DELETE FROM {table_name} WHERE {quote_column(app_id_column, dialect)} = {sql_literal(app_id, dialect)};"
            )
        data_path = workdir / f"{table['file']}.jsonl"
        batch = []
        column_sql = ", ".join(quote_column(column, dialect) for column in columns)
        for row in iter_json_rows(data_path):
            values = ", ".join(sql_literal(row.get(column), dialect) for column in columns)
            batch.append(f"({values})")
            if len(batch) >= args.batch_size:
                statements.append(f"INSERT INTO {table_name} ({column_sql}) VALUES\n" + ",\n".join(batch) + ";")
                batch = []
        if batch:
            statements.append(f"INSERT INTO {table_name} ({column_sql}) VALUES\n" + ",\n".join(batch) + ";")

    if dialect == "mysql":
        statements.append("SET FOREIGN_KEY_CHECKS=1;")
    statements.append("COMMIT;")
    output.write_text("\n".join(statements) + "\n", encoding="utf-8")
    print(str(output))


def main():
    parser = argparse.ArgumentParser(description="Pack and unpack SGDEV database Excel files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("--workdir", required=True)
    pack_parser.add_argument("--output", required=True)
    pack_parser.add_argument("--app-slug", default="")
    pack_parser.add_argument("--app-id", default="")
    pack_parser.add_argument("--engine", default="")
    pack_parser.add_argument("--database", default="")
    pack_parser.add_argument("--service", default="")
    pack_parser.set_defaults(func=pack)

    unpack_parser = subparsers.add_parser("unpack")
    unpack_parser.add_argument("--input", required=True)
    unpack_parser.add_argument("--workdir", required=True)
    unpack_parser.add_argument("--app-slug", default="")
    unpack_parser.add_argument("--app-id", default="")
    unpack_parser.add_argument("--allow-cross-app", action="store_true")
    unpack_parser.set_defaults(func=unpack)

    sql_parser = subparsers.add_parser("sql")
    sql_parser.add_argument("--workdir", required=True)
    sql_parser.add_argument("--output", required=True)
    sql_parser.add_argument("--dialect", required=True, choices=["postgres", "mysql", "mariadb"])
    sql_parser.add_argument("--mode", default="insert", choices=["insert", "replace-project"])
    sql_parser.add_argument("--app-id", default="")
    sql_parser.add_argument("--app-id-column", default="app_id")
    sql_parser.add_argument("--batch-size", type=int, default=250)
    sql_parser.set_defaults(func=sql)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
