#!/usr/bin/env python3
"""
Prepare Blue Archive EX-skill timeline review artifacts.

The script downloads/reuses an MP4, creates UI scan sheets, detects paid-cost
drop windows, and writes a review.md for an agent to inspect visually.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


BASE_W = 1916
BASE_H = 1080
UI_RECT = (1130, 780, 760, 300)
COST_RECT = (1190, 990, 560, 70)
WIKIRU_CHARACTER_LIST = "https://bluearchive.wikiru.jp/?キャラクター一覧"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create review artifacts for extracting a Blue Archive EX-skill TL.",
    )
    parser.add_argument("input", help="YouTube/Bilibili URL or local MP4 path")
    parser.add_argument(
        "--download-dir",
        default="~/Downloads/yt-dlp",
        help="Directory where yt-dlp videos are stored; default: ~/Downloads/yt-dlp",
    )
    parser.add_argument(
        "--output-root",
        default="~/Downloads/tl-reader",
        help="Directory for generated review artifacts; default: ~/Downloads/tl-reader",
    )
    parser.add_argument(
        "--scan-fps",
        type=float,
        default=5.0,
        help="FPS for bottom-right UI scan sheets; default: 5",
    )
    parser.add_argument(
        "--detect-fps",
        type=float,
        default=30.0,
        help="FPS for cost-drop detection; default: 30",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Download even if a matching MP4 already exists.",
    )
    return parser.parse_args()


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"+ {shlex.join(cmd)}", flush=True)
    return subprocess.run(cmd, text=True, check=check)


def capture(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def is_url(value: str) -> bool:
    return bool(re.match(r"https?://", value))


def parse_media_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|/shorts/|youtu\.be/)([-_A-Za-z0-9]{11})",
        r"/(BV[0-9A-Za-z]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ytdlp_script() -> Path:
    return repo_root() / "skills" / "yt-dlp" / "scripts" / "download_video.py"


def matching_downloads(download_dir: Path, media_id: str | None) -> list[Path]:
    if not download_dir.exists():
        return []
    files = [path for path in download_dir.glob("*.mp4") if path.is_file()]
    if media_id:
        files = [path for path in files if f"[{media_id}]" in path.name]
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def ensure_video(input_value: str, download_dir: Path, force_download: bool) -> Path:
    if not is_url(input_value):
        path = Path(input_value).expanduser()
        if not path.exists():
            raise SystemExit(f"Input MP4 not found: {path}")
        return path.resolve()

    media_id = parse_media_id(input_value)
    if not force_download:
        matches = matching_downloads(download_dir, media_id)
        if matches:
            print(f"Reusing downloaded MP4: {matches[0]}")
            return matches[0].resolve()

    before = {path.resolve() for path in download_dir.glob("*.mp4")} if download_dir.exists() else set()
    script = ytdlp_script()
    if not script.exists():
        raise SystemExit(f"yt-dlp helper not found: {script}")
    run([sys.executable, str(script), input_value, str(download_dir)])

    matches = matching_downloads(download_dir, media_id)
    if matches:
        return matches[0].resolve()

    after = {path.resolve() for path in download_dir.glob("*.mp4")} if download_dir.exists() else set()
    new_files = sorted(after - before, key=lambda path: path.stat().st_mtime, reverse=True)
    if new_files:
        return new_files[0]
    raise SystemExit("Download finished, but no MP4 could be located.")


def ffprobe(video: Path) -> dict:
    raw = capture(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,width,height,r_frame_rate,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video),
        ],
    )
    data = json.loads(raw)
    video_stream = next(stream for stream in data["streams"] if stream.get("codec_type") == "video")
    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "duration": float(data["format"]["duration"]),
        "frame_rate": video_stream.get("r_frame_rate", ""),
    }


def scaled_rect(rect: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    sx = width / BASE_W
    sy = height / BASE_H
    return (
        max(0, round(x * sx)),
        max(0, round(y * sy)),
        max(1, round(w * sx)),
        max(1, round(h * sy)),
    )


def sanitize_name(name: str) -> str:
    value = re.sub(r"[^\w.\-一-龯ぁ-んァ-ンー（）()\[\] ]+", "_", name)
    value = re.sub(r"\s+", "_", value).strip("._")
    return value[:120] or "video"


def make_output_dir(video: Path, output_root: Path) -> Path:
    stem = sanitize_name(video.stem)
    output_dir = output_root / stem
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def drawtext_filter(label: str = "%{pts}") -> str:
    escaped = label.replace(":", "\\:")
    return (
        "drawtext="
        "fontcolor=yellow:fontsize=28:box=1:boxcolor=black@0.55:"
        f"x=10:y=10:text={escaped}"
    )


def make_scan_sheets(video: Path, info: dict, output_dir: Path, scan_fps: float) -> list[Path]:
    duration = info["duration"]
    width = info["width"]
    height = info["height"]
    x, y, w, h = scaled_rect(UI_RECT, width, height)
    frames_per_page = 40
    seconds_per_page = frames_per_page / scan_fps
    page_count = max(1, math.ceil(duration / seconds_per_page))
    outputs: list[Path] = []

    for page in range(page_count):
        start = page * seconds_per_page
        out = output_dir / f"scan_ui_{page + 1:03d}_{start:05.1f}s.jpg"
        vf = (
            f"fps={scan_fps},crop={w}:{h}:{x}:{y},"
            f"{drawtext_filter()},scale=570:-1,tile=4x10"
        )
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{seconds_per_page:.3f}",
                "-i",
                str(video),
                "-vf",
                vf,
                "-frames:v",
                "1",
                str(out),
            ],
        )
        outputs.append(out)

    full_out = output_dir / "scan_full_1fps.jpg"
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"fps=1,{drawtext_filter()},scale=479:-1,tile=4x10",
            "-frames:v",
            "1",
            str(full_out),
        ],
    )
    outputs.append(full_out)
    return outputs


def cost_mask_count(data: bytes, width: int, height: int) -> int:
    count = 0
    for y in range(5, height - 5):
        row = y * width * 3
        for x in range(round(width * 0.13), width - 5):
            off = row + x * 3
            r, g, b = data[off], data[off + 1], data[off + 2]
            if r < 110 and g > 90 and b > 110 and (b - r) > 40 and (g - r) > 20:
                count += 1
    return count


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def detect_cost_drops(video: Path, info: dict, detect_fps: float) -> list[dict]:
    width = info["width"]
    height = info["height"]
    x, y, w, h = scaled_rect(COST_RECT, width, height)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vf",
        f"crop={w}:{h}:{x}:{y},fps={detect_fps}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]
    print(f"+ {shlex.join(cmd)}", flush=True)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    assert process.stdout is not None
    frame_size = w * h * 3
    values: list[tuple[float, int]] = []
    index = 0
    while True:
        data = process.stdout.read(frame_size)
        if len(data) < frame_size:
            break
        values.append((index / detect_fps, cost_mask_count(data, w, h)))
        index += 1
    process.wait()

    smoothed: list[tuple[float, float]] = []
    for i, (time_sec, _count) in enumerate(values):
        window = [count for _time, count in values[max(0, i - 2) : min(len(values), i + 3)]]
        smoothed.append((time_sec, median(window)))

    raw: list[tuple[float, float, float, float]] = []
    lookback = max(1, round(0.35 * detect_fps))
    for i, (time_sec, current) in enumerate(smoothed):
        start = max(0, i - lookback)
        previous = max(count for _time, count in smoothed[start : i + 1])
        delta = previous - current
        if delta > 800:
            raw.append((time_sec, delta, previous, current))

    clusters: list[list[tuple[float, float, float, float]]] = []
    for item in raw:
        if not clusters or item[0] - clusters[-1][-1][0] > 0.45:
            clusters.append([item])
        else:
            clusters[-1].append(item)

    drops: list[dict] = []
    for index, cluster in enumerate(clusters, start=1):
        best = max(cluster, key=lambda item: item[1])
        start = max(0.0, cluster[0][0] - 0.65)
        end = min(info["duration"], cluster[-1][0] + 0.65)
        drops.append(
            {
                "index": index,
                "time": best[0],
                "start": start,
                "end": end,
                "delta": best[1],
                "before_area": best[2],
                "after_area": best[3],
            },
        )
    return drops


def make_candidate_sheets(video: Path, info: dict, output_dir: Path, drops: list[dict]) -> list[Path]:
    width = info["width"]
    height = info["height"]
    x, y, w, h = scaled_rect(UI_RECT, width, height)
    outputs: list[Path] = []
    for drop in drops:
        index = drop["index"]
        start = drop["start"]
        duration = max(0.5, drop["end"] - drop["start"])
        full_out = output_dir / f"candidate_{index:02d}_{drop['time']:.3f}s_full.jpg"
        ui_out = output_dir / f"candidate_{index:02d}_{drop['time']:.3f}s_ui.jpg"
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(video),
                "-vf",
                f"fps=6,{drawtext_filter()},scale=479:-1,tile=4x4",
                "-frames:v",
                "1",
                str(full_out),
            ],
        )
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(video),
                "-vf",
                f"fps=10,crop={w}:{h}:{x}:{y},{drawtext_filter()},scale=760:-1,tile=4x4",
                "-frames:v",
                "1",
                str(ui_out),
            ],
        )
        outputs.extend([full_out, ui_out])
    return outputs


def write_summary(video: Path, info: dict, output_dir: Path, scan_files: list[Path], drops: list[dict]) -> Path:
    tsv = output_dir / "candidate_drops.tsv"
    with tsv.open("w", encoding="utf-8") as file:
        file.write("index\tvideo_time\twindow_start\twindow_end\tdelta\tbefore_area\tafter_area\n")
        for drop in drops:
            file.write(
                f"{drop['index']}\t{drop['time']:.3f}\t{drop['start']:.3f}\t{drop['end']:.3f}\t"
                f"{drop['delta']:.0f}\t{drop['before_area']:.0f}\t{drop['after_area']:.0f}\n",
            )

    review = output_dir / "review.md"
    lines = [
        "# tl-reader review",
        "",
        f"Video: `{video}`",
        f"Resolution: {info['width']}x{info['height']}",
        f"Duration: {info['duration']:.3f}s",
        "",
        "## Scan Sheets",
        "",
    ]
    lines.extend(f"- `{path.name}`" for path in scan_files)
    lines.extend(
        [
            "",
            "## Candidate Cost Drops",
            "",
            f"Detector output: `{tsv.name}`",
            "",
        ],
    )
    for drop in drops:
        lines.append(
            f"- Candidate {drop['index']:02d}: video {drop['time']:.3f}s "
            f"(window {drop['start']:.3f}-{drop['end']:.3f}s), "
            f"open `candidate_{drop['index']:02d}_{drop['time']:.3f}s_full.jpg` and "
            f"`candidate_{drop['index']:02d}_{drop['time']:.3f}s_ui.jpg`.",
        )
    lines.extend(
        [
            "",
            "## Manual Reading Rules",
            "",
            "- Use the last greyed/selected-card frame before the cost drop.",
            "- Read the game timer at the top right, not the video timestamp label.",
            "- Read the current cost from the blue cost boxes, including one decimal from partial fill.",
            "- Confirm the selected card disappears or changes after the drop.",
            "- A candidate window may include more than one EX execution; inspect the whole sheet.",
            "- Yellow overlay values are relative seconds within that sheet/window, not TL timestamps.",
            "- Include a positive-cost activation even if the following frames enter orange/negative special-cost mode.",
            "- Ignore later 0-cost follow-up cards and activations without a cost decrease for the first version.",
            f"- For ambiguous portraits, compare against Wikiru: {WIKIRU_CHARACTER_LIST}",
            "",
            "## Output Format",
            "",
            "```text",
            "7.7 (3:43.500) 食蜂操祈",
            "```",
            "",
        ],
    )
    review.write_text("\n".join(lines), encoding="utf-8")
    return review


def main() -> int:
    args = parse_args()
    download_dir = Path(args.download_dir).expanduser()
    output_root = Path(args.output_root).expanduser()

    video = ensure_video(args.input, download_dir, args.force_download)
    info = ffprobe(video)
    output_dir = make_output_dir(video, output_root)

    scan_files = make_scan_sheets(video, info, output_dir, args.scan_fps)
    drops = detect_cost_drops(video, info, args.detect_fps)
    make_candidate_sheets(video, info, output_dir, drops)
    review = write_summary(video, info, output_dir, scan_files, drops)

    print()
    print(f"Video: {video}")
    print(f"Review directory: {output_dir}")
    print(f"Open: {review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
