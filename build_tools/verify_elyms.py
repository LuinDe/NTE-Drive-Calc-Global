"""Exercise Elyms' equipment paths on the staged installation using an empty temporary account.

Run with the project's Python environment: python build_tools/verify_elyms.py <stage/_internal>
"""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    db = root / "data" / "game_static.sqlite3"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ["NTE_GAME_STATIC_DB"] = str(db)
    os.environ["NTE_KO_PATCH_LANG"] = "zh"

    from src.integrations.role_catalog_release import read_role_catalog, validate_role_assets
    from src.optimizer.allocation_kernel import AllocationKernel
    from src.services.character_weight_service import ensure_account_character_weights, save_account_character_weights
    from src.services.official_role_page_service import load_official_role_detail
    from src.solver.orchestrator import NTEPipelineOrchestrator
    from src.storage.sqlite.static_game_data_dao import StaticGameDataDao
    from src.storage.sqlite.user_data_dao import UserDataDao

    catalog = read_role_catalog(root / "data" / "role_catalog")
    assets = validate_role_assets(catalog.asset_root, catalog.dataset_id, catalog.sha256)
    from PySide6.QtGui import QImage

    for group, key, size in (("characters", "1090", (256, 256)),
                             ("character_arts", "1090", (1000, 1185)),
                             ("fork_items", "fork_elyms", (256, 256))):
        path = catalog.asset_root / assets[group][key]
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), path
        image = QImage(str(path))
        assert not image.isNull() and (image.width(), image.height()) == size, path
    print("Character catalog OK: runtime validation and all three Elyms PNG images decoded by Qt.")

    with TemporaryDirectory() as temp:
        account = Path(temp) / "test.sqlite3"
        with UserDataDao(account, account_id="elyms-test"):
            pass
        with StaticGameDataDao(db) as dao:
            name = dao.get_character(1090)["name_zh"]
            assert name == "曳尔沐"
            assert sum(row["character_id"] == 1090 for row in dao.list_role_template_characters([1090])) == 1
            plan = dao.get_equipment_plan(1090)
            assert len(plan["cells"]) == 20 and len(plan["module_item_ids"]) == 7
            bonus = dao.get_character_shape_bonus(1090)
            assert bonus["shape_grid_count"] == 3
            assert [(p["property_id"], p["display_value"]) for p in bonus["properties"]] == [("CritBase", 8)]
        detail = load_official_role_detail(account, 1090, static_database_path=db, include_inventory_contexts=False)
        cap = next(row for row in detail["growth_rows"] if row["level"] == 80)
        assert (cap["hp_base"], cap["atk_base"], cap["def_base"]) == (15392, 660, 909)
        assert len(detail["skills"]) == 4 and len(detail["awakenings"]) == 8
        assert detail["graduation_template"]["extra_shape_count"] == 4
        fork = next(row for row in detail["forks"] if row["fork_id"] == "fork_elyms")
        assert [row["property_value"] for row in fork["permanent_properties"]] == [0.15, 0.1875, 0.225, 0.2625, 0.3]
        planner = NTEPipelineOrchestrator(root / "config", static_database_path=db)
        blueprints = planner.solve_blueprints([name])[name]
        suit = planner.roles_db[name]["default_set"]
        pieces = blueprints[0]["set_pieces"] + blueprints[0]["extra_pieces"]
        inventory = [
            dict(uid=f"drive-{i}", item_type="drive", quality="Gold", area=planner.shapes_db[piece].area,
                 shape_id=piece, set_name=suit, sub_stats={"暴击伤害%": 4.0})
            for i, piece in enumerate(pieces)
        ]
        inventory.append(dict(uid="core", item_type="tape", quality="Gold", area=15, suit_id="Suit6",
                              set_name=suit, main_stats="光属性异能伤害增强%", sub_stats={"暴击伤害%": 4.0}))
        result = planner.run_full_allocation(
            inventory, [name], allocation_executor=lambda request, scoring: AllocationKernel(scoring).execute(request)
        )[name]
        assert result["assigned_tape"].uid == "core"
        drives = result["assigned_set_drives"] + result["assigned_extra_drives"]
        assert len({drive.uid for drive in drives}) == 7 and sum(drive.area for drive in drives) == 20
        assert all(drive.role_scores[name] > 0 for drive in drives)

        defaults = ensure_account_character_weights(account, [1090], static_database_path=db)
        assert defaults[1090]["property_weights"]["CritBase"] == 0.8
        save_account_character_weights(account, 1090, {"CritBase": 0.31}, static_database_path=db)
        assert ensure_account_character_weights(account, [1090], static_database_path=db)[1090]["property_weights"]["CritBase"] == 0.31
        print(f"Elyms OK: {len(blueprints)} blueprints, seven scored drives, one cartridge, saved account weights.")


if __name__ == "__main__":
    main()
