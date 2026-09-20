"""
Application entry point and startup lifecycle management.
Targets: Python 3.12.10
"""

import logging
import shutil
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from handlers import (
    button_callback_handler,
    cancel_handler,
    help_handler,
    photo_message_handler,
    start_handler,
    text_message_handler,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=logging.INFO,
)
# Mute httpx logging so bot tokens are never printed to stdout/logs
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


def main() -> None:
    """Builds and starts the Telegram bot."""
    cleanup_stale_temp_files()

    logger.info("Initializing bot application...")
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

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
