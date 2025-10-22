"""Batch normalisation tool for worker videos.
This script re-encodes selfie videos so their rotation metadata is cleared and
stored under ``static/uploads/worker_videos``. Existing records in
``data/approved.json`` are updated to point at the normalised files.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path
from services.video_utils import normalize_video_file
def normalise_all(static_dir: Path, approved_path: Path, overwrite: bool = False) -> int:
    """Normalise every video referenced in *approved_path*.
    Returns the number of worker records that were updated. When *overwrite* is
    False and the destination file already exists the record is skipped.
    """
    if not approved_path.exists():
        print(f"Approved file not found: {approved_path}", file=sys.stderr)
        return 0
    uploads_dir = static_dir / "uploads" / "worker_videos"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    workers = json.loads(approved_path.read_text(encoding="utf-8"))
    if not isinstance(workers, list):
        print("Approved file does not contain a list.", file=sys.stderr)
        return 0
    updated = 0
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        video_rel = (worker.get("video_local") or "").strip()
        if not video_rel:
            continue
        src = (static_dir / video_rel).resolve()
        try:
            src.relative_to(static_dir)
        except ValueError:
            print(f"Skipping video outside static directory: {video_rel}")
            continue
        if not src.exists():
            print(f"Video file not found: {src}")
            continue
        if src.parent == uploads_dir and src.suffix.lower() == ".mp4" and not overwrite:
            continue
        dest_name = f"{uuid.uuid4().hex}.mp4"
        dest = uploads_dir / dest_name
        try:
            ok = normalize_video_file(src, dest)
        except FileNotFoundError:
            print("ffmpeg/ffprobe not found – cannot normalise videos.", file=sys.stderr)
            return updated
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"Normalisation failed for {src}: {exc}", file=sys.stderr)
            ok = False
        if not ok:
            try:
                shutil.copy2(src, dest)
                ok = dest.exists()
            except Exception as copy_exc:  # pragma: no cover - defensive logging
                print(f"Fallback copy failed for {src}: {copy_exc}", file=sys.stderr)
                continue
        rel_path = dest.relative_to(static_dir)
        worker["video_local"] = str(rel_path).replace("\\", "/")
        for stale_key in (
            "card_video_rotation",
            "card_video_aspect_landscape",
            "card_video_aspect_portrait",
            "card_video_aspect_ratio",
        ):
            worker.pop(stale_key, None)
        updated += 1
    if updated:
        backup_path = approved_path.with_suffix(".bak")
        if not backup_path.exists():
            shutil.copy2(approved_path, backup_path)
        approved_path.write_text(
            json.dumps(workers, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return updated
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalise worker video files")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="re-encode videos even if they already live under uploads/worker_videos",
    )
    args = parser.parse_args(argv)
    base_dir = Path(__file__).resolve().parents[1]
    static_dir = base_dir / "static"
    approved_path = base_dir / "data" / "approved.json"
    updated = normalise_all(static_dir, approved_path, overwrite=args.overwrite)
    if updated:
        print(f"Updated {updated} worker video{'s' if updated != 1 else ''}.")
    else:
        print("No worker videos required normalisation.")
    return 0
if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())