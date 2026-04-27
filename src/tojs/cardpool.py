from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import AbilityDefinition, CardDefinition

SPREADSHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
WORKBOOK_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def load_cardpool_from_xlsx(
    path: str | Path,
    ability_metadata_path: str | Path | None = None,
) -> list[CardDefinition]:
    workbook_path = Path(path)
    ability_metadata = _load_ability_metadata(workbook_path, ability_metadata_path)
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = _load_shared_strings(archive)
        worksheet = _load_first_worksheet(archive)
        rows = _read_rows(worksheet, shared_strings)

    if not rows:
        return []

    header = rows[0]
    return [
        _build_card(header, row, ability_metadata)
        for row in rows[1:]
        if any(cell != "" for cell in row) and not _is_header_row(header, row)
    ]


def _load_ability_metadata(
    workbook_path: Path,
    ability_metadata_path: str | Path | None,
) -> dict[str, dict[str, object]]:
    metadata_path = Path(ability_metadata_path) if ability_metadata_path is not None else (
        workbook_path.parent / "carddata" / "ability_metadata.json"
    )
    if not metadata_path.exists():
        return {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    cards = data.get("cards")
    if not isinstance(cards, dict):
        return {}
    return {str(card_no): value for card_no, value in cards.items() if isinstance(value, dict)}


def _load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("a:si", SPREADSHEET_NS):
        fragments = [text.text or "" for text in item.iterfind(".//a:t", SPREADSHEET_NS)]
        values.append("".join(fragments))
    return values


def _load_first_worksheet(archive: zipfile.ZipFile) -> ET.Element:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relation_map = {node.attrib["Id"]: node.attrib["Target"] for node in relationships}
    first_sheet = workbook.find("a:sheets", SPREADSHEET_NS)[0]
    relationship_id = first_sheet.attrib[f"{{{WORKBOOK_REL_NS}}}id"]
    target = relation_map[relationship_id]
    if not target.startswith("xl/"):
        target = f"xl/{target}"
    return ET.fromstring(archive.read(target))


def _read_rows(worksheet: ET.Element, shared_strings: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in worksheet.findall(".//a:sheetData/a:row", SPREADSHEET_NS):
        parsed_cells: dict[int, str] = {}
        for cell in row.findall("a:c", SPREADSHEET_NS):
            cell_ref = cell.attrib.get("r", "")
            column_index = _column_letters_to_index("".join(ch for ch in cell_ref if ch.isalpha()))
            cell_type = cell.attrib.get("t")
            value_node = cell.find("a:v", SPREADSHEET_NS)
            value = "" if value_node is None else value_node.text or ""
            if cell_type == "s" and value:
                value = shared_strings[int(value)]
            parsed_cells[column_index] = value
        if parsed_cells:
            last_index = max(parsed_cells)
            parsed_row = [parsed_cells.get(index, "") for index in range(last_index + 1)]
        else:
            parsed_row = []
        rows.append(parsed_row)
    return rows


def _build_card(
    header: list[str],
    row: list[str],
    ability_metadata: dict[str, dict[str, object]],
) -> CardDefinition:
    data = {key: row[index] if index < len(row) else "" for index, key in enumerate(header)}
    abilities_raw = json.loads(data["abilities"]) if data.get("abilities") else []
    card_metadata = ability_metadata.get(data["no"], {})
    merged_abilities_raw = _merge_ability_metadata(abilities_raw, card_metadata)
    abilities = tuple(
        AbilityDefinition(
            name=item.get("name", ""),
            text=item.get("text", ""),
            raw=item,
        )
        for item in merged_abilities_raw
    )
    return CardDefinition(
        card_no=data["no"],
        category=data["category"],
        rarity=data["rarity"],
        color=data["color"],
        name=data["name"],
        cp=_parse_optional_int(data.get("cp", "")),
        bp_by_level=_parse_bp_levels(data.get("bp", "")),
        abilities=abilities,
        race="" if data.get("race", "") == "-" else data.get("race", ""),
    )


def _merge_ability_metadata(
    abilities_raw: list[dict[str, object]],
    card_metadata: dict[str, object],
) -> list[dict[str, object]]:
    metadata_abilities = card_metadata.get("abilities")
    if not isinstance(metadata_abilities, list):
        return abilities_raw
    metadata_by_name = {
        item.get("name"): item
        for item in metadata_abilities
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    merged: list[dict[str, object]] = []
    for ability in abilities_raw:
        if not isinstance(ability, dict):
            continue
        metadata = metadata_by_name.get(ability.get("name"))
        if isinstance(metadata, dict):
            merged.append({**ability, **metadata})
        else:
            merged.append(ability)
    return merged


def _parse_bp_levels(bp_text: str) -> tuple[int, ...]:
    if not bp_text or bp_text == "-":
        return ()
    return tuple(int(part) for part in bp_text.split("/"))


def _parse_optional_int(value: str) -> int | None:
    if not value or value == "-":
        return None
    return int(value)


def _column_letters_to_index(column_letters: str) -> int:
    if not column_letters:
        return 0
    index = 0
    for letter in column_letters:
        index = index * 26 + (ord(letter.upper()) - ord("A") + 1)
    return index - 1


def _is_header_row(header: list[str], row: list[str]) -> bool:
    return row[: len(header)] == header
