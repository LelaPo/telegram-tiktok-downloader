"""YouTube audio extraction and metadata fetching via yt-dlp."""

import io
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
import yt_dlp

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


def download_youtube_audio(url: str, session_dir: Path) -> MediaResult:
    """
    Downloads audio from YouTube URL, converts to MP3 (320kbps CBR) via FFmpeg,
    extracts metadata, and converts the thumbnail to a standard JPEG cover image.
    Executed synchronously inside an asyncio thread executor.
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(session_dir / "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
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
    }

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
        # Fallback search if yt-dlp sanitized ID unexpectedly
        mp3_files = list(session_dir.glob("*.mp3"))
        if not mp3_files:
            raise DownloadError("FFmpeg audio conversion failed: No MP3 file produced.")
        mp3_path = mp3_files[0]

    cover_path = None
    if thumbnail_url:
        try:
            req = urllib.request.Request(
                thumbnail_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                thumb_bytes = resp.read()

            cover_path = session_dir / "cover.jpg"
            img = Image.open(io.BytesIO(thumb_bytes)).convert("RGB")
            img.save(cover_path, format="JPEG", quality=95)
            logger.info("Saved and converted thumbnail to JPEG: %s", cover_path)
        except Exception as exc:
            logger.warning(
                "Could not download/convert thumbnail from %s: %s", thumbnail_url, exc
            )
            cover_path = None

    return MediaResult(
        mp3_path=mp3_path,
        title=raw_title,
        artist=raw_artist,
        cover_path=cover_path,
    )
