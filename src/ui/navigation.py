# 定义主窗口侧边栏导航项。
"""Navigation metadata for the main window stack."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    button_attr: str
    page_builder: str
    refresh_method: str | None = None
    sidebar: bool = True
    parent_key: str | None = None
    required_capability: str | None = None


NAV_ITEMS = (
    NavItem("home", _L('工作台'), "btn_home", "_page_home", "_refresh_home"),
    NavItem("execute", _L('⚡  计算'), "btn_exec", "_page_execute", "_refresh_execute"),
    NavItem("team_sim", _L('👥  队伍模拟 (Beta)'), "btn_team_sim", "_page_team_sim"),
    NavItem("arc_eff", _L('📈  弧盘效率表 (Beta)'), "btn_arc_eff", "_page_arc_eff"),
    NavItem("equipment", _L('💎  配装'), "btn_equip", "_page_equipment", "_refresh_equip"),
    NavItem("my_role", _L('👤  角色'), "btn_my_role", "_page_my_role", "_refresh_my_role"),
    NavItem("warehouse", _L('📦  仓库'), "btn_warehouse", "_page_warehouse", "_refresh_warehouse"),
    NavItem(
        "identify",
        _L('🔍  鉴定'),
        "btn_identify",
        "_page_identify",
        "_refresh_identify_options",
    ),
    NavItem(
        "battle_report",
        _L('📊  战报'),
        "btn_battle_report",
        "_page_battle_report",
    ),
    NavItem(
        "blueprint",
        _L('角色图纸'),
        "btn_blueprint",
        "_page_blueprint",
        "_refresh_blueprints",
        sidebar=False,
        parent_key="my_role",
    ),
    NavItem(
        "config",
        _L('基础权重'),
        "btn_config",
        "_page_config",
        "_refresh_config_forms",
        sidebar=False,
        parent_key="my_role",
    ),
    NavItem("toolbox", _L('🧰  工具'), "btn_toolbox", "_page_toolbox", "_refresh_toolbox"),
    NavItem("plugins", _L('🧩  插件'), "btn_plugins", "_page_plugins", "_refresh_plugins"),
    NavItem(
        "static_catalog",
        _L('游戏资料库'),
        "btn_static_catalog",
        "_page_static_catalog",
        "_refresh_static_catalog",
        sidebar=False,
        parent_key="toolbox",
    ),
    NavItem("settings", _L('🔧  设置'), "btn_settings", "_page_settings"),
)


def nav_index_map() -> dict[str, int]:
    return {item.key: index for index, item in enumerate(NAV_ITEMS)}


def nav_item_by_key(key: str) -> NavItem | None:
    return next((item for item in NAV_ITEMS if item.key == key), None)


def sidebar_nav_items() -> tuple[NavItem, ...]:
    return tuple(item for item in NAV_ITEMS if item.sidebar)
