"""Access control decorator and user validation."""

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED_USER_IDS

logger = logging.getLogger(__name__)


def is_user_allowed(user_id: int | None) -> bool:
    """Check if the given Telegram user ID is present in the whitelist."""
    return user_id is not None and user_id in ALLOWED_USER_IDS


def restricted(func):
    """
    Decorator that rejects any user not listed in ALLOWED_USER_IDS.
    Rejects immediately at handler invocation and logs the attempt.
    """

    @wraps(func)
    async def wrapped(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        user = update.effective_user
        user_id = user.id if user else None
        username = user.username if user else "Unknown"

        if not is_user_allowed(user_id):
            logger.warning(
                "UNAUTHORIZED ACCESS REJECTED: user_id=%s, username=@%s, handler=%s",
                user_id,
                username,
                func.__name__,
            )
            if update.message:
                await update.message.reply_text(
                    "⛔ You are not authorized to use this bot."
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "⛔ Unauthorized access.", show_alert=True
                )
            return

        return await func(update, context, *args, **kwargs)

    return wrapped
