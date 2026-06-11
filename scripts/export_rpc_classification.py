from __future__ import annotations

import json
import math
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "asiair-jsonrpc.md"
REPORT_DIR = ROOT / "state" / "rpc-probes"
OUT_XLSX = ROOT / "docs" / "asiair-jsonrpc-method-classification-4digit.xlsx"
OUT_HTML = ROOT / "docs" / "asiair-jsonrpc-method-classification-4digit.html"
OUT_DIR = ROOT / "docs" / "asiair-jsonrpc-method-classification-images"


STATUS_LABEL = {"1": "已测试成功", "2": "测试失败", "3": "未测试"}
MAJOR_LABEL = {
    "0": "系统/App/网络",
    "1": "存储/文件",
    "2": "相机/拍摄",
    "3": "计划/序列",
    "4": "赤道仪/Goto/子午线",
    "5": "导星/Dither",
    "6": "滤轮/调焦",
    "7": "解算/极轴/标注/星点",
    "8": "叠加/视频/直播",
    "9": "电源/天体数据/内部",
}
MAJOR_DIGIT = {
    "System, App, Network": "0",
    "Storage and Files": "1",
    "Camera and Capture": "2",
    "Plans and Sequences": "3",
    "Mount, Goto, Meridian": "4",
    "Guiding and Dither": "5",
    "Filter Wheel": "6",
    "Focuser and Autofocus": "6",
    "Plate Solve, Polar Align, Annotation, Star Detection": "7",
    "Stacking, Live, Video, Streaming": "8",
    "Power Outputs": "9",
    "Object Lists and Sky Data": "9",
    "Internal or Poorly Understood": "9",
}
SUB_LABEL = {
    ("0", "00"): "系统连接/状态读取",
    ("0", "01"): "App 页面/发送状态",
    ("0", "02"): "时间/版本/授权",
    ("0", "03"): "Wi-Fi/AP 查询",
    ("0", "04"): "Wi-Fi 配置/连接动作",
    ("0", "05"): "以太网状态/配置",
    ("0", "06"): "重启/关机/系统控制",
    ("0", "07"): "通用设置读写",
    ("0", "08"): "内部/加密/未知",
    ("0", "09"): "其他系统动作",
    ("1", "00"): "容量/存储列表/保存位置读取",
    ("1", "01"): "保存位置设置",
    ("1", "02"): "文件/页面信息读取",
    ("1", "03"): "文件元数据写入",
    ("1", "04"): "文件保存/重命名/导出",
    ("1", "05"): "删除/弹出/格式化",
    ("1", "09"): "其他存储文件操作",
    ("2", "00"): "相机连接/状态/能力读取",
    ("2", "01"): "控制项读取",
    ("2", "02"): "控制项写入",
    ("2", "03"): "曝光/bin/16bit/ROI/命名读取",
    ("2", "04"): "曝光/bin/ROI/命名设置",
    ("2", "05"): "拍摄开始/停止/保存",
    ("2", "06"): "视频录制/RTMP",
    ("2", "07"): "相机连接/断开",
    ("2", "08"): "当前图像读取",
    ("2", "09"): "危险或参数异常相机设置",
    ("3", "00"): "计划/序列读取",
    ("3", "01"): "计划/序列写入/导入",
    ("3", "02"): "进度重置",
    ("3", "03"): "计划/序列删除清空",
    ("3", "04"): "错误标记清理",
    ("3", "09"): "其他计划序列操作",
    ("4", "00"): "赤道仪坐标/状态读取",
    ("4", "01"): "跟踪/指向侧/子午线设置",
    ("4", "02"): "Goto/移动/同步/停泊",
    ("4", "03"): "自动 Goto 启停",
    ("4", "04"): "赤道仪扫描",
    ("4", "05"): "中止运动",
    ("4", "09"): "其他赤道仪操作",
    ("5", "00"): "导星/Dither 设置读取",
    ("5", "01"): "导星/Dither 设置写入",
    ("5", "02"): "导星曝光/找星/脉冲",
    ("5", "03"): "Dither/校准/重启导星",
    ("5", "09"): "其他导星操作",
    ("6", "00"): "滤轮/调焦器连接状态能力读取",
    ("6", "01"): "滤轮位置/调焦器值读取",
    ("6", "02"): "滤轮/调焦器设置读取",
    ("6", "03"): "滤轮/调焦器设置写入",
    ("6", "04"): "滤轮/调焦器运动或自动对焦",
    ("6", "05"): "滤轮/调焦器连接断开",
    ("6", "06"): "自动对焦图像读取",
    ("6", "09"): "其他滤轮/调焦操作",
    ("7", "00"): "解算/标注/找星结果读取",
    ("7", "01"): "解算/标注/找星启动",
    ("7", "02"): "解算/标注/找星停止",
    ("7", "03"): "极轴图像引用读写",
    ("7", "04"): "极轴流程启停/暂停",
    ("7", "05"): "极轴设置/结果读取",
    ("7", "06"): "极轴设置写入",
    ("7", "09"): "其他图像分析操作",
    ("8", "00"): "叠加状态/结果读取",
    ("8", "01"): "叠加设置写入",
    ("8", "02"): "实时叠加启停/保存",
    ("8", "03"): "校准帧/校准参数读写",
    ("8", "04"): "RTMP 配置读写",
    ("8", "05"): "行星/批量叠加启停",
    ("8", "06"): "叠加删除/清空",
    ("8", "07"): "导出/保存结果",
    ("8", "09"): "其他叠加视频操作",
    ("9", "00"): "电源状态读取",
    ("9", "01"): "电源输出写入",
    ("9", "02"): "对象列表读取",
    ("9", "03"): "对象列表创建/重命名/添加",
    ("9", "04"): "对象列表删除",
    ("9", "05"): "天体数据读取/更新",
    ("9", "08"): "内部/未知符号",
    ("9", "09"): "其他杂项",
}

TERM_CN = {
    "camera": "相机",
    "cameras": "相机",
    "focuser": "调焦器",
    "wheel": "滤轮",
    "wheels": "滤轮",
    "scope": "赤道仪",
    "mount": "赤道仪",
    "plan": "计划",
    "sequence": "序列",
    "sequences": "序列",
    "stack": "叠加",
    "stacking": "叠加",
    "image": "图像",
    "img": "图像",
    "file": "文件",
    "setting": "设置",
    "state": "状态",
    "info": "信息",
    "value": "值",
    "position": "位置",
    "solve": "解算",
    "star": "星点",
    "polar": "极轴",
    "align": "对齐",
    "guiding": "导星",
    "dither": "抖动",
    "power": "电源",
    "output": "输出",
    "storage": "存储",
    "list": "列表",
    "object": "对象",
    "target": "目标",
    "get": "",
    "set": "",
    "start": "",
    "stop": "",
    "is": "",
    "can": "",
    "need": "",
    "clear": "",
    "delete": "",
    "del": "",
    "add": "",
    "rename": "",
    "import": "",
    "reset": "",
    "open": "",
    "close": "",
    "move": "",
    "read": "",
    "write": "",
    "test": "测试",
    "app": "App",
    "view": "视图",
    "device": "设备",
    "connection": "连接",
    "connected": "已连接",
    "time": "时间",
    "verified": "验证",
    "vl805": "USB控制器",
    "version": "版本",
    "encrypt": "加密",
    "ap": "热点",
    "station": "无线客户端",
    "scan": "扫描",
    "select": "选择",
    "remove": "移除",
    "auto": "自动",
    "connect": "连接",
    "and": "和",
    "config": "配置",
    "frame": "帧",
    "frames": "帧",
    "drive": "盘",
    "thread": "线程",
    "eth0": "以太网",
    "downgraded": "降级",
    "downgrade": "降级",
    "disk": "磁盘",
    "volume": "容量",
    "mass": "大容量",
    "path": "路径",
    "usb": "USB",
    "eject": "弹出",
    "page": "页面",
    "number": "数量",
    "name": "名称",
    "format": "格式化",
    "emmc": "eMMC",
    "export": "导出",
    "controls": "控制项",
    "control": "控制项",
    "exp": "曝光",
    "exposure": "曝光",
    "bin": "Bin",
    "16bit": "16-bit",
    "subframe": "ROI",
    "gain": "增益",
    "segment": "段",
    "pixel": "像元",
    "liveview": "实时预览",
    "abort": "中止",
    "expose": "曝光",
    "capture": "拍摄",
    "field": "字段",
    "record": "录制",
    "avi": "AVI",
    "rtmp": "RTMP",
    "current": "当前",
    "enabled": "启用",
    "autosave": "自动保存",
    "err": "错误",
    "progress": "进度",
    "cap": "能力",
    "ra": "RA",
    "dec": "Dec",
    "equ": "赤道",
    "coord": "坐标",
    "location": "位置",
    "pierside": "望远镜侧",
    "track": "跟踪",
    "moving": "运动状态",
    "goto": "Goto",
    "slew": "转动",
    "park": "停泊",
    "left": "左",
    "angle": "角度",
    "sync": "同步",
    "merid": "子午线",
    "delta": "差值",
    "am5": "AM5",
    "guide": "导星",
    "loop": "循环曝光",
    "flip": "翻转",
    "calibration": "校准",
    "restart": "重启",
    "caps": "能力",
    "slot": "槽位",
    "unidirection": "单向",
    "calibrate": "校准",
    "focuse": "对焦",
    "focus": "对焦",
    "result": "结果",
    "last": "最近",
    "3p": "三点",
    "pa": "极轴",
    "axis": "轴",
    "obj": "对象",
    "annotate": "标注",
    "annotated": "已标注",
    "find": "寻找",
    "type": "类型",
    "calib": "校准",
    "param": "参数",
    "stacked": "已叠加",
    "planet": "行星",
    "batch": "批量",
    "supply": "供电",
    "constellations": "星座",
    "comet": "彗星",
    "txt": "文本",
}
CN_OVERRIDES = {
    "test_connection": "连接测试。",
    "get_app_state": "读取当前 App 页面、拍摄、解算、叠加、导出等工作流状态。",
    "get_view_state": "读取视图/实时显示状态。",
    "get_device_state": "读取设备状态。",
    "set_page": "切换 ASIAIR 当前工作页面。",
    "stop_send": "停止发送或流式传输任务。",
    "pi_set_time": "设置盒子系统时间。",
    "pi_get_time": "读取盒子系统时间。",
    "pi_get_info": "读取盒子系统信息。",
    "pi_is_verified": "读取设备验证/授权状态。",
    "pi_vl805_version": "读取 USB 控制器固件/版本信息。",
    "pi_encrypt": "疑似设备/App 加密或授权辅助接口。",
    "pi_get_ap": "读取热点/AP 设置和状态。",
    "pi_shutdown": "关闭 ASIAIR。",
    "pi_reboot": "重启 ASIAIR。",
    "pi_station_scan": "扫描周围 Wi-Fi 网络。",
    "pi_station_set": "配置 Wi-Fi station。",
    "pi_station_state": "读取 Wi-Fi station 状态。",
    "pi_station_select": "选择 Wi-Fi station 配置。",
    "pi_station_list": "列出已保存/已扫描的 Wi-Fi station。",
    "pi_station_remove": "移除 Wi-Fi station 配置。",
    "pi_station_auto_connect": "配置 Wi-Fi 自动连接。",
    "pi_station_open": "启用 Wi-Fi station 模式。",
    "pi_station_close": "关闭 Wi-Fi station 模式。",
    "pi_eth0_state": "读取以太网状态。",
    "pi_set_eth0": "配置以太网参数。",
    "need_reboot": "读取是否需要重启。",
    "is_downgraded": "读取降级状态。",
    "clear_downgrade": "清除降级标记。",
    "get_disk_volume": "读取存储总容量和剩余容量。",
    "list_mass_storage": "列出已挂载存储设备。",
    "get_image_save_path": "读取当前图像保存位置。",
    "set_image_save_path": "设置当前图像保存位置。",
    "set_image_save_usb_disk": "设置 USB 存储为图像保存目标。",
    "eject_disk": "弹出外部存储。",
    "get_img_file_info": "读取图像文件元数据。",
    "set_img_file_info": "写入图像文件元数据。",
    "get_img_file_page_number": "读取图像浏览器页数。",
    "get_img_file_page_name": "读取图像浏览器页面/文件夹名称。",
    "delete_image": "删除图像文件。",
    "file_rename": "重命名文件。",
    "save_image": "保存当前图像。",
    "start_export_image": "启动图像导出。",
    "stop_export_image": "停止图像导出。",
    "can_format_emmc": "检查 eMMC 是否允许格式化；本身不执行格式化。",
    "get_current_img": "获取或引用当前图像。",
    "clear_autosave_err": "清除自动保存错误标记。",
    "scan_am5": "扫描 AM5/AM 系列赤道仪。",
    "StreamingThread": "内部流线程符号。",
    "my_write_canstop": "内部写入/停止辅助符号。",
    "get_power_supply": "读取供电状态。",
    "pi_output_get": "读取电源输出状态。",
    "pi_output_get2": "读取新版电源输出状态。",
    "pi_output_set": "设置电源输出状态。",
    "pi_output_set2": "设置新版电源输出状态。",
    "get_rtmp_config": "读取 RTMP 配置。",
    "set_rtmp_config": "设置 RTMP 配置。",
    "get_calib_frame": "读取校准帧配置。",
    "set_calib_frame": "设置校准帧配置。",
    "get_calib_param": "读取校准参数。",
    "set_calib_param": "设置校准参数。",
    "get_batch_stack_setting": "读取批量叠加设置。",
    "set_batch_stack_setting": "设置批量叠加设置。",
    "get_3p_pa_setting": "读取三点极轴设置。",
    "set_3p_pa_setting": "设置三点极轴设置。",
    "get_3p_pa_state": "读取三点极轴状态。",
}


def parse_catalog() -> list[dict[str, str]]:
    text = DOC_PATH.read_text(encoding="utf-8")
    known = text[text.index("## Known Method Catalog") :]
    rows: list[dict[str, str]] = []
    current_category = ""
    for line in known.splitlines():
        heading = re.match(r"^###\s+(.+)$", line)
        if heading:
            current_category = heading.group(1).strip()
            continue
        match = re.match(r"^\| `([^`]+)` \| ([^|]+) \| ([^|]+) \|$", line)
        if not match:
            continue
        method, risk, desc = (match.group(1).strip(), match.group(2).strip(), match.group(3).strip())
        if method != "Method":
            rows.append({"method": method, "risk": risk, "description_en": desc, "doc_category": current_category})
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if row["method"] not in seen:
            unique.append(row)
            seen.add(row["method"])
    return unique


def collect_status() -> tuple[set[str], set[str], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    success: set[str] = set()
    attempted: set[str] = set()
    success_notes: dict[str, list[str]] = defaultdict(list)
    failed_notes: dict[str, list[str]] = defaultdict(list)
    skipped_notes: dict[str, list[str]] = defaultdict(list)

    def mark_success(method: str | None, note: str = "") -> None:
        if method:
            attempted.add(method)
            success.add(method)
            if note:
                success_notes[method].append(note)

    def mark_fail(method: str | None, note: str = "") -> None:
        if method:
            attempted.add(method)
            if note:
                failed_notes[method].append(note)

    for path in sorted(REPORT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("skipped", []) if isinstance(data.get("skipped"), list) else []:
            method = item.get("method")
            if method and item.get("reason"):
                skipped_notes[method].append(item["reason"])
        for key in ("results", "actions", "reads", "restore_actions"):
            arr = data.get(key)
            if not isinstance(arr, list):
                continue
            for item in arr:
                if not isinstance(item, dict):
                    continue
                getter = item.get("getter")
                setter = item.get("setter")
                if getter and (item.get("before_code") == 0 or item.get("after_code") == 0 or item.get("ok") is True):
                    mark_success(getter, f"{path.name}: 读取成功")
                if setter:
                    if item.get("ok") is True:
                        mark_success(setter, f"{path.name}: 写入/恢复成功")
                    else:
                        mark_fail(setter, f"{path.name}: 尝试未成功")
                name = item.get("name")
                if name == "pixel_size":
                    mark_success("get_camera_info", f"{path.name}: 基线读取成功")
                    mark_fail("set_pixel_size", f"{path.name}: 候选参数失败")
                if isinstance(name, str) and name.startswith("control_"):
                    if item.get("ok") is True:
                        mark_success("get_control_value", f"{path.name}: 控制项读取成功")
                        mark_success("set_control_value", f"{path.name}: no-op 设置成功")
                    else:
                        mark_fail("set_control_value", f"{path.name}: 控制项 no-op 失败")
                method = item.get("method")
                if method:
                    if item.get("ok") is True:
                        mark_success(method, f"{path.name}: code=0")
                    else:
                        code = item.get("code")
                        err = item.get("error")
                        mark_fail(method, f"{path.name}: code={code}" + (f", {err}" if err else ""))
    return success, attempted, success_notes, failed_notes, skipped_notes


def subcode_for(method: str, major: str) -> str:
    table = {
        "0": [
            ({"test_connection", "pi_get_info", "pi_is_verified", "need_reboot", "is_downgraded", "get_device_state"}, "00"),
            ({"get_app_state", "get_view_state", "set_page", "stop_send"}, "01"),
            ({"pi_set_time", "pi_get_time", "pi_vl805_version"}, "02"),
            ({"pi_get_ap", "pi_station_scan", "pi_station_state", "pi_station_list"}, "03"),
            ({"pi_eth0_state", "pi_set_eth0"}, "05"),
            ({"pi_reboot", "pi_shutdown"}, "06"),
            ({"get_setting", "set_setting", "get_app_setting", "set_app_setting", "get_test_setting", "set_test_setting", "clear_downgrade"}, "07"),
            ({"pi_encrypt"}, "08"),
        ],
        "1": [
            ({"get_disk_volume", "list_mass_storage", "get_image_save_path"}, "00"),
            ({"set_image_save_path", "set_image_save_usb_disk"}, "01"),
            ({"get_img_file_info", "get_img_file_page_number", "get_img_file_page_name"}, "02"),
            ({"set_img_file_info"}, "03"),
            ({"file_rename", "save_image", "start_export_image", "stop_export_image"}, "04"),
            ({"delete_image", "eject_disk", "can_format_emmc"}, "05"),
        ],
        "2": [
            ({"get_connected_cameras", "get_camera_state", "get_camera_info", "get_controls", "can_liveview", "can_abort_expose"}, "00"),
            ({"get_control_value"}, "01"),
            ({"set_control_value"}, "02"),
            ({"get_camera_exp_and_bin", "get_camera_bin", "get_camera_16bit", "get_subframe", "get_gain_segment", "get_img_name_field"}, "03"),
            ({"set_camera_exp_and_bin", "set_camera_bin", "set_subframe", "set_img_name_field"}, "04"),
            ({"start_exposure", "stop_exposure", "stop_capture"}, "05"),
            ({"start_record_avi", "stop_record_avi", "start_avi_rtmp", "stop_avi_rtmp"}, "06"),
            ({"open_camera", "close_camera"}, "07"),
            ({"get_current_img"}, "08"),
            ({"set_camera_16bit", "set_pixel_size"}, "09"),
        ],
        "3": [
            ({"get_sequence_number", "get_sequence", "get_sequence_setting", "get_target_sequences", "get_plan", "get_enabled_plan", "list_plan"}, "00"),
            ({"set_sequence", "set_sequence_setting", "set_plan", "import_plan"}, "01"),
            ({"reset_plan", "reset_sequence_progress"}, "02"),
            ({"delete_sequence", "clear_sequence", "delete_plan", "clear_plan"}, "03"),
            ({"clear_autosave_err"}, "04"),
        ],
        "4": [
            ({"get_merid_delta", "get_merid_setting", "scope_get_cap", "scope_get_ra_dec", "scope_get_equ_coord", "scope_get_location", "scope_get_pierside", "scope_get_track_state", "scope_get_target_pierside", "scope_is_moving"}, "00"),
            ({"scope_set_track_state", "scope_set_target_pierside", "set_merid_setting"}, "01"),
            ({"scope_goto", "scope_move", "scope_move_left_by_angle", "scope_sync", "scope_park"}, "02"),
            ({"start_auto_goto", "start_auto_goto_pixel", "stop_auto_goto"}, "03"),
            ({"scan_am5"}, "04"),
            ({"scope_abort_slew"}, "05"),
        ],
        "5": [
            ({"get_flip_calibration", "get_dither"}, "00"),
            ({"set_dither"}, "01"),
            ({"guide", "loop", "find_star"}, "02"),
            ({"dither", "flip_calibration", "restart_guide"}, "03"),
        ],
        "6": [
            ({"get_connected_wheels", "get_wheel_state", "get_connected_focuser", "get_focuser_state", "get_focuser_caps"}, "00"),
            ({"get_wheel_position", "get_focuser_value", "get_focuser_position"}, "01"),
            ({"get_wheel_slot_name", "get_wheel_setting", "get_focuser_setting"}, "02"),
            ({"set_wheel_slot_name", "set_wheel_setting", "set_wheel_unidirection", "set_focuser_value", "set_focuser_setting"}, "03"),
            ({"set_wheel_position", "calibrate_wheel", "move_focuser", "stop_focuser", "start_auto_focuse", "stop_auto_focuse"}, "04"),
            ({"open_wheel", "close_wheel", "open_focuser", "close_focuser"}, "05"),
            ({"get_auto_focus_img"}, "06"),
        ],
        "7": [
            ({"get_solve_result", "get_last_solve_result", "get_solve_obj", "get_annotate_result", "is_img_file_annotated", "get_find_star_result"}, "00"),
            ({"start_solve", "start_annotate", "start_find_star"}, "01"),
            ({"stop_solve", "stop_annotate", "stop_find_star"}, "02"),
            ({"set_polar_align_image", "rm_polar_align_image", "get_polar_align_image"}, "03"),
            ({"start_polar_align", "pause_polar_align", "stop_polar_align"}, "04"),
            ({"get_polar_axis", "get_3p_pa_setting", "get_3p_pa_state"}, "05"),
            ({"set_3p_pa_setting"}, "06"),
        ],
        "8": [
            ({"get_stack_info", "get_stack_setting", "get_stacked_img", "get_batch_stack_setting"}, "00"),
            ({"set_stack_type", "set_stack_setting", "set_batch_stack_setting"}, "01"),
            ({"start_stack", "stop_stack", "save_stack"}, "02"),
            ({"set_calib_frame", "get_calib_frame", "set_calib_param", "get_calib_param"}, "03"),
            ({"get_rtmp_config", "set_rtmp_config"}, "04"),
            ({"start_planet_stack", "stop_planet_stack", "start_batch_stack", "stop_batch_stack"}, "05"),
            ({"clear_stack", "clear_planet_stack", "clear_batch_stack", "del_batch_stack_file"}, "06"),
        ],
        "9": [
            ({"get_power_supply", "pi_output_get", "pi_output_get2"}, "00"),
            ({"pi_output_set", "pi_output_set2"}, "01"),
            ({"get_list", "get_obj"}, "02"),
            ({"add_list", "rename_list", "add_obj"}, "03"),
            ({"del_list", "del_obj"}, "04"),
            ({"get_constellations", "get_comet_position", "get_planet_position", "update_comet_txt"}, "05"),
            ({"StreamingThread", "my_write_canstop", "pi_encrypt"}, "08"),
        ],
    }
    if major == "0" and method.startswith("pi_station_"):
        return "04"
    for methods, subcode in table.get(major, []):
        if method in methods:
            return subcode
    return "09"


def description_for(method: str, english: str) -> str:
    if method in CN_OVERRIDES:
        return CN_OVERRIDES[method]
    if method.startswith(("get_", "list_", "is_", "can_", "need_", "test_", "scope_get_")):
        action = "读取/查询"
    elif method.startswith(("set_", "pi_set_")):
        action = "设置"
    elif method.startswith("start_"):
        action = "启动"
    elif method.startswith("stop_"):
        action = "停止"
    elif method.startswith(("delete_", "del_", "clear_", "rm_")):
        action = "删除/清除"
    elif method.startswith(("add_", "import_", "rename_")) or method == "file_rename":
        action = "创建/导入/重命名"
    elif method.startswith(("open_", "close_")):
        action = "连接/断开"
    elif method.startswith(("move_", "scope_move", "scope_goto", "guide", "dither")):
        action = "运动/导星"
    else:
        action = "操作"
    words = method.replace("pi_", "盒子_").replace("scope_", "赤道仪_").replace("3p", "三点").split("_")
    translated = "".join(TERM_CN.get(word, word) for word in words if word)
    return f"{action}{translated}。"


def special_note_for(method: str, risk: str) -> str:
    sensitive_methods = {"pi_get_ap", "get_setting"}
    remote_loss_methods = {
        "pi_shutdown",
        "pi_reboot",
        "pi_station_set",
        "pi_station_select",
        "pi_station_remove",
        "pi_station_auto_connect",
        "pi_station_open",
        "pi_station_close",
        "pi_set_eth0",
        "pi_output_set",
        "pi_output_set2",
    }
    destructive_methods = {
        "delete_image",
        "eject_disk",
        "del_batch_stack_file",
        "clear_stack",
        "clear_planet_stack",
        "clear_batch_stack",
        "delete_sequence",
        "clear_sequence",
        "delete_plan",
        "clear_plan",
        "del_list",
        "del_obj",
        "rm_polar_align_image",
    }
    motion_methods = {
        "guide",
        "dither",
        "loop",
        "find_star",
        "flip_calibration",
        "restart_guide",
        "set_wheel_position",
        "calibrate_wheel",
        "move_focuser",
        "scope_set_track_state",
        "scope_set_target_pierside",
        "scope_goto",
        "scope_park",
        "scope_move",
        "scope_move_left_by_angle",
        "scope_sync",
        "start_auto_goto",
        "start_auto_goto_pixel",
        "set_merid_setting",
    }
    plan_methods = {"set_sequence", "set_sequence_setting", "set_plan", "import_plan", "reset_plan", "reset_sequence_progress"}
    if method == "set_camera_16bit":
        return "实测会把 16-bit 切成 false，并导致预览 FITS 变 8-bit；需重启相机恢复。"
    if method in sensitive_methods:
        return "可能返回敏感字段，报告必须脱敏。"
    if method in remote_loss_methods:
        return "可能导致远程失联、重启、关机或断电，远程禁测。"
    if method in destructive_methods:
        return "破坏性操作，仅在精确确认目标后测试。"
    if method in motion_methods:
        return "会触发设备运动或导星动作，需实时监督。"
    if method in plan_methods:
        return "会修改生产计划或进度，需隔离测试计划。"
    if risk == "UNKNOWN":
        return "内部/未知接口，暂不测试。"
    return ""


def build_rows() -> list[list[str]]:
    catalog = parse_catalog()
    success, attempted, _success_notes, _failed_notes, _skipped_notes = collect_status()
    failed_unresolved = {method for method in attempted if method not in success}
    rows: list[list[str]] = []
    for item in catalog:
        method = item["method"]
        status = "1" if method in success else "2" if method in failed_unresolved else "3"
        major = MAJOR_DIGIT.get(item["doc_category"], "9")
        sub = subcode_for(method, major)
        code = status + major + sub
        note = special_note_for(method, item["risk"])
        rows.append([code, method, description_for(method, item["description_en"]), note])
    return sorted(rows, key=lambda row: (row[0], row[1]))


def write_xlsx(rows: list[list[str]]) -> None:
    sheets = [
        ("总分类", [["编号", "方法名", "方法具体描述", "备注"]] + rows),
        (
            "四位编号说明",
            [["编码位", "数字/范围", "含义", "备注"]]
            + [["第一位：状态", digit, label, "1=成功，2=失败，3=未测试"] for digit, label in STATUS_LABEL.items()]
            + [["第二位：大类", digit, label, "按 ASIAIR 功能域归并"] for digit, label in MAJOR_LABEL.items()]
            + [["第三四位：小类", "00-99", "在每个大类内解释", "同一小类可包含多个方法；编号是分类码，不是唯一流水号"]],
        ),
        (
            "小类说明",
            [["第二位大类", "后两位小类", "小类名称", "说明"]]
            + [[MAJOR_LABEL[major], sub, label, f"完整编号形如 状态{major}{sub}"] for (major, sub), label in sorted(SUB_LABEL.items())],
        ),
        (
            "统计",
            [
                ["项目", "数值", "说明", ""],
                ["方法总数", str(len(rows)), "来自 docs/asiair-jsonrpc.md 的 Known Method Catalog", ""],
                ["已测试成功", str(sum(row[0].startswith("1") for row in rows)), "编号首位 1", ""],
                ["测试失败", str(sum(row[0].startswith("2") for row in rows)), "编号首位 2；表示已尝试但未跑通", ""],
                ["未测试", str(sum(row[0].startswith("3") for row in rows)), "编号首位 3；表示没有发送该方法命令", ""],
                ["生成时间", datetime.now().isoformat(timespec="seconds"), "本地时间", ""],
            ],
        ),
    ]

    def col_letter(number: int) -> str:
        text = ""
        while number:
            number, rem = divmod(number - 1, 26)
            text = chr(65 + rem) + text
        return text

    def cell_xml(value: Any, row_idx: int, col_idx: int) -> str:
        ref = f"{col_letter(col_idx)}{row_idx}"
        text = "" if value is None else str(value).replace("\x00", "")
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'

    def sheet_xml(data: list[list[Any]], widths: list[int]) -> str:
        max_cols = max(len(row) for row in data)
        max_rows = len(data)
        cols = "<cols>" + "".join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, width in enumerate(widths, 1)) + "</cols>"
        sheet_rows = []
        for r_idx, row in enumerate(data, 1):
            sheet_rows.append(f'<row r="{r_idx}">' + "".join(cell_xml(value, r_idx, c_idx) for c_idx, value in enumerate(row, 1)) + "</row>")
        dim = f"A1:{col_letter(max_cols)}{max_rows}"
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<dimension ref="{dim}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f"{cols}<sheetData>{''.join(sheet_rows)}</sheetData><autoFilter ref=\"{dim}\"/></worksheet>"
        )

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for index in range(1, len(sheets) + 1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append("</Types>")
    workbook_sheets = "".join(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>' for index, (name, _) in enumerate(sheets, 1))
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{workbook_sheets}</sheets></workbook>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>' for index in range(1, len(sheets) + 1))
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        + "</Relationships>"
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Microsoft YaHei"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        "</styleSheet>"
    )
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>ASIAIR JSON-RPC Method Classification 4-Digit</dc:title><dc:creator>asiairbridge</dc:creator>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified></cp:coreProperties>'
    )
    app_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>asiairbridge</Application></Properties>'
    )
    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_XLSX, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "".join(content_types))
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", app_xml)
        widths = {1: [10, 34, 72, 128], 2: [22, 14, 36, 58], 3: [24, 14, 42, 40], 4: [18, 16, 66, 16]}
        for index, (_name, data) in enumerate(sheets, 1):
            zf.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(data, widths[index]))


def write_landscape_images(rows: list[list[str]]) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_image in OUT_DIR.glob("asiair-jsonrpc-method-classification-4digit-landscape-cn*.png"):
        old_image.unlink()
    font_regular = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
    font_small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 13)
    font_bold = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 14)
    font_title = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 24)
    font_code = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 15)
    margin = 20
    title_h = 52
    gap = 12
    panel_w = 760
    col_widths = [58, 150, 372, 180]
    panel_header_h = 26
    row_h = 54
    rows_per_panel = 26
    panels_per_page = 5
    rows_per_page = rows_per_panel * panels_per_page
    img_w = margin * 2 + panel_w * panels_per_page + gap * (panels_per_page - 1)
    img_h = margin + title_h + panel_header_h + row_h * rows_per_panel + margin

    def width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
        return int(draw.textbbox((0, 0), text, font=font)[2]) if text else 0

    def wrap(draw: ImageDraw.ImageDraw, text: str, max_w: int, font: ImageFont.FreeTypeFont, max_lines: int) -> list[str]:
        tokens = re.findall(r"[A-Za-z0-9_./:\\\\<>\-]+|\s+|.", str(text).replace("\r", " ").replace("\n", " "))
        lines: list[str] = []
        buf = ""
        for token in tokens:
            candidate = buf + (" " if token.isspace() else token)
            if buf and width(draw, candidate, font) > max_w:
                lines.append(buf.rstrip())
                buf = "" if token.isspace() else token
            else:
                buf = candidate
        if buf:
            lines.append(buf.rstrip())
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip("；。，,. ") + "…"
        return lines or [""]

    def status_style(code: str) -> tuple[str, str, str]:
        if code.startswith("1"):
            return "#e8f7ef", "#2f9e56", "#0f5132"
        if code.startswith("2"):
            return "#fff0ed", "#d94835", "#7f1d1d"
        return "#f1f5f9", "#64748b", "#334155"

    def draw_panel_header(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.rectangle([x, y, x + panel_w, y + panel_header_h], fill="#243047", outline="#93a4b8")
        cx = x
        for idx, label in enumerate(["编号", "方法名", "描述", "备注"]):
            draw.line([cx, y, cx, y + panel_header_h], fill="#93a4b8")
            draw.text((cx + 6, y + 4), label, font=font_bold, fill="#ffffff")
            cx += col_widths[idx]
        draw.line([x + panel_w, y, x + panel_w, y + panel_header_h], fill="#93a4b8")

    def draw_row(draw: ImageDraw.ImageDraw, x: int, y: int, row: list[str], index: int) -> None:
        code, method, desc, note = row
        bg, stripe, code_color = status_style(code)
        if index % 2:
            bg = "#ffffff" if code.startswith("3") else bg
        draw.rectangle([x, y, x + panel_w, y + row_h], fill=bg, outline="#d3dce8")
        draw.rectangle([x, y, x + 4, y + row_h], fill=stripe)
        cx = x
        values = [code, method, desc, note]
        fonts = [font_code, font_small, font_small, font_small]
        max_lines = [1, 2, 2, 2]
        fills = [code_color, "#111827", "#111827", "#111827"]
        for col, value in enumerate(values):
            draw.line([cx, y, cx, y + row_h], fill="#d3dce8")
            ty = y + 5
            for line in wrap(draw, value, col_widths[col] - 14, fonts[col], max_lines[col]):
                draw.text((cx + 5, ty), line, font=fonts[col], fill=fills[col])
                ty += int(fonts[col].size * 1.16) + 1
            cx += col_widths[col]
        draw.line([x + panel_w, y, x + panel_w, y + row_h], fill="#d3dce8")

    def draw_page(path: Path, chunk: list[list[str]], page_no: int, page_total: int, suffix: str = "") -> None:
        img = Image.new("RGB", (img_w, img_h), "#f8fafc")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, img_w, margin + title_h], fill="#172033")
        title = "ASIAIR JSON-RPC 方法总分类表（横向分栏版）"
        if suffix:
            title += f" - {suffix}"
        draw.text((margin, margin + 8), title, font=font_title, fill="#ffffff")
        subtitle = f"第 {page_no}/{page_total} 页 · 每页 {panels_per_page} 栏 x {rows_per_panel} 行 · 四位编号：状态/大类/小类"
        draw.text((margin + 660, margin + 17), subtitle, font=font_regular, fill="#cbd5e1")
        start_y = margin + title_h
        for panel_idx in range(panels_per_page):
            panel_rows = chunk[panel_idx * rows_per_panel : (panel_idx + 1) * rows_per_panel]
            x = margin + panel_idx * (panel_w + gap)
            draw_panel_header(draw, x, start_y)
            y = start_y + panel_header_h
            for row_idx, row in enumerate(panel_rows, start=1):
                draw_row(draw, x, y, row, row_idx)
                y += row_h
            for _ in range(rows_per_panel - len(panel_rows)):
                draw.rectangle([x, y, x + panel_w, y + row_h], fill="#ffffff", outline="#e5e7eb")
                y += row_h
        img.save(path, "PNG", optimize=True)

    written: list[Path] = []
    page_total = math.ceil(len(rows) / rows_per_page)
    for page_idx in range(page_total):
        path = OUT_DIR / f"asiair-jsonrpc-method-classification-4digit-landscape-cn-{page_idx + 1:02d}.png"
        draw_page(path, rows[page_idx * rows_per_page : (page_idx + 1) * rows_per_page], page_idx + 1, page_total)
        written.append(path)
    for status, suffix, name in [("1", "success", "成功"), ("2", "failed", "失败"), ("3", "untested", "未测试")]:
        status_rows = [row for row in rows if row[0].startswith(status)]
        total = math.ceil(len(status_rows) / rows_per_page) or 1
        for page_idx in range(total):
            path = OUT_DIR / f"asiair-jsonrpc-method-classification-4digit-landscape-cn-{suffix}-{page_idx + 1:02d}.png"
            draw_page(path, status_rows[page_idx * rows_per_page : (page_idx + 1) * rows_per_page], page_idx + 1, total, name)
            written.append(path)
    return written


def write_html(rows: list[list[str]]) -> None:
    def status_name(code: str) -> str:
        return STATUS_LABEL.get(code[:1], "未知")

    def status_class(code: str) -> str:
        return {"1": "success", "2": "failed", "3": "untested"}.get(code[:1], "unknown")

    success_count = sum(row[0].startswith("1") for row in rows)
    failed_count = sum(row[0].startswith("2") for row in rows)
    untested_count = sum(row[0].startswith("3") for row in rows)
    generated_at = datetime.now().isoformat(timespec="seconds")
    body_rows = []
    for code, method, desc, note in rows:
        body_rows.append(
            "<tr "
            f'data-status="{escape(status_class(code))}" '
            f'data-code="{escape(code)}" '
            f'data-method="{escape(method.lower())}">'
            f'<td class="code"><span class="code-pill {escape(status_class(code))}">{escape(code)}</span></td>'
            f"<td class=\"method\"><code>{escape(method)}</code></td>"
            f"<td>{escape(desc)}</td>"
            f"<td class=\"note\">{escape(note)}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ASIAIR JSON-RPC 方法总分类表</title>
  <style>
    :root {{
      --bg: #f6f8fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #64748b;
      --line: #d8e0ea;
      --head: #172033;
      --success: #23884f;
      --success-bg: #e9f8ef;
      --failed: #ca3b2f;
      --failed-bg: #fff0ee;
      --untested: #64748b;
      --untested-bg: #f1f5f9;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      padding: 16px 22px 14px;
      background: var(--head);
      color: white;
      box-shadow: 0 2px 16px rgba(15, 23, 42, .18);
    }}
    .topline {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
      font-weight: 700;
    }}
    .meta {{
      color: #cbd5e1;
      font-size: 12px;
      white-space: nowrap;
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(240px, 520px) auto;
      gap: 12px;
      align-items: center;
    }}
    input[type="search"] {{
      width: 100%;
      height: 36px;
      border: 1px solid #475569;
      border-radius: 6px;
      padding: 0 12px;
      background: #0f172a;
      color: white;
      outline: none;
      font-size: 14px;
    }}
    input[type="search"]::placeholder {{ color: #94a3b8; }}
    .filters {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    button {{
      height: 36px;
      border: 1px solid #475569;
      border-radius: 6px;
      padding: 0 12px;
      color: #e2e8f0;
      background: #1e293b;
      cursor: pointer;
      font-size: 13px;
    }}
    button.active {{
      border-color: #93c5fd;
      color: white;
      background: #2563eb;
    }}
    main {{
      padding: 18px 22px 28px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
    }}
    .stat .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .stat .value {{
      font-size: 22px;
      font-weight: 700;
      line-height: 1;
    }}
    .table-wrap {{
      overflow: auto;
      max-height: calc(100vh - 178px);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      min-width: 1160px;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      border-right: 1px solid var(--line);
      padding: 7px 9px;
      vertical-align: top;
      line-height: 1.38;
    }}
    th {{
      position: sticky;
      top: 0;
      z-index: 2;
      color: white;
      background: #243047;
      text-align: left;
      font-size: 12px;
      font-weight: 700;
    }}
    th:first-child, td:first-child {{
      width: 82px;
      text-align: center;
    }}
    th:nth-child(2), td:nth-child(2) {{ width: 240px; }}
    th:nth-child(3), td:nth-child(3) {{ width: 520px; }}
    th:nth-child(4), td:nth-child(4) {{ width: 360px; }}
    tr.success {{ background: var(--success-bg); }}
    tr.failed {{ background: var(--failed-bg); }}
    tr.untested {{ background: var(--untested-bg); }}
    tr:hover {{ filter: brightness(.985); }}
    code {{
      font-family: Consolas, "Cascadia Mono", monospace;
      font-size: 12px;
      color: #0f172a;
    }}
    .code-pill {{
      display: inline-block;
      min-width: 52px;
      border-radius: 5px;
      padding: 3px 6px;
      color: white;
      font-weight: 700;
      font-family: Consolas, "Cascadia Mono", monospace;
      font-size: 12px;
    }}
    .code-pill.success {{ background: var(--success); }}
    .code-pill.failed {{ background: var(--failed); }}
    .code-pill.untested {{ background: var(--untested); }}
    .note {{ color: #334155; }}
    .hidden {{ display: none; }}
    @media (max-width: 900px) {{
      .controls {{ grid-template-columns: 1fr; }}
      .filters {{ justify-content: flex-start; }}
      .stats {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
      .meta {{ white-space: normal; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topline">
      <h1>ASIAIR JSON-RPC 方法总分类表</h1>
      <div class="meta">四位编号：状态 / 大类 / 小类 · 生成时间 {escape(generated_at)}</div>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="搜索编号、方法名、描述或备注">
      <div class="filters" aria-label="状态筛选">
        <button class="active" data-filter="all">全部</button>
        <button data-filter="success">成功</button>
        <button data-filter="failed">失败</button>
        <button data-filter="untested">未测试</button>
      </div>
    </div>
  </header>
  <main>
    <section class="stats">
      <div class="stat"><div class="label">全部方法</div><div class="value" id="shownCount">{len(rows)}</div></div>
      <div class="stat"><div class="label">已测试成功</div><div class="value">{success_count}</div></div>
      <div class="stat"><div class="label">测试失败</div><div class="value">{failed_count}</div></div>
      <div class="stat"><div class="label">未测试</div><div class="value">{untested_count}</div></div>
    </section>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>编号</th><th>方法名</th><th>方法具体描述</th><th>备注</th></tr>
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
    </div>
  </main>
  <script>
    const search = document.getElementById('search');
    const buttons = [...document.querySelectorAll('button[data-filter]')];
    const rows = [...document.querySelectorAll('tbody tr')];
    const shownCount = document.getElementById('shownCount');
    let filter = 'all';

    function applyFilter() {{
      const q = search.value.trim().toLowerCase();
      let shown = 0;
      for (const row of rows) {{
        const statusOk = filter === 'all' || row.dataset.status === filter;
        const queryOk = !q || row.innerText.toLowerCase().includes(q);
        const visible = statusOk && queryOk;
        row.classList.toggle('hidden', !visible);
        if (visible) shown++;
      }}
      shownCount.textContent = shown;
    }}

    search.addEventListener('input', applyFilter);
    for (const button of buttons) {{
      button.addEventListener('click', () => {{
        filter = button.dataset.filter;
        buttons.forEach(item => item.classList.toggle('active', item === button));
        applyFilter();
      }});
    }}
  </script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")



def main() -> None:
    rows = build_rows()
    write_xlsx(rows)
    write_html(rows)
    images = write_landscape_images(rows)
    print(
        json.dumps(
            {
                "xlsx": str(OUT_XLSX),
                "html": str(OUT_HTML),
                "image_dir": str(OUT_DIR),
                "rows": len(rows),
                "success": sum(row[0].startswith("1") for row in rows),
                "failed": sum(row[0].startswith("2") for row in rows),
                "untested": sum(row[0].startswith("3") for row in rows),
                "images": [str(path) for path in images],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
