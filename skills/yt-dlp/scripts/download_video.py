#!/usr/bin/env python3
"""
Download a video URL as MP4 using yt-dlp.

The script prefers an existing yt-dlp executable, then an importable yt_dlp
module, and finally creates a per-user virtualenv cache for yt-dlp.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download one video URL as an MP4 file with yt-dlp.",
    )
    parser.add_argument("url", help="YouTube, Bilibili, or other yt-dlp supported URL")
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="Directory to save the video into; defaults to ~/Downloads/yt-dlp",
    )
    parser.add_argument(
        "-d",
        "--output-dir",
        dest="output_dir_flag",
        help="Directory to save the video into; overrides positional output_dir",
    )
    parser.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        help="Pass through yt-dlp --cookies-from-browser, e.g. chrome, firefox, safari",
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Allow playlist downloads. By default only the single URL item is downloaded.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Resolve metadata and format selection without downloading media.",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Upgrade the cached yt-dlp package before downloading.",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Fail instead of creating a cached virtualenv when yt-dlp is missing.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Append one raw argument to yt-dlp. Repeat for multiple arguments.",
    )
    return parser.parse_args()


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    printable = shlex.join(cmd)
    print(f"+ {printable}", flush=True)
    return subprocess.run(cmd, text=True, check=check)


def cache_root() -> Path:
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "agent-skills" / "yt-dlp"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "agent-skills" / "yt-dlp"
    return Path.home() / ".cache" / "agent-skills" / "yt-dlp"


def venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def importable_yt_dlp() -> bool:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False
    return True


def system_yt_dlp_cmd() -> list[str] | None:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    if importable_yt_dlp():
        return [sys.executable, "-m", "yt_dlp"]
    return None


def print_install_help() -> None:
    print(
        """
Could not prepare yt-dlp automatically.

Ubuntu / WSL2:
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip ffmpeg

macOS with Homebrew:
  brew install yt-dlp ffmpeg

macOS without Homebrew:
  Install Python 3, then rerun this script so it can create its yt-dlp virtualenv.
  Install ffmpeg from a trusted distribution source if MP4 merging is required.
""".strip(),
        file=sys.stderr,
    )


def ensure_cached_yt_dlp(upgrade: bool) -> list[str]:
    venv_dir = cache_root() / "venv"
    python = venv_python(venv_dir)

    try:
        if not python.exists():
            print(f"Creating yt-dlp virtualenv at {venv_dir}", flush=True)
            venv.EnvBuilder(with_pip=True).create(venv_dir)

        probe = subprocess.run(
            [str(python), "-m", "yt_dlp", "--version"],
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if upgrade or probe.returncode != 0:
            run([str(python), "-m", "pip", "install", "--upgrade", "yt-dlp[default]"])
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"yt-dlp setup failed: {exc}", file=sys.stderr)
        print_install_help()
        sys.exit(2)

    return [str(python), "-m", "yt_dlp"]


def ensure_yt_dlp(args: argparse.Namespace) -> list[str]:
    if args.upgrade:
        return ensure_cached_yt_dlp(upgrade=True)

    existing = system_yt_dlp_cmd()
    if existing:
        return existing
    if args.no_install:
        print("yt-dlp is not installed and --no-install was specified.", file=sys.stderr)
        print_install_help()
        sys.exit(2)
    return ensure_cached_yt_dlp(args.upgrade)


def output_dir(args: argparse.Namespace) -> Path:
    raw_dir = args.output_dir_flag or args.output_dir or "~/Downloads/yt-dlp"
    directory = Path(raw_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def yt_dlp_download_cmd(yt_dlp: list[str], args: argparse.Namespace, directory: Path) -> list[str]:
    ffmpeg_available = shutil.which("ffmpeg") is not None
    if ffmpeg_available:
        fmt = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
    else:
        fmt = "b[ext=mp4]/best[ext=mp4]"
        print(
            "ffmpeg was not found. Downloading the best single-file MP4 available; "
            "install ffmpeg if this fails or the quality is too low.",
            file=sys.stderr,
        )

    cmd = [
        *yt_dlp,
        "--newline",
        "--paths",
        str(directory),
        "--output",
        "%(title).200B [%(id)s].%(ext)s",
        "--format",
        fmt,
    ]

    if ffmpeg_available:
        cmd.extend(["--merge-output-format", "mp4", "--remux-video", "mp4"])

    if not args.playlist:
        cmd.append("--no-playlist")

    if args.simulate:
        cmd.append("--simulate")

    if args.cookies_from_browser:
        cmd.extend(["--cookies-from-browser", args.cookies_from_browser])

    cmd.extend(args.extra_arg)
    cmd.append(args.url)
    return cmd


def main() -> int:
    args = parse_args()
    directory = output_dir(args)
    yt_dlp = ensure_yt_dlp(args)

    version = subprocess.run(
        [*yt_dlp, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if version.stdout.strip():
        print(f"yt-dlp version: {version.stdout.strip()}")

    print(f"Saving video into: {directory}")
    cmd = yt_dlp_download_cmd(yt_dlp, args, directory)
    try:
        run(cmd)
    except subprocess.CalledProcessError as exc:
        print(f"Download failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
