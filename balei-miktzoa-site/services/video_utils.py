from __future__ import annotations
import math
import struct
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple
VideoMeta = Dict[str, float]
def get_local_video_metadata(static_root: Path | str, relative_path: str | None) -> VideoMeta:
    """Return orientation metadata for a video stored under the static folder."""
    if not relative_path:
        return {}
    try:
        static_root_path = Path(static_root).resolve(strict=True)
    except FileNotFoundError:
        return {}
    try:
        target = (static_root_path / relative_path).resolve(strict=True)
    except FileNotFoundError:
        return {}
    try:
        target.relative_to(static_root_path)
    except ValueError:
        # Resolved path escapes the static directory – ignore for safety.
        return {}
    return _read_video_metadata_cached(str(target))
@lru_cache(maxsize=256)
def _read_video_metadata_cached(full_path: str) -> VideoMeta:
    path = Path(full_path)
    if not path.exists() or not path.is_file():
        return {}
    if path.suffix.lower() != ".mp4":
        return {}
    try:
        rotation, width, height = _extract_mp4_track_metadata(path)
    except Exception:
        return {}
    meta: VideoMeta = {}
    if rotation is not None:
        normalized = (int(round(rotation / 90.0)) * 90) % 360
        if normalized in (90, 180, 270):
            meta["rotation"] = float(normalized)
    if width and height:
        meta["width"] = float(width)
        meta["height"] = float(height)
        if height:
            aspect_landscape = float(width) / float(height)
            if aspect_landscape > 0:
                meta["aspect_landscape"] = aspect_landscape
                meta["aspect_portrait"] = float(height) / float(width)
    return meta
def _extract_mp4_track_metadata(path: Path) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    with path.open("rb") as fh:
        moov = _find_box(fh, ["moov"])
        if not moov:
            return None, None, None
        moov_start, moov_end, moov_header = moov
        video_trak = _find_video_trak(fh, moov_start + moov_header, moov_end)
        if not video_trak:
            return None, None, None
        trak_start, trak_end, trak_header = video_trak
        return _read_rotation_and_size(fh, trak_start + trak_header, trak_end)
def _find_video_trak(fh, start: int, end: Optional[int]):
    for box_type, box_start, box_end, header in _iter_boxes(fh, start, end):
        if box_type != "trak" or box_end is None:
            continue
        handler = _read_handler_type(fh, box_start + header, box_end)
        if handler == b"vide":
            return box_start, box_end, header
    return None
def _read_handler_type(fh, start: int, end: Optional[int]):
    hdlr = _find_box(fh, ["mdia", "hdlr"], start, end)
    if not hdlr:
        return None
    box_start, box_end, header = hdlr
    if box_end is None:
        return None
    fh.seek(box_start + header)
    header_bytes = fh.read(12)
    if len(header_bytes) < 12:
        return None
    return header_bytes[8:12]
def _read_rotation_and_size(fh, start: int, end: Optional[int]):
    tkhd = _find_box(fh, ["tkhd"], start, end)
    if not tkhd:
        return None, None, None
    box_start, box_end, header = tkhd
    if box_end is None:
        return None, None, None
    fh.seek(box_start + header)
    payload = fh.read(box_end - (box_start + header))
    if not payload:
        return None, None, None
    version = payload[0]
    idx = 4
    if version == 1:
        idx += 8 + 8 + 4 + 4 + 8
    else:
        idx += 4 + 4 + 4 + 4 + 4
    idx += 8  # reserved
    idx += 2 + 2 + 2 + 2  # layer, alternate group, volume, reserved
    matrix_end = idx + 36
    if len(payload) < matrix_end:
        return None, None, None
    matrix = struct.unpack(">9i", payload[idx:matrix_end])
    a, b, _, c, d, _, _, _, _ = matrix
    scale = float(1 << 16)
    angle = math.degrees(math.atan2(b / scale, a / scale)) if scale else 0.0
    width = height = None
    if len(payload) >= matrix_end + 8:
        width_raw = struct.unpack(">I", payload[matrix_end:matrix_end + 4])[0]
        height_raw = struct.unpack(">I", payload[matrix_end + 4:matrix_end + 8])[0]
        width = width_raw / 65536.0
        height = height_raw / 65536.0
    return angle, width, height
def _iter_boxes(fh, start: int, end: Optional[int]):
    fh.seek(start)
    while True:
        pos = fh.tell()
        if end is not None and pos >= end:
            break
        header = fh.read(8)
        if len(header) < 8:
            break
        size = int.from_bytes(header[:4], "big")
        box_type = header[4:].decode("latin-1")
        header_size = 8
        if size == 1:
            large_size_bytes = fh.read(8)
            if len(large_size_bytes) < 8:
                break
            size = int.from_bytes(large_size_bytes, "big")
            header_size = 16
        if size == 0:
            box_end = end
        else:
            if size < header_size:
                break
            box_end = pos + size
        yield box_type, pos, box_end, header_size
        if box_end is None:
            break
        fh.seek(box_end)
def _find_box(fh, path: Sequence[str], start: Optional[int] = None, end: Optional[int] = None):
    if start is not None:
        fh.seek(start)
    if not path:
        return None
    name = path[0]
    for box_type, box_start, box_end, header in _iter_boxes(fh, fh.tell(), end):
        if box_type != name or box_end is None:
            continue
        if len(path) == 1:
            return box_start, box_end, header
        child_start = box_start + header
        child = _find_box(fh, path[1:], child_start, box_end)
        if child:
            return child
    return None