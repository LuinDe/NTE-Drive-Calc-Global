# 编排游戏角色列表识别、装配计划执行和结果复核会话。
"""Automatic assembly session orchestration for the game role list."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from datetime import datetime
from pathlib import Path
import re
import time
from collections.abc import Callable
from typing import Any

import cv2
import mss
import numpy as np

from src.features.drive_assembly.executor import (
    AssemblyExecutionReport,
    AssemblyExecutionStopped,
    MouseBackend,
    PyAutoGuiMouseBackend,
    execute_action_sequence,
    execute_role_traversal_assembly_plan,
    f12_stop_checker,
)
from src.features.drive_assembly.page_mapping import (
    map_assembly_page_prepare_controls,
    map_drive_blocks_installation,
)
from src.features.drive_assembly.role_flow import (
    build_role_assembly_payloads,
    collect_role_roster_from_mouse_rows,
    map_role_list_mouse_entry,
    map_role_list_mouse_row_scan,
    plan_role_assembly_from_role_list_roster,
    recognize_current_role_from_image,
    required_roles_from_payloads,
)
from src.features.drive_assembly.tape_plan import tape_install_sequence
from src.scanner.ocr_engine import OCREngine
from src.scanner.window_capture import capture_foreground_window, game_content_rect
from src.storage.sqlite.static_game_data_dao import StaticGameDataDao, StaticGameDataError
from src.utils.logger import logger


_STARTUP_ROLE_RECOGNITION_METHODS = {
    "ocr",
    "ocr_fallback",
    "ocr_correction",
    "ocr_yi_fallback",
}


def _log_mouse_delivery_diagnostics(backend: MouseBackend) -> None:
    """Log local button-state observations without coupling the UI to a backend type."""

    consume = getattr(backend, "consume_mouse_delivery_diagnostics", None)
    if not callable(consume):
        return
    records = consume()
    if not records:
        return
    states = []
    for record in records:
        if record.get("stage") == "touch_tap":
            touch_text = "ok" if record.get("touch_success") else "failed"
            error_text = record.get("touch_error")
            states.append(f"touch_tap:{touch_text}:error={error_text if error_text is not None else 'n/a'}")
            continue
        local_state = record.get("local_left_down")
        state_text = "down" if local_state is True else "up" if local_state is False else "unknown"
        sent = record.get("send_input_result")
        sent_text = "n/a" if sent is None else str(sent)
        requested = record.get("requested_position")
        dispatched = record.get("dispatched_position")
        cursor = record.get("cursor_position")
        states.append(
            f"{record.get('stage')}:{state_text}:send={sent_text}:"
            f"requested={requested}:dispatched={dispatched}:cursor={cursor}"
        )
    logger.info(_L('驱动装配鼠标送达诊断 | ') + " | ".join(states))
_RECORDED_ASSEMBLY_ACTIONS = {
    "open_role_list",
    "confirm_role_list_selection",
    "close_role_list_after_confirmation",
    "left_kongmu_tab",
    "wait_after_left_kongmu_tab",
    "assemble_button",
    "wait_after_assemble_button",
    "assembly_back_to_role_page",
}


class AssemblyRunRecorder:
    """Persist screenshots for the navigation steps of one assembly run."""

    def __init__(self, root: str | Path):
        record_root = Path(root)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.directory: Path | None = record_root / f"assembly_{run_id}"
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(_LF('无法创建装配过程截图目录 | 路径={0} | 原因={1}').format((self.directory), (exc)))
            self.directory = None
        self._sequence = 0

    def save_image(self, image: np.ndarray, label: str) -> Path | None:
        if self.directory is None or image is None or image.size == 0:
            return None
        safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label)).strip("_") or "screen"
        self._sequence += 1
        path = self.directory / f"{self._sequence:03d}_{safe_label}.png"
        try:
            ok, encoded = cv2.imencode(".png", image)
            if not ok:
                raise ValueError("PNG encoding failed")
            encoded.tofile(str(path))
            logger.info(_LF('装配过程截图已保存 | {0}').format((path)))
            return path
        except Exception as exc:
            logger.warning(_LF('保存装配过程截图失败 | 标签={0} | 原因={1}').format((safe_label), (exc)))
            return None

    def capture_foreground(self, label: str) -> Path | None:
        try:
            image, _rect = _capture_foreground_client_image()
        except Exception as exc:
            logger.warning(_LF('截取装配过程页面失败 | 标签={0} | 原因={1}').format((label), (exc)))
            return None
        return self.save_image(image, label)

    def record_action(self, action: dict[str, Any], role_name: str | None) -> None:
        action_name = str(action.get("name") or "")
        is_duplicate_filter_complete = bool(action.get("duplicate_status_filter")) and action_name == "status_other"
        if action_name not in _RECORDED_ASSEMBLY_ACTIONS and not is_duplicate_filter_complete:
            return
        role_suffix = f"_{role_name}" if role_name else ""
        if is_duplicate_filter_complete:
            self.capture_foreground(f"duplicate_status_filters_block_{action.get('block_id', 'unknown')}{role_suffix}")
            return
        self.capture_foreground(f"{action_name}{role_suffix}")


def is_role_detail_startup_recognition(recognition: Any) -> bool:
    """Accept only high-confidence role-detail OCR before sending navigation input."""

    return bool(
        getattr(recognition, "role_name", None)
        and getattr(recognition, "method", "") in _STARTUP_ROLE_RECOGNITION_METHODS
    )


def build_single_role_assembly_plan(
    equipped_state: dict[str, Any] | None,
    role_name: str,
    screen_size: tuple[int, int] | None = None,
    content_rect: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """Return the planned tape and drive actions for one role."""

    payloads = build_role_assembly_payloads(equipped_state, screen_size, content_rect)
    payload = payloads.get(role_name)
    if not payload:
        return {
            "role_name": role_name,
            "available": False,
            "reason": _L('未找到该角色的已保存装配数据。'),
            "actions": [],
        }
    actions: list[dict[str, Any]] = []
    tape_filter = payload.get("tape_filter")
    drive_blocks = payload.get("drive_blocks") or []
    if tape_filter or drive_blocks:
        actions.append(
            {
                "name": "prepare_assembly_page",
                "role_name": role_name,
                "sequence": map_assembly_page_prepare_controls(screen_size, content_rect)["prepare_sequence"],
            }
        )
    if tape_filter:
        actions.append(
            {
                "name": "install_tape",
                "role_name": role_name,
        "sequence": tape_install_sequence(tape_filter, screen_size, content_rect),
            }
        )
    if drive_blocks:
        drive_plan = map_drive_blocks_installation(drive_blocks, screen_size, content_rect)
        actions.append(
            {
                "name": "install_drives",
                "role_name": role_name,
                "sequence": drive_plan["assembly_sequence"],
                "install_plans": drive_plan["install_plans"],
            }
        )
    return {
        "role_name": role_name,
        "available": bool(actions),
        "reason": "" if actions else _L('该角色没有可装配的卡带或驱动块。'),
        "tape_count": 1 if tape_filter else 0,
        "drive_count": len(drive_blocks),
        "drive_blocks": drive_blocks,
        "actions": actions,
    }


def build_all_role_assembly_plan(
    equipped_state: dict[str, Any] | None,
    screen_size: tuple[int, int] | None = None,
    content_rect: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """Return per-role assembly plans for all roles with saved payloads."""

    payloads = build_role_assembly_payloads(equipped_state, screen_size, content_rect)
    roles = required_roles_from_payloads(payloads)
    role_plans = [build_single_role_assembly_plan(equipped_state, role, screen_size, content_rect) for role in roles]
    ready = [plan for plan in role_plans if plan["available"]]
    return {
        "role_count": len(roles),
        "ready_count": len(ready),
        "roles": roles,
        "role_plans": role_plans,
        "missing_roles": [plan["role_name"] for plan in role_plans if not plan["available"]],
    }


def execute_all_roles_from_current_game_page(
    equipped_state: dict[str, Any] | None,
    backend: MouseBackend | None = None,
    template_dir: str | None = None,
    max_pages: int | None = None,
    startup_delay_seconds: float = 3.0,
    reset_scroll_count: int = 6,
    verification_enabled: bool = True,
    role_name_aliases: dict[str, str] | None = None,
    record_root: str | Path | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> AssemblyExecutionReport:
    """Recognize the current game role list, traverse roles, and execute assembly."""

    return _execute_roles_from_current_game_page(
        equipped_state,
        target_roles=None,
        backend=backend,
        template_dir=template_dir,
        max_pages=max_pages,
        startup_delay_seconds=startup_delay_seconds,
        reset_scroll_count=reset_scroll_count,
        verification_enabled=verification_enabled,
        role_name_aliases=role_name_aliases,
        record_root=record_root,
        should_stop=should_stop,
    )


def execute_selected_role_from_current_game_page(
    equipped_state: dict[str, Any] | None,
    role_name: str,
    backend: MouseBackend | None = None,
    template_dir: str | None = None,
    max_pages: int | None = None,
    startup_delay_seconds: float = 3.0,
    reset_scroll_count: int = 6,
    verification_enabled: bool = True,
    role_name_aliases: dict[str, str] | None = None,
    record_root: str | Path | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> AssemblyExecutionReport:
    """Find one selected role in the game sidebar and assemble only its blueprint."""

    return _execute_roles_from_current_game_page(
        equipped_state,
        target_roles=[role_name],
        backend=backend,
        template_dir=template_dir,
        max_pages=max_pages,
        startup_delay_seconds=startup_delay_seconds,
        reset_scroll_count=reset_scroll_count,
        verification_enabled=verification_enabled,
        role_name_aliases=role_name_aliases,
        record_root=record_root,
        should_stop=should_stop,
    )


def _execute_roles_from_current_game_page(
    equipped_state: dict[str, Any] | None,
    target_roles: list[str] | tuple[str, ...] | None,
    backend: MouseBackend | None,
    template_dir: str | None,
    max_pages: int | None,
    startup_delay_seconds: float,
    reset_scroll_count: int,
    verification_enabled: bool,
    role_name_aliases: dict[str, str] | None = None,
    record_root: str | Path | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> AssemblyExecutionReport:
    """Shared game-page flow: find target roles first, then assemble their blueprints."""

    checker = should_stop or f12_stop_checker()
    if template_dir is None or record_root is None:
        raise ValueError("automatic assembly requires template_dir and record_root")
    template_root = template_dir
    if startup_delay_seconds > 0:
        deadline = time.monotonic() + startup_delay_seconds
        while time.monotonic() < deadline:
            if checker():
                raise AssemblyExecutionStopped("assembly execution stopped")
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    if checker():
        raise AssemblyExecutionStopped("assembly execution stopped")
    first_image, first_rect = _capture_foreground_client_image()
    recorder = AssemblyRunRecorder(record_root)
    recorder.save_image(first_image, "startup")
    screen_size = (first_rect.width, first_rect.height)
    image_content_rect = _fit_content_rect(first_rect.width, first_rect.height)
    action_rect = (
        first_rect.left + image_content_rect[0],
        first_rect.top + image_content_rect[1],
        image_content_rect[2],
        image_content_rect[3],
    )
    assembly_plan = build_all_role_assembly_plan(equipped_state, screen_size=screen_size, content_rect=action_rect)
    assembly_plan = _filter_assembly_plan_for_roles(assembly_plan, target_roles)
    required_roles = assembly_plan.get("roles", [])
    _log_assembly_plan_diagnostics(assembly_plan, screen_size, action_rect)
    if not required_roles:
        logger.warning(_L('驱动装配未启动 | 原因=没有可装配的目标角色'))
        return execute_role_traversal_assembly_plan({"plans": []}, assembly_plan, backend=backend)
    recognition_roles = role_recognition_candidates(required_roles, template_root, equipped_state, role_name_aliases)
    ocr_engine = OCREngine()
    startup_recognition = recognize_current_role_from_image(
        first_image,
        recognition_roles,
        ocr_engine,
        screen_size=screen_size,
        content_rect=image_content_rect,
        role_aliases=role_name_aliases,
    )
    logger.info(
        "Assembly startup page recognition | "
        f"role={startup_recognition.role_name or 'unrecognized'} | "
        f"method={startup_recognition.method} | OCR={startup_recognition.raw_text!r} | "
        f"record_dir={recorder.directory}"
    )
    if not is_role_detail_startup_recognition(startup_recognition):
        logger.warning(
            "Current page was not recognized as role detail; continuing automatic assembly as requested | "
            f"OCR={startup_recognition.raw_text!r} | record_dir={recorder.directory}"
        )
    logger.info(
        (_L('驱动装配角色扫描开始 | ') + _LF('目标角色={0} | 识别候选数={1} | ').format((required_roles), (len(recognition_roles))) + _LF('窗口尺寸={0} | 操作区域={1} | 向上复位次数=5').format((screen_size), (action_rect)))
    )
    logger.info(
        (_L('角色列表扫描路径 | 普通鼠标 | 右侧下滑×2 | 首个头像 | 信息页签 | 右下角色列表按钮 | ') + _L('首屏12格一次识别，随后滚轮逐行并只检查第4行；首次重复即到底'))
    )
    action_backend = backend or PyAutoGuiMouseBackend()
    randomization_enabled = enable_assembly_randomization(action_backend)
    logger.info(
        (_L('驱动装配随机化 | ') + _LF('鼠标随机化={0} | ').format(('已启用' if randomization_enabled else '后端不支持')) + _L('点击/滚轮±3像素、离散输入延迟0~0.1秒、拖拽端点与节奏随机'))
    )

    def open_role_list() -> None:
        sequence = map_role_list_mouse_entry(screen_size, action_rect)["entry_sequence"]
        execute_action_sequence(
            sequence,
            backend=action_backend,
            should_stop=checker,
        )
        _log_mouse_delivery_diagnostics(action_backend)
        logger.info(_L('角色列表鼠标入口已执行 | 右侧下滑×1 | 首个头像 | 信息页签 | 右下角色列表按钮'))
        recorder.capture_foreground("role_list_opened")

    row_scan = map_role_list_mouse_row_scan(screen_size, action_rect)
    captured_role_images: dict[int, np.ndarray] = {}

    def select_role_list_slot(slot_index: int) -> None:
        action = row_scan["slot_selection_actions"][slot_index]
        logger.info(
            (_L('角色列表格点击请求 | ') + f"slot={slot_index} | position={action['position']}")
        )
        execute_action_sequence(
            [action],
            backend=action_backend,
            should_stop=checker,
        )
        _log_mouse_delivery_diagnostics(action_backend)

    def scroll_role_list_next_row() -> None:
        execute_action_sequence(
            row_scan["row_scroll_sequence"],
            backend=action_backend,
            should_stop=checker,
        )

    def observe_current(_index: int) -> Any:
        if checker():
            raise AssemblyExecutionStopped("assembly execution stopped")
        image, _rect = _capture_foreground_client_image()
        captured_role_images[_index] = image
        recognition = recognize_current_role_from_image(
            image,
            recognition_roles,
            ocr_engine,
            screen_size=screen_size,
            content_rect=image_content_rect,
            role_aliases=role_name_aliases,
        )
        logger.info(
            (_LF('驱动装配角色扫描 #{0}：').format((_index + 1)) + _LF('匹配={0}，').format((recognition.role_name or '未识别')) + _LF('方式={0}，').format((recognition.method)) + _LF('置信度={0:.3f}，').format((recognition.confidence)) + f"OCR={recognition.raw_text!r}")
        )
        return recognition

    def record_unique_role_observation(index: int) -> None:
        image = captured_role_images.pop(index, None)
        if image is not None:
            recorder.save_image(image, f"role_list_scan_{index + 1:02d}")

    try:
        role_roster = collect_role_roster_from_mouse_rows(
            required_roles,
            current_observer=observe_current,
            select_grid_slot=select_role_list_slot,
            scroll_next_row=scroll_role_list_next_row,
            enter_role_list=open_role_list,
            on_unique_observation=record_unique_role_observation,
            max_roles=max_pages or max(20, len(recognition_roles) + 6),
        )
        captured_role_images.clear()

    except BaseException:
        close_assembly_backend(action_backend)
        raise
    logger.info(
        (_L('驱动装配角色扫描完成：') + _LF('已识别={0}，').format((role_roster.get('roles', []))) + _LF('未识别={0}，').format((role_roster.get('unrecognized', []))) + _LF('重复={0}').format((role_roster.get('duplicates', []))))
    )
    logger.info(
        (_L('角色列表扫描结果 | ') + _LF('停止原因={0} | ').format((role_roster.get('stop_reason', ''))) + _LF('缺少={0} | ').format((role_roster.get('missing_expected_roles', []))) + _LF('当前列表索引={0} | 将在选中首个装配角色后关闭列表').format((role_roster.get('current_index', 0))))
    )
    recorder.capture_foreground("role_list_scan_complete")
    traversal_plan = plan_role_assembly_from_role_list_roster(
        required_roles,
        role_roster,
        screen_size=screen_size,
        content_rect=action_rect,
        current_index=role_roster.get("current_index", max(0, len(role_roster.get("roles", []) or []) - 1)),
    )
    _log_traversal_plan_diagnostics(traversal_plan)
    def verifier(role_name: str, role_plan: dict[str, Any]) -> dict[str, Any] | None:
        if not verification_enabled:
            return None
        image, rect = _capture_foreground_client_image()
        return verify_blueprint_against_screenshot(image, rect, role_plan)

    try:
        report = execute_role_traversal_assembly_plan(
            traversal_plan,
            assembly_plan,
            backend=action_backend,
            should_stop=checker,
            role_verifier=verifier,
            on_action_executed=recorder.record_action,
        )
    finally:
        close_assembly_backend(action_backend)
    logger.info(
        (_L('驱动装配总结果 | ') + _LF('已执行={0} | 导航={1} | ').format((report.executed_actions), (report.navigation_actions)) + _LF('角色={0} | ').format(([(item.role_name, item.executed_actions, len(item.skipped_actions)) for item in report.role_reports])) + _LF('跳过角色={0} | 校验失败={1}').format((report.skipped_roles), (report.verification_failures)))
    )
    return report


def enable_assembly_randomization(backend: MouseBackend) -> bool:
    """Enable bounded mouse randomization when the selected backend supports it."""

    enable_randomization = getattr(backend, "enable_randomization", None)
    if not callable(enable_randomization):
        return False
    enable_randomization()
    return True


def close_assembly_backend(backend: MouseBackend) -> bool:
    """Close the virtual controller when the backend owns one."""

    close = getattr(backend, "close", None)
    if not callable(close):
        return False
    try:
        close()
    except Exception as exc:
        logger.warning(_LF('虚拟手柄关闭失败 | {0}').format((exc)))
        return False
    logger.info(_L('虚拟手柄已重置并关闭'))
    return True


def _log_assembly_plan_diagnostics(
    assembly_plan: dict[str, Any],
    screen_size: tuple[int, int],
    content_rect: tuple[int, int, int, int],
) -> None:
    """Log the planned equipment and target geometry before any UI input."""

    logger.info(
        (_L('驱动装配计划生成 | ') + _LF('角色={0} | 可执行={1}/{2} | ').format((assembly_plan.get('roles', [])), (assembly_plan.get('ready_count', 0)), (assembly_plan.get('role_count', 0))) + _LF('窗口尺寸={0} | 操作区域={1}').format((screen_size), (content_rect)))
    )
    for role_plan in assembly_plan.get("role_plans", []):
        role_name = role_plan.get("role_name", _L('未命名'))
        if not role_plan.get("available"):
            logger.warning(_LF('角色装配计划不可用 | 角色={0} | 原因={1}').format((role_name), (role_plan.get('reason', '未知'))))
            continue
        logger.info(
            (_L('角色装配计划 | ') + _LF('角色={0} | 卡带={1} | 驱动={2} | ').format((role_name), (role_plan.get('tape_count', 0)), (role_plan.get('drive_count', 0))) + _LF('重复驱动={0} | ').format((sum((1 for block in role_plan.get('drive_blocks', []) if _is_duplicate_drive_block(block))))) + _LF('顶层动作={0}').format(([action.get('name') for action in role_plan.get('actions', [])])))
        )
        for block in role_plan.get("drive_blocks", []) or []:
            drive = block.get("drive") if isinstance(block.get("drive"), dict) else {}
            logger.info(
                (_L('驱动装配目标 | ') + _LF('角色={0} | 块={1} | uid={2} | ').format((role_name), (block.get('block_id')), (drive.get('uid', '未知'))) + _LF('形状={0} | 品质={1} | ').format((block.get('drive_type') or drive.get('shape_id', '未知')), (drive.get('quality', '未知'))) + _LF('套装={0} | 副词条={1} | ').format((block.get('set_name') or drive.get('set_name', '未筛选')), (drive.get('sub_stats', {}))) + _LF('格子={0} | 质心={1} | ').format((block.get('cells', [])), (block.get('grid_centroid') or block.get('shape_centroid'))) + _LF('目标={0} | 重复={1} | ').format((block.get('pixel_position')), (_is_duplicate_drive_block(block))) + _LF('状态筛选={0}').format(('锁定/弃置/其他' if _is_duplicate_drive_block(block) else '无')))
            )


def _log_traversal_plan_diagnostics(traversal_plan: dict[str, Any]) -> None:
    """Log the role-recognition result and the exact D-pad route per role."""

    logger.info(
        (_L('角色路径规划完成 | ') + _LF('导航={0} | 计划={1} | ').format((traversal_plan.get('navigation', '未知')), (traversal_plan.get('planned_roles', []))) + _LF('缺失={0} | 未识别={1} | ').format((traversal_plan.get('missing_roles', [])), (traversal_plan.get('unrecognized', []))) + _LF('重复={0}').format((traversal_plan.get('duplicates', []))))
    )
    for step in traversal_plan.get("plans", []):
        moves = [
            action.get("gamepad_button") or action.get("gamepad_stick")
            for action in step.get("action_sequence", [])
            if action.get("gamepad_button") or action.get("gamepad_stick")
        ]
        logger.info(
            (_L('角色路径 | ') + _LF('角色={0} | 起始索引={1} | ').format((step.get('role_name')), (step.get('start_roster_index'))) + _LF('目标索引={0} | 手柄路径={1} | ').format((step.get('roster_index')), (moves)) + _LF('进入动作={0}').format(([action.get('name') for action in step.get('action_sequence', [])])))
        )


def _filter_assembly_plan_for_roles(
    assembly_plan: dict[str, Any],
    target_roles: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    if not target_roles:
        return assembly_plan
    targets = [str(role) for role in target_roles if str(role).strip()]
    target_set = set(targets)
    role_plans = [
        plan for plan in assembly_plan.get("role_plans", []) if str(plan.get("role_name") or "") in target_set
    ]
    ready = [plan for plan in role_plans if plan.get("available")]
    filtered = dict(assembly_plan)
    filtered["roles"] = [role for role in targets if any(plan.get("role_name") == role for plan in role_plans)]
    filtered["role_plans"] = role_plans
    filtered["role_count"] = len(filtered["roles"])
    filtered["ready_count"] = len(ready)
    filtered["missing_roles"] = [role for role in targets if role not in set(filtered["roles"])]
    return filtered


def role_recognition_candidates(
    required_roles: list[str] | tuple[str, ...],
    template_root: str,
    equipped_state: dict[str, Any] | None,
    role_name_aliases: dict[str, str] | None = None,
) -> list[str]:
    """Return the complete role-name set used to identify the game roster."""

    names: list[str] = []
    for role in required_roles:
        _append_unique_role_name(names, role)
    if isinstance(equipped_state, dict):
        for role in equipped_state:
            _append_unique_role_name(names, role)
    if isinstance(role_name_aliases, dict):
        for canonical, alias in role_name_aliases.items():
            _append_unique_role_name(names, canonical)
            _append_unique_role_name(names, alias)
    for role_name in _static_role_name_candidates():
        _append_unique_role_name(names, role_name)
    template_dir = Path(template_root)
    if template_dir.exists():
        for path in sorted(template_dir.glob("*.png")):
            _append_unique_role_name(names, path.stem)
    return names


def _static_role_name_candidates() -> list[str]:
    """Load every playable name from the bundled static database.

    Assembly plans contain only the selected roles, while the RS roster scan
    necessarily crosses every owned role.  Restricting OCR candidates to the
    plan therefore made fully legible non-target roles appear unrecognized.
    """

    try:
        with StaticGameDataDao() as static_dao:
            return [
                str(character.get("name_zh") or "").strip()
                for character in static_dao.list_role_template_characters()
                if str(character.get("name_zh") or "").strip()
            ]
    except StaticGameDataError as exc:
        logger.warning(_LF('角色识别静态角色库不可用，将仅使用方案与模板候选 | {0}').format((exc)))
        return []


def _append_unique_role_name(names: list[str], role_name: Any) -> None:
    value = str(role_name).strip()
    if value and value not in names:
        names.append(value)


def verify_blueprint_against_screenshot(
    image: np.ndarray,
    rect: Any,
    role_plan: dict[str, Any],
    sample_radius: int = 4,
    brightness_threshold: float = 22.0,
) -> dict[str, Any]:
    """Check that expected drive block target positions look occupied in a screenshot."""

    if image is None or image.size == 0:
        return {"ok": False, "reason": "empty_screenshot", "missing_blocks": []}
    missing: list[dict[str, Any]] = []
    for block in role_plan.get("drive_blocks", []) or []:
        position = block.get("pixel_position")
        if not position:
            continue
        x = int(position[0]) - int(getattr(rect, "left", 0))
        y = int(position[1]) - int(getattr(rect, "top", 0))
        if not _sample_position_looks_occupied(image, x, y, sample_radius, brightness_threshold):
            drive = block.get("drive") if isinstance(block.get("drive"), dict) else {}
            missing_block = {
                "block_id": block.get("block_id"),
                "position": tuple(position),
            }
            if _is_duplicate_drive_block(block):
                missing_block.update(
                    {
                        "is_duplicate_drive": True,
                        "duplicate_count": block.get("duplicate_count") or drive.get("duplicate_count"),
                        "shape_id": block.get("drive_type") or drive.get("shape_id"),
                    }
                )
            missing.append(missing_block)
    return {"ok": not missing, "missing_blocks": missing}


def summarize_assembly_plan(plan: dict[str, Any]) -> str:
    """Return a concise human-readable plan summary."""

    if "role_plans" in plan:
        lines = [_LF('可装配角色：{0}/{1}').format((plan.get('ready_count', 0)), (plan.get('role_count', 0)))]
        for role_plan in plan.get("role_plans", []):
            if role_plan.get("available"):
                lines.append(
                    _LF('- {0}：卡带 {1}，驱动 {2}').format((role_plan['role_name']), (role_plan.get('tape_count', 0)), (role_plan.get('drive_count', 0)))
                )
            else:
                lines.append(_LF('- {0}：{1}').format((role_plan['role_name']), (role_plan.get('reason', '不可装配'))))
        return "\n".join(lines)
    if not plan.get("available"):
        return _LF('{0}：{1}').format((plan.get('role_name', '角色')), (plan.get('reason', '不可装配')))
    return _LF('{0}：卡带 {1}，驱动 {2}').format((plan['role_name']), (plan.get('tape_count', 0)), (plan.get('drive_count', 0)))


def _capture_foreground_client_image():
    with mss.MSS() as sct:
        screenshot, rect = capture_foreground_window(sct)
    image = np.array(screenshot)
    if image.ndim == 3 and image.shape[2] > 3:
        image = image[:, :, :3]
    return image, rect


def _sample_position_looks_occupied(
    image: np.ndarray,
    x: int,
    y: int,
    radius: int,
    brightness_threshold: float,
) -> bool:
    height, width = image.shape[:2]
    x1 = max(0, min(width, x - radius))
    x2 = max(0, min(width, x + radius + 1))
    y1 = max(0, min(height, y - radius))
    y2 = max(0, min(height, y + radius + 1))
    if x1 >= x2 or y1 >= y2:
        return False
    patch = image[y1:y2, x1:x2]
    return float(np.mean(patch)) >= brightness_threshold


def _fit_content_rect(
    width: int, height: int, reference_size: tuple[int, int] = (2560, 1440)
) -> tuple[int, int, int, int]:
    return game_content_rect(width, height, reference_size)


def _is_duplicate_drive_block(block: dict[str, Any]) -> bool:
    raw_drive = block.get("drive")
    drive: dict[str, Any] = raw_drive if isinstance(raw_drive, dict) else {}
    return bool(
        block.get("is_duplicate_drive")
        or block.get("is_duplicate_equipment")
        or drive.get("is_duplicate_drive")
        or drive.get("is_duplicate_equipment")
        or int(block.get("duplicate_count") or 0) > 1
        or int(drive.get("duplicate_count") or 0) > 1
    )
