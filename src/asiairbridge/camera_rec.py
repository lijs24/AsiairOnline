"""米家监控录像:按日期列出已完成的分段并提供下载,以及直播流的实时码率统计。

录像由独立 ffmpeg 录制器写到 F:\\camera_rec\\ulanqab\\{h264,hevc}\\,
文件名形如 ulanqab_YYYYMMDD_HHMMSS.mp4(普通 mp4,每段关闭后带完整 moov)。
本模块只读列目录 + 校验文件名(防路径穿越)+ 读 go2rtc 字节数,不做任何写操作。
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

RECORDINGS_ROOT = Path("F:/camera_rec/ulanqab")
STREAMS = ("h264", "hevc")
_NAME_RE = re.compile(r"^ulanqab_(\d{8})_(\d{6})\.mp4$")


def _parse_name(name: str):
    m = _NAME_RE.match(name)
    if not m:
        return None
    d, t = m.group(1), m.group(2)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}", f"{t[0:2]}:{t[2:4]}:{t[4:6]}"


def _scan_all() -> list[dict]:
    """扫描两个流的全部已完成段(排除每个流最新的、正在录的一段)。"""
    entries: list[dict] = []
    for s in STREAMS:
        d = RECORDINGS_ROOT / s
        if not d.is_dir():
            continue
        files = sorted(
            (p for p in d.glob("ulanqab_*.mp4") if _parse_name(p.name)),
            key=lambda p: p.name,
        )
        if files:
            files = files[:-1]  # 排除最新(正在录、未写 moov)
        for p in files:
            parsed = _parse_name(p.name)
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


def list_recordings_payload(stream: str | None = None, date: str | None = None) -> dict:
    """返回 {ok, dates[](倒序), items[](选中日期), selected_date}。"""
    entries = _scan_all()
    dates = sorted({e["date"] for e in entries}, reverse=True)
    selected = date if date in dates else (dates[0] if dates else None)
    sf = stream if stream in STREAMS else None
    items = [e for e in entries
             if e["date"] == selected and (sf is None or e["stream"] == sf)]
    items.sort(key=lambda x: (x["time"], x["stream"]), reverse=True)
    total_mb = round(sum(e["size_mb"] for e in items), 1)
    return {
        "ok": True, "dates": dates, "items": items,
        "selected_date": selected, "count": len(items), "total_mb": total_mb,
    }


def resolve_recording(stream: str | None, name: str | None) -> Path | None:
    """把 (stream, name) 安全解析为录像文件路径;非法/不存在返回 None。"""
    if stream not in STREAMS:
        return None
    if not name or not _NAME_RE.match(name):
        return None
    p = RECORDINGS_ROOT / stream / name
    try:
        if p.is_file():
            return p
    except OSError:
        pass
    return None


def stream_stats() -> dict:
    """从本机 go2rtc 取直播流累计字节数(前端据此算实时码率)。失败返回 ok:false。"""
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

    return {"ok": True, "bytes": prod_bytes("ulanqab"), "src_bytes": prod_bytes("ulanqab_src")}
