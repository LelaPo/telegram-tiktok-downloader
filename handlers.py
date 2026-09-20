"""Telegram bot command, message, and inline button handlers."""

import asyncio
import io
import logging
import re
import shutil
import time
from pathlib import Path
from PIL import Image
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

import config
from auth import restricted
from downloader import download_youtube_audio, process_image, DownloadError
from tagger import embed_tags

logger = logging.getLogger(__name__)

YOUTUBE_URL_REGEX = re.compile(
    r"(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[a-zA-Z0-9_\-]+[^\s]*"
)


def get_editor_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Edit Title", callback_data="edit_title"),
                InlineKeyboardButton("👤 Edit Artist", callback_data="edit_artist"),
            ],
            [
                InlineKeyboardButton("🖼️ Edit Cover", callback_data="edit_cover"),
                InlineKeyboardButton("✅ Looks good", callback_data="done"),
            ],
        ]
    )


def cleanup_session(user_data: dict) -> None:
    session = user_data.pop("session", None)
    if session and "session_dir" in session:
        session_dir = Path(session["session_dir"])
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.info("Cleaned up session directory: %s", session_dir)
    user_data.pop("edit_state", None)


@restricted
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome! Send me any YouTube link to download it as an MP3 (320kbps) with full tags and cover art."
    )


@restricted
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *Usage Instructions*:\n"
        "1. Send a YouTube link.\n"
        "2. The bot extracts the audio and sets ID3 tags.\n"
        "3. Use the inline buttons below the audio message to adjust metadata.",
        parse_mode="Markdown",
    )


@restricted
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cleanup_session(context.user_data)
    await update.message.reply_text(
        "🧹 Active session cancelled and temporary files cleared."
    )


@restricted
async def text_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    text = update.message.text.strip()
    edit_state = context.user_data.get("edit_state")

    if edit_state in ("TITLE", "ARTIST"):
        session = context.user_data.get("session")
        if not session:
            context.user_data["edit_state"] = None
            await update.message.reply_text(
                "⚠️ No active session found. Please send a new link."
            )
            return

        mp3_path = Path(session["mp3_path"])
        cover_path = Path(session["cover_path"]) if session.get("cover_path") else None

        if edit_state == "TITLE":
            session["title"] = text
            embed_tags(
                mp3_path, title=text, artist=session["artist"], cover_path=cover_path
            )
            await update.message.reply_text(
                f"✅ Title updated to: *{text}*", parse_mode="Markdown"
            )
        elif edit_state == "ARTIST":
            session["artist"] = text
            embed_tags(
                mp3_path, title=session["title"], artist=text, cover_path=cover_path
            )
            await update.message.reply_text(
                f"✅ Artist updated to: *{text}*", parse_mode="Markdown"
            )

        context.user_data["edit_state"] = None
        await send_mp3_response(update, session)
        return

    match = YOUTUBE_URL_REGEX.search(text)
    if not match:
        await update.message.reply_text("⚠️ Please send a valid YouTube link.")
        return

    url = match.group(0)
    cleanup_session(context.user_data)

    status_msg = await update.message.reply_text(
        "⏳ Downloading audio and generating tags..."
    )
    user_id = update.effective_user.id
    session_dir = config.DOWNLOAD_DIR / f"user_{user_id}_{int(time.time())}"

    try:
        result = await asyncio.to_thread(download_youtube_audio, url, session_dir)

        embed_tags(
            mp3_path=result.mp3_path,
            title=result.title,
            artist=result.artist,
            cover_path=result.cover_path,
        )

        context.user_data["session"] = {
            "session_dir": str(session_dir),
            "mp3_path": str(result.mp3_path),
            "title": result.title,
            "artist": result.artist,
            "cover_path": str(result.cover_path) if result.cover_path else None,
            "thumb_path": str(result.thumb_path) if result.thumb_path else None,
        }

        await status_msg.delete()
        await send_mp3_response(update, context.user_data["session"])

    except DownloadError as err:
        logger.error("Download failure: %s", err)
        cleanup_session(context.user_data)
        await status_msg.edit_text(f"❌ Error: {err}")
    except Exception:
        logger.exception("Unexpected error processing %s", url)
        cleanup_session(context.user_data)
        await status_msg.edit_text("❌ An error occurred while processing the request.")


async def send_mp3_response(update: Update, session: dict) -> None:
    """Uploads the MP3 file with thumbnail and displays the editor keyboard."""
    mp3_path = Path(session["mp3_path"])
    thumb_path = Path(session["thumb_path"]) if session.get("thumb_path") else None

    with open(mp3_path, "rb") as audio_file:
        thumb_file = (
            open(thumb_path, "rb") if (thumb_path and thumb_path.exists()) else None
        )
        try:
            await update.message.reply_audio(
                audio=audio_file,
                title=session["title"],
                performer=session["artist"],
                thumbnail=thumb_file,
                caption=(
                    f"🎵 *{session['title']}*\n"
                    f"👤 *{session['artist']}*\n\n"
                    "Use buttons to adjust metadata or tap *Looks good* to finish."
                ),
                parse_mode="Markdown",
                reply_markup=get_editor_keyboard(),
            )
        finally:
            if thumb_file:
                thumb_file.close()


@restricted
async def photo_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles replacement cover art photo uploads."""
    if context.user_data.get("edit_state") != "COVER":
        await update.message.reply_text(
            "ℹ️ To change the cover art, tap 'Edit Cover' on the track message first."
        )
        return

    session = context.user_data.get("session")
    if not session:
        context.user_data["edit_state"] = None
        await update.message.reply_text(
            "⚠️ No active file session found. Please send a new link."
        )
        return

    session_dir = Path(session["session_dir"])
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()

    photo_bytes = io.BytesIO()
    await photo_file.download_to_memory(photo_bytes)
    photo_bytes.seek(0)

    raw_img = Image.open(photo_bytes)
    cover_path, thumb_path = process_image(raw_img, session_dir)

    session["cover_path"] = str(cover_path)
    session["thumb_path"] = str(thumb_path)
    mp3_path = Path(session["mp3_path"])

    embed_tags(
        mp3_path=mp3_path,
        title=session["title"],
        artist=session["artist"],
        cover_path=cover_path,
    )

    context.user_data["edit_state"] = None
    await update.message.reply_text("✅ Cover art updated successfully.")
    await send_mp3_response(update, session)


@restricted
async def button_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    action = query.data
    session = context.user_data.get("session")

    if action == "done":
        cleanup_session(context.user_data)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("✅ Track finalized! Temporary files removed.")
        return

    if not session:
        await query.message.reply_text(
            "⚠️ Session expired. Please send a new YouTube link."
        )
        return

    if action == "edit_title":
        context.user_data["edit_state"] = "TITLE"
        await query.message.reply_text(
            "✏️ Please send the new Title as a text message:"
        )
    elif action == "edit_artist":
        context.user_data["edit_state"] = "ARTIST"
        await query.message.reply_text(
            "👤 Please send the new Artist name as a text message:"
        )
    elif action == "edit_cover":
        context.user_data["edit_state"] = "COVER"
        await query.message.reply_text(
            "🖼️ Please send a photo to use as the new cover art:"
        )
