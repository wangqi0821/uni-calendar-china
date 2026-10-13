"""Build the frozen monthly calendar archive without changing source data or media.

Run from the project root (Pillow is required)::

    python tools/build_archive.py --media-root /path/to/original/repository

The media root must contain the original media/ (and, if used, media.plus/)
directories. No downloads, image conversion, caption repair, or date conversion
are performed. Existing hashed month files remain available for cached clients.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATE = "2020-06-10"
CDN_PREFIX = "/gh/wangqi0821/uni-calendar-china@main/"
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def relative_media_path(source: str) -> str:
    """Accept only this archive's known CDN URLs and produce a safe local path."""
    if not isinstance(source, str):
        raise ValueError("A media source must be a string")
    url = urlsplit(source)
    if (
        url.scheme != "https"
        or url.netloc != "cdn.jsdelivr.net"
        or url.query
        or url.fragment
        or not url.path.startswith(CDN_PREFIX)
    ):
        raise ValueError(f"Unexpected media URL: {source!r}")
    relative = unquote(url.path[len(CDN_PREFIX):])
    parts = relative.split("/")
    if (
        len(parts) != 2
        or parts[0] not in {"media", "media.plus"}
        or parts[1] in {"", ".", ".."}
        or any(character in relative for character in "\\:?#%")
        or any(ord(character) < 32 for character in relative)
        or PurePosixPath(relative).is_absolute()
    ):
        raise ValueError(f"Unsafe media path: {relative!r}")
    return relative


def media_metadata(relative: str, media_root: Path) -> dict:
    original = (media_root / relative).resolve()
    if not original.is_relative_to(media_root) or not original.is_file():
        raise ValueError(f"Media file missing or outside media root: {relative}")
    extension = original.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        with Image.open(original) as image:
            width, height = image.size
            # Browsers honor JPEG EXIF orientation when displaying an image.
            if image.getexif().get(274, 1) in {5, 6, 7, 8}:
                width, height = height, width
        if width < 1 or height < 1:
            raise ValueError(f"Invalid image dimensions: {relative}")
        return {"src": relative, "type": "image", "width": width, "height": height}
    if extension in VIDEO_EXTENSIONS:
        return {"src": relative, "type": "video"}
    raise ValueError(f"Unsupported media type: {relative}")


def compile_archive(records: list, media_root: Path) -> tuple[dict, dict[str, bytes]]:
    """Validate and preserve every source record, text, date, and media reference."""
    if not isinstance(records, list) or not records:
        raise ValueError("The archive must contain a nonempty record list")
    media_root = media_root.resolve()
    days: dict[str, list] = defaultdict(list)
    metadata_cache: dict[str, dict] = {}
    media_count = 0

    for position, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Record {position} is not an object")
        day = record.get("日期")
        if not isinstance(day, str) or not DATE_PATTERN.fullmatch(day):
            raise ValueError(f"Record {position} has an invalid date: {day!r}")
        date.fromisoformat(day)  # Validate; retain the original date string.
        description, source = record.get("描述"), record.get("原链接")
        if not isinstance(description, str) or not isinstance(source, str):
            raise ValueError(f"Record {position} has a non-string description/source")
        references = record.get("Uni")
        if not isinstance(references, list):
            raise ValueError(f"Record {position} has a non-array media field")
        media = []
        for reference in references:
            relative = relative_media_path(reference)
            if relative not in metadata_cache:
                metadata_cache[relative] = media_metadata(relative, media_root)
            media.append(metadata_cache[relative].copy())
        media_count += len(media)
        days[day].append({"description": description, "source": source, "media": media})

    dates = sorted(days)
    months: dict[str, dict] = defaultdict(dict)
    for day in dates:
        months[day[:7]][day] = days[day]
    month_paths = {}
    files = {}
    for month, month_days in months.items():
        contents = json_bytes({"days": month_days})
        digest = hashlib.sha256(contents).hexdigest()[:12]
        relative = f"data/{month}.{digest}.json"
        month_paths[month] = relative
        files[relative] = contents
    if DEFAULT_DATE not in days:
        raise ValueError(f"The frozen archive is missing its default date: {DEFAULT_DATE}")
    # Embed the default month so the first visit needs only one data request.
    # Its independent content-addressed file remains unchanged for other clients.
    initial_month = DEFAULT_DATE[:7]
    index = {
        "version": 1,
        "firstDate": dates[0],
        "lastDate": dates[-1],
        "dates": dates,
        "months": month_paths,
        "postCount": len(records),
        "mediaCount": media_count,
        "initialMonth": {"month": initial_month, "days": months[initial_month]},
    }
    return index, files


def build_archive(source: Path, output_root: Path, media_root: Path) -> dict:
    records = json.loads(source.read_text(encoding="utf-8"))
    index, files = compile_archive(records, media_root)
    data_directory = output_root / "data"
    data_directory.mkdir(parents=True, exist_ok=True)
    for relative, contents in files.items():
        destination = output_root / relative
        if destination.exists():
            if destination.read_bytes() != contents:
                raise ValueError(f"Existing hashed archive has different content: {relative}")
        else:
            destination.write_bytes(contents)
    # Publish the stable index after every referenced month is available.
    temporary_index = data_directory / "index.json.tmp"
    temporary_index.write_bytes(json_bytes(index))
    temporary_index.replace(data_directory / "index.json")
    month_sizes = [len(contents) for contents in files.values()]
    return {
        "postCount": index["postCount"],
        "mediaCount": index["mediaCount"],
        "dateCount": len(index["dates"]),
        "monthCount": len(files),
        "firstDate": index["firstDate"],
        "lastDate": index["lastDate"],
        "sourceBytes": source.stat().st_size,
        "indexBytes": len(json_bytes(index)),
        "monthBytesTotal": sum(month_sizes),
        "smallestMonthBytes": min(month_sizes),
        "largestMonthBytes": max(month_sizes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT / "Uni.json")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--media-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    result = build_archive(args.source, args.output_root, args.media_root)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
