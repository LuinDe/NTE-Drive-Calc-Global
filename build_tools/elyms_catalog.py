"""Apply the CN 1.5.4 Elyms supplement to clean, disposable 2.3.1 installer staging files."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
BASE_HASHES = {
    "game": "AF810B5A8ADB82625BD023B11D2B348948B8649CE79D14E039ADA018F5217C5D",
    "reference": "500414EADB0EB59710271D5D064616523089EACB588D05BB0D784E570E0DD524",
}
UI_FILES = (
    ("characters", "1090", "1090.png", 256, 256),
    ("character_arts", "1090", "1090.webp", 1000, 1185),
    ("fork_items", "fork_elyms", "fork_elyms.png", 256, 256),
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def update_catalog(folder: Path, scope: str) -> dict:
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database = manifest["database"]
    path = folder / "game_static.sqlite3"
    if manifest["catalog_scope"] != scope or sha256(path) != BASE_HASHES[scope]:
        raise ValueError(f"Elyms supplement requires the original 2.3.1 {scope} catalog")

    dataset_id = database["dataset_id"] + "_elyms_154"
    sql = (DATA / "cn_154_elyms.sql").read_text(encoding="utf-8")
    with closing(sqlite3.connect(path)) as con, con:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript("BEGIN; PRAGMA defer_foreign_keys=ON;\n" + sql)
        if scope == "game":
            con.execute("INSERT INTO fork_permanent_review VALUES "
                        "('fork_elyms', 'resolved_permanent', 5, 5, 5, 'CN 1.5.4: buff_Elyms_AtkUp')")
        con.execute("UPDATE dataset SET dataset_id=? WHERE dataset_id=?", (dataset_id, database["dataset_id"]))
        con.execute("UPDATE dataset_scope SET dataset_id=? WHERE dataset_id=?", (dataset_id, database["dataset_id"]))
        issues = con.execute("PRAGMA foreign_key_check").fetchmany(5)
        if issues:
            raise ValueError(f"{scope} catalog has unresolved references: {issues}")

    database.update(dataset_id=dataset_id, sha256=sha256(path), size_bytes=path.stat().st_size)
    manifest["supplement"] = {"character_id": 1090, "build": "CN 1.5.4 / 594078",
                              "base_sha256": BASE_HASHES[scope], "source": "cn_154_elyms.sql"}
    write_manifest(manifest_path, manifest)
    return database


def stage_elyms(data_root: Path) -> None:
    update_catalog(data_root, "game")
    reference = data_root / "role_catalog"
    database = update_catalog(reference, "reference")
    ui = reference / "game_ui"
    manifest_path = ui / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for group, key, filename, width, height in UI_FILES:
        parent = "forks" if group == "fork_items" else group
        rel = f"{parent}/{filename}"
        path = ui / rel
        shutil.copyfile(DATA / "elyms_ui" / filename, path)
        manifest[group][key] = rel
        manifest["files"][rel] = {"width": width, "height": height, "bytes": path.stat().st_size,
                                  "sha256": sha256(path), "source": "CN 1.5 Elyms UI"}
    manifest["total_files"] = len(manifest["files"])
    manifest["total_bytes"] = sum(entry["bytes"] for entry in manifest["files"].values())
    manifest.update(dataset_id=database["dataset_id"], database_sha256=database["sha256"])
    write_manifest(manifest_path, manifest)
