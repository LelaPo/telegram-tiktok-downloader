"""YouTube audio extraction and metadata fetching via yt-dlp."""

import io
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
import yt_dlp

import config

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Custom exception raised when yt-dlp or post-processing fails."""

    pass


@dataclass
class MediaResult:
    mp3_path: Path
    title: str
    artist: str
    cover_path: Path | None
    thumb_path: Path | None


def process_image(img: Image.Image, session_dir: Path) -> tuple[Path, Path]:
    """
    Crops image to a 1:1 square and creates:
    1. cover.jpg (800x800) for ID3 APIC tag embedding.
    2. thumb.jpg (320x320, <200KB) strictly for Telegram's message preview.
    """
    img = img.convert("RGB")
    width, height = img.size
    min_dim = min(width, height)

    # Center crop to 1:1 square
    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
    img_square = img.crop((left, top, left + min_dim, top + min_dim))

    # 1. Full cover for MP3 ID3 tag (800x800 max)
    cover_img = img_square.copy()
    if min_dim > 800:
        cover_img = cover_img.resize((800, 800), Image.Resampling.LANCZOS)
    cover_path = session_dir / "cover.jpg"
    cover_img.save(cover_path, format="JPEG", quality=90)

    # 2. Telegram chat preview thumbnail (strictly <= 320x320)
    thumb_img = img_square.resize((320, 320), Image.Resampling.LANCZOS)
    thumb_path = session_dir / "thumb.jpg"
    thumb_img.save(thumb_path, format="JPEG", quality=85)

    return cover_path, thumb_path


def download_youtube_audio(url: str, session_dir: Path) -> MediaResult:
    """
    Downloads audio from YouTube URL, converts to MP3 (320kbps CBR) via FFmpeg,
    extracts metadata, and generates covers.
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(session_dir / "%(id)s.%(ext)s")

    ydl_opts = {
        # Select pure lightweight audio streams (m4a/opus)
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": out_tmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Multi-threaded chunk downloading
        "concurrent_fragment_downloads": 4,
        "buffersize": 1024 * 1024,
        # Client rotation to bypass 403 Forbidden without disabling nsig throttling solver
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if config.YOUTUBE_COOKIES_FILE and config.YOUTUBE_COOKIES_FILE.exists():
        ydl_opts["cookiefile"] = str(config.YOUTUBE_COOKIES_FILE)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Fetching info and downloading audio: %s", url)
            info = ydl.extract_info(url, download=True)
            if not info:
                raise DownloadError("Failed to extract video information.")

            video_id = info.get("id", "audio")
            raw_title = info.get("track") or info.get("title") or "Unknown Title"
            raw_artist = (
                info.get("artist")
                or info.get("creator")
                or info.get("uploader")
                or info.get("channel")
                or "Unknown Artist"
            )
            thumbnail_url = info.get("thumbnail")

    except Exception as exc:
        logger.exception("yt-dlp download failed for URL: %s", url)
        raise DownloadError(f"Download failed: {exc}") from exc

    mp3_path = session_dir / f"{video_id}.mp3"
    if not mp3_path.exists():
        mp3_files = list(session_dir.glob("*.mp3"))
        if not mp3_files:
            raise DownloadError("FFmpeg audio conversion failed: No MP3 file produced.")
        mp3_path = mp3_files[0]

    cover_path, thumb_path = None, None
    if thumbnail_url:
        try:
            req = urllib.request.Request(
                thumbnail_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                thumb_bytes = resp.read()

            raw_image = Image.open(io.BytesIO(thumb_bytes))
            cover_path, thumb_path = process_image(raw_image, session_dir)
            logger.info(
                "Generated cover (%s) and TG thumbnail (%s)", cover_path, thumb_path
            )
        except Exception as exc:
            logger.warning(
                "Could not process thumbnail from %s: %s", thumbnail_url, exc
            )

    return MediaResult(
        mp3_path=mp3_path,
        title=raw_title,
        artist=raw_artist,
        cover_path=cover_path,
        thumb_path=thumb_path,
    )
