"""米家监控录像:按日期列出已完成的分段并提供下载,以及直播流的实时码率统计。

录像由独立 ffmpeg 录制器写到 <盘>\\camera_rec\\<cam>\\{h264,hevc}\\,文件名形如
<cam>_YYYYMMDD_HHMMSS.mp4。存储盘按优先级 F→E(F 在用 F,不在退 E);列举时
跨所有当前可用盘合并(历史不丢)。本模块只读列目录 + 校验文件名(防穿越)+ 读
go2rtc 字节数,不做任何写操作。
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

# 存储优先级:F 盘优先,不在退到 E 盘(与 go2rtc/storage.py 一致)
_PRIORITY = ("F:", "E:")
_CAMERA_SUB = "camera_rec"
CAMERAS = ("ulanqab", "ulanqab2")
CODECS = ("h264", "hevc")
STREAMS = CODECS  # 兼容旧引用名
_NAME_RE = re.compile(r"^(ulanqab2?)_(\d{8})_(\d{6})\.mp4$")


def _drive_ok(d: str) -> bool:
    try:
        return os.path.exists(d + "\\")
    except OSError:
        return False


def _camera_roots() -> list[Path]:
    roots = [Path(d + "\\") / _CAMERA_SUB for d in _PRIORITY if _drive_ok(d)]
    return roots or [Path(_PRIORITY[-1] + "\\") / _CAMERA_SUB]


def _cam(cam: str | None) -> str:
    return cam if cam in CAMERAS else CAMERAS[0]


def _parse_name(name: str, cam: str):
    m = _NAME_RE.match(name)
    if not m or m.group(1) != cam:
        return None
    d, t = m.group(2), m.group(3)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}", f"{t[0:2]}:{t[2:4]}:{t[4:6]}"


def _scan_all(cam: str) -> list[dict]:
    """跨所有可用盘扫某相机两编码的已完成段(每个 流目录 排除最新正在录的一段)。"""
    entries: list[dict] = []
    for root in _camera_roots():
        for s in CODECS:
            d = root / cam / s
            if not d.is_dir():
                continue
            files = sorted(
                (p for p in d.glob(cam + "_*.mp4") if _parse_name(p.name, cam)),
                key=lambda p: p.name,
            )
            if files:
                files = files[:-1]  # 排除该目录最新(正在录、未写 moov)
            for p in files:
                parsed = _parse_name(p.name, cam)
                if not parsed:
                    continue
                dt, tm = parsed
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                entries.append({
                    "stream": s, "name": p.name, "date": dt, "time": tm,
                    "size_mb": round(size / 1048576, 1),
                })
    return entries


def list_recordings_payload(stream: str | None = None, date: str | None = None,
                            cam: str | None = None) -> dict:
    """返回 {ok, cam, cameras[], dates[](倒序), items[](选中日期), selected_date}。"""
    cam = _cam(cam)
    entries = _scan_all(cam)
    dates = sorted({e["date"] for e in entries}, reverse=True)
    selected = date if date in dates else (dates[0] if dates else None)
    sf = stream if stream in CODECS else None
    items = [e for e in entries
             if e["date"] == selected and (sf is None or e["stream"] == sf)]
    items.sort(key=lambda x: (x["time"], x["stream"]), reverse=True)
    total_mb = round(sum(e["size_mb"] for e in items), 1)
    return {
        "ok": True, "cam": cam, "cameras": list(CAMERAS),
        "dates": dates, "items": items,
        "selected_date": selected, "count": len(items), "total_mb": total_mb,
    }


def resolve_recording(stream: str | None, name: str | None,
                      cam: str | None = None) -> Path | None:
    """把 (cam, stream, name) 安全解析为录像文件路径(跨盘查找);非法/不存在返回 None。"""
    cam = _cam(cam)
    if stream not in CODECS:
        return None
    if not name or not _parse_name(name, cam):
        return None
    for root in _camera_roots():
        p = root / cam / stream / name
        try:
            if p.is_file():
                return p
        except OSError:
            pass
    return None


def stream_stats() -> dict:
    """从本机 go2rtc 取各路直播流累计字节数(前端据此算实时码率)。失败返回 ok:false。

    返回 {ok, cameras:{<cam>:{bytes,src_bytes}}, 以及顶层 bytes/src_bytes(=第一路,兼容旧前端)}。
    """
    try:
        with urllib.request.urlopen("http://127.0.0.1:1984/api/streams", timeout=3) as r:
            data = json.load(r)
    except Exception:
        return {"ok": False}

    def prod_bytes(name: str) -> int:
        s = data.get(name) or {}
        tot = 0
        for p in (s.get("producers") or []):
            b = p.get("bytes_recv")
            if isinstance(b, int):
                tot += b
        return tot

    cams = {c: {"bytes": prod_bytes(c), "src_bytes": prod_bytes(c + "_src")}
            for c in CAMERAS}
    first = CAMERAS[0]
    return {
        "ok": True,
        "cameras": cams,
        "bytes": cams[first]["bytes"],
        "src_bytes": cams[first]["src_bytes"],
    }
