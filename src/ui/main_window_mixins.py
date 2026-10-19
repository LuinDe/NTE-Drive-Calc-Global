# 显式声明主窗口从各功能模块获得的方法。
"""Explicit MainWindow mixins for extracted feature methods."""

from __future__ import annotations

from src.features.inventory.equipment_assembly_controller import (
    EquipmentAssemblyControllerMixin,
)
from src.features.inventory.equipment_display_controller import (
    EquipmentDisplayControllerMixin,
)
from src.features.inventory.warehouse_controller import WarehouseControllerMixin
from src.features.toolbox.page import build_toolbox_page, refresh_toolbox_page
from src.features.team_simulation.page import build_team_sim_page
from src.features.arc_efficiency import build_arc_efficiency_page
from src.features.weighted_allocation import page as weighted_allocation_page
from src.ui.controllers.configuration_controller import ConfigurationControllerMixin
from src.ui.controllers.environment_controller import EnvironmentControllerMixin
from src.ui.controllers.hotkey_controller import HotkeyControllerMixin
from src.ui.controllers.inventory_sync_controller import InventorySyncControllerMixin
from src.ui.controllers.about_links_controller import AboutLinksMixin


class WeightedAllocationMixin:
    _page_weighted_allocation = weighted_allocation_page.build_weighted_allocation_page
    _refresh_weighted_allocation = weighted_allocation_page.refresh_weighted_allocation_page


class ArcEfficiencyMixin:
    _page_arc_eff = build_arc_efficiency_page


class TeamSimulationMixin:
    _page_team_sim = build_team_sim_page


class ToolboxMixin:
    _page_toolbox = build_toolbox_page
    _refresh_toolbox = refresh_toolbox_page


class FeatureMainWindowMixin(
    ConfigurationControllerMixin,
    EnvironmentControllerMixin,
    HotkeyControllerMixin,
    InventorySyncControllerMixin,
    AboutLinksMixin,
    WarehouseControllerMixin,
    EquipmentAssemblyControllerMixin,
    EquipmentDisplayControllerMixin,
    WeightedAllocationMixin,
    ArcEfficiencyMixin,
    ToolboxMixin,
    TeamSimulationMixin,
):
    """Explicitly composed feature surface for MainWindow."""
