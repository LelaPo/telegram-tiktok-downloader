"""ID3 metadata manipulation using Mutagen."""

import logging
from pathlib import Path
from mutagen.id3 import ID3, APIC, TIT2, TPE1, ID3NoHeaderError

logger = logging.getLogger(__name__)


def embed_tags(
    mp3_path: Path,
    title: str | None = None,
    artist: str | None = None,
    cover_path: Path | None = None,
) -> None:
    """Embed ID3v2.3 tags (TIT2, TPE1, APIC) into MP3."""
    if not mp3_path.exists():
        raise FileNotFoundError(f"Target MP3 does not exist: {mp3_path}")

    try:
        tags = ID3(str(mp3_path))
    except ID3NoHeaderError:
        tags = ID3()

    if title is not None:
        tags.delall("TIT2")
        tags.add(TIT2(encoding=3, text=title.strip()))

    if artist is not None:
        tags.delall("TPE1")
        tags.add(TPE1(encoding=3, text=artist.strip()))

    if cover_path is not None and cover_path.exists():
        tags.delall("APIC")
        with open(cover_path, "rb") as img_file:
            cover_data = img_file.read()

        tags.add(
            APIC(
                encoding=0,  # ISO-8859-1 for widest player compatibility
                mime="image/jpeg",
                type=3,  # Front cover
                desc="",
                data=cover_data,
            )
        )

    tags.save(str(mp3_path), v2_version=3)
    logger.info(
        "Saved ID3 tags for %s (Title='%s', Artist='%s')", mp3_path.name, title, artist
    )
