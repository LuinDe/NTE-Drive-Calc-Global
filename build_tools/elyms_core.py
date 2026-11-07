"""Extend the two embedded JSON resources used by the bundled 2.3.1 inventory projector.

This is a data-only adaptation of a pinned x64 PE. The upstream Rust working tree
for this exact Core was not distributed. We keep all original resource bytes and
redirect the two existing decompression descriptors to a new read-only PE section.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import zlib
from contextlib import closing
from pathlib import Path


BASE_CORE_SHA256 = "1f875858409ad47eed83ded7991d7a3133eb4afafebf2c2b09cd52802c7b2fed"

# Offsets are specific to BASE_CORE_SHA256. Each site contains:
# mov eax, raw_size; mov ecx, compressed_size; lea rdx, [rip + compressed_data].
# Values are (descriptor file offset, resource file offset, plain size, compressed size).
CHARACTERS = (0x73909, 0x17DB3C, 4055, 903)
EQUIPMENT = (0x7397D, 0x178203, 71661, 9267)


def _elyms_rows(database: Path) -> tuple[dict, dict]:
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        name, element = db.execute(
            "SELECT name_zh, element_type FROM character WHERE character_id=1090"
        ).fetchone()
        core_id, = db.execute("SELECT core_item_id FROM equipment_plan WHERE character_id=1090").fetchone()
        cells = db.execute(
            'SELECT row, "column", anchor_item_id FROM equipment_plan_cell '
            'WHERE character_id=1090 ORDER BY row, "column"'
        ).fetchall()
        source_path = "DataTable/Character/DT_Character.json"
        source_sha, = db.execute(
            "SELECT sha256 FROM source_file WHERE relative_path=?", ("CN-1.5.4/" + source_path,)
        ).fetchone()
    if name != "曳尔沐" or not element.endswith("::CHARACTER_ELEMENT_TYPE_COSMOS"):
        raise ValueError("Expected the CN retail Elyms record")
    character = {"attribute": "光", "codename": "Elyms", "name_en": "Elyms", "name_zh": name,
                 "source": {"path": source_path, "row": "1090", "sha256": source_sha}, "verified": True}
    plan = {"recommended_core": core_id,
            "recommended_modules": [{"column": col, "item_id": item, "row": row}
                                    for row, col, item in cells if item is not None],
            "valid_cells": [{"column": col, "row": row} for row, col, _ in cells]}
    if len(cells) != 20 or len(plan["recommended_modules"]) != 7:
        raise ValueError("Incomplete Elyms equipment plan")
    return character, plan


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def patch_core(original: bytes, database: Path) -> bytes:
    if hashlib.sha256(original).hexdigest() != BASE_CORE_SHA256:
        raise ValueError("Unsupported nte-core.exe; expected the original 2.3.1 component")
    image = bytearray(original)
    pe, = struct.unpack_from("<I", image, 0x3C)
    section_count, = struct.unpack_from("<H", image, pe + 6)
    optional_size, = struct.unpack_from("<H", image, pe + 20)
    optional = pe + 24
    section_alignment, file_alignment = struct.unpack_from("<II", image, optional + 32)
    section_table = optional + optional_size
    sections = [struct.unpack_from("<8sIIII", image, section_table + i * 40) for i in range(section_count)]
    new_header = section_table + section_count * 40
    if new_header + 40 > sections[0][4] or any(image[new_header:new_header + 40]):
        raise ValueError("No free PE section-header slot")
    if len(image) != max(offset + size for _, _, _, size, offset in sections):
        raise ValueError("Unexpected PE overlay")
    new_rva = _align(max(rva + vsize for _, vsize, rva, _, _ in sections), section_alignment)
    new_file_offset = _align(len(image), file_alignment)

    def file_rva(offset: int) -> int:
        for _, _, rva, size, start in sections:
            if start <= offset < start + size:
                return rva + offset - start
        raise ValueError(f"Unmapped original file offset {offset:#x}")

    char, plan = _elyms_rows(database)
    section = bytearray()
    for descriptor, table, record in [(CHARACTERS, "characters", char), (EQUIPMENT, "plans", plan)]:
        site, offset, plain_size, packed_size = descriptor
        next_rva = file_rva(site) + 17

        def reference(raw: int, packed: int, rva: int) -> bytes:
            return (b"\xb8" + struct.pack("<I", raw) + b"\xb9" + struct.pack("<I", packed)
                    + b"\x48\x8d\x15" + struct.pack("<i", rva - next_rva))

        if image[site:site + 17] != reference(plain_size, packed_size, file_rva(offset)):
            raise ValueError(f"Unexpected {table} decompression descriptor")
        raw = zlib.decompress(original[offset:offset + packed_size])
        data = json.loads(raw)
        if len(raw) != plain_size or "1090" in data[table]:
            raise ValueError(f"Unexpected source table: {table}")
        if table == "plans":
            item_ids = [plan["recommended_core"], *(m["item_id"] for m in plan["recommended_modules"])]
            if any(item not in data["items"] for item in item_ids):
                raise ValueError("Elyms plan references an unmapped equipment item")
        data[table]["1090"] = record
        updated = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        packed = zlib.compress(updated, 9)
        image[site:site + 17] = reference(len(updated), len(packed), new_rva + len(section))
        section.extend(packed)

    raw_size = _align(len(section), file_alignment)
    image.extend(bytes(new_file_offset - len(image)) + section + bytes(raw_size - len(section)))
    # IMAGE_SCN_CNT_INITIALIZED_DATA | IMAGE_SCN_MEM_READ. No executable/writable access.
    struct.pack_into("<8sIIIIIIHHI", image, new_header, b".ntedata", len(section), new_rva,
                     raw_size, new_file_offset, 0, 0, 0, 0, 0x40000040)
    struct.pack_into("<H", image, pe + 6, section_count + 1)
    initialized, = struct.unpack_from("<I", image, optional + 8)
    struct.pack_into("<I", image, optional + 8, initialized + raw_size)
    struct.pack_into("<I", image, optional + 56, _align(new_rva + len(section), section_alignment))
    struct.pack_into("<I", image, optional + 64, 0)
    checksum = sum(word for (word,) in struct.iter_unpack("<H", image))
    while checksum > 0xFFFF:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    struct.pack_into("<I", image, optional + 64, checksum + len(image))
    return bytes(image)
