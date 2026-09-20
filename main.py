"""
Application entry point and startup lifecycle management.
Targets: Python 3.12.10
"""

import logging
import shutil
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import config
from handlers import (
    button_callback_handler,
    cancel_handler,
    help_handler,
    photo_message_handler,
    start_handler,
    text_message_handler,
)

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=logging.INFO,
)
# Suppress httpx request logging to prevent token leaks
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("yt_audio_bot")


def cleanup_stale_temp_files():
    """Purges any lingering session directories from previous unclean shutdowns."""
    if config.DOWNLOAD_DIR.exists():
        for item in config.DOWNLOAD_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        logger.info(
            "Startup check: Cleaned stale directories in %s", config.DOWNLOAD_DIR
        )


async def global_error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Log exceptions caused by updates without terminating the bot."""
    logger.error("Exception while handling update %s:", update, exc_info=context.error)


def main() -> None:
    """Builds and starts the Telegram bot."""
    cleanup_stale_temp_files()

    logger.info("Initializing bot application...")
    builder = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN)

    # Configure timeouts and optional SOCKS5/HTTP proxy
    if config.SOCKS5_PROXY:
        logger.info(
            "Enabling SOCKS5/HTTP proxy for Telegram API: %s", config.SOCKS5_PROXY
        )
        request = HTTPXRequest(
            proxy=config.SOCKS5_PROXY,
            connect_timeout=30.0,
            read_timeout=60.0,
            write_timeout=60.0,
            media_write_timeout=180.0,
        )
        get_updates_request = HTTPXRequest(
            proxy=config.SOCKS5_PROXY,
            connect_timeout=30.0,
            read_timeout=60.0,
            write_timeout=60.0,
        )
        builder = builder.request(request).get_updates_request(get_updates_request)
    else:
        # Standard timeouts with generous buffer for MP3 uploads
        request = HTTPXRequest(
            connect_timeout=20.0,
            read_timeout=40.0,
            write_timeout=40.0,
            media_write_timeout=180.0,
        )
        builder = builder.request(request)

    app = builder.build()

    # Register error handler
    app.add_error_handler(global_error_handler)

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))

    # Inline Editor Button Callbacks
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler)
    )

    logger.info(
        "Bot is operational. Allowed user count: %d. Waiting for updates...",
        len(config.ALLOWED_USER_IDS),
    )
    app.run_polling()


if __name__ == "__main__":
    main()
