"""Notifier module for Skill Forge.

Sends Telegram notifications for each significant lifecycle event in the
skill-learning pipeline.
"""

from __future__ import annotations

import asyncio
import html
import os
from typing import Any, Dict

from loguru import logger
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode


# HTML-formatted templates — much simpler than MarkdownV2 since only
# <, >, & in dynamic values need escaping.
NOTIF_RESEARCH_START = "🔍 <b>Skill Forge</b> — Researching: <code>{domain}</code>"
NOTIF_RESEARCH_DONE = "📖 Research complete — {source_count} sources for <code>{domain}</code>"
NOTIF_WRITING = "✍️ Writing skill: <code>{skill_name}</code>"
NOTIF_VALIDATING = "🧪 Validating <code>{skill_name}</code> in sandbox..."
NOTIF_VALIDATED_OK = (
    "✅ <b>Skill learned!</b>\n"
    "<code>{skill_name}</code>\n"
    "<i>{description}</i>\n\n"
    "{steps_tested} steps validated"
)
NOTIF_VALIDATED_FAIL = (
    "⚠️ Validation failed for <code>{skill_name}</code>\n"
    "Retrying... (attempt {attempt}/3)"
)
NOTIF_SAVED = "📚 Saved: <code>{skill_name}</code>\n🌐 <a href=\"{dashboard_url}\">View on dashboard</a>"

NOTIF_DAILY_SUMMARY = (
    "📊 <b>Skill Forge — Daily Report</b>\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "✅ Learned today: {learned}\n"
    "{learned_list}\n"
    "❌ Failed: {failed}\n"
    "{failed_list}\n"
    "📈 Total skills: {total}\n"
    "🌐 {dashboard_url}\n"
    "━━━━━━━━━━━━━━━━━━━"
)

_EVENT_TEMPLATES: Dict[str, str] = {
    "research_start": NOTIF_RESEARCH_START,
    "research_done": NOTIF_RESEARCH_DONE,
    "writing": NOTIF_WRITING,
    "validating": NOTIF_VALIDATING,
    "validated_ok": NOTIF_VALIDATED_OK,
    "validated_fail": NOTIF_VALIDATED_FAIL,
    "saved": NOTIF_SAVED,
}


def _get_telegram_credentials() -> tuple[str | None, str | None]:
    # Load .env once so running `python -m forge.notifier` from the project root
    # picks up TELEGRAM_* values without extra shell configuration.
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    return token, chat_id


def _escape_html(text: str) -> str:
    """Escape text for safe embedding in Telegram HTML messages."""
    return html.escape(str(text))


async def _send_telegram(text: str) -> None:
    """Send a Telegram message asynchronously using HTML parse mode, with plain-text fallback."""
    token, chat_id = _get_telegram_credentials()
    if not token or not chat_id:
        logger.warning(
            "Telegram credentials missing; would have sent notification: {text}",
            text=text,
        )
        return

    bot = Bot(token=token)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        logger.info("Sent Telegram notification (HTML).")
        return
    except Exception:
        logger.exception(
            "Failed to send Telegram message with HTML, falling back to plain text."
        )

    try:
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info("Sent Telegram notification as plain text.")
    except Exception:
        logger.exception("Failed to send Telegram message as plain text.")


def _build_message(event: str, **kwargs: Any) -> str:
    """Build a notification message from the event name and keyword arguments."""
    template = _EVENT_TEMPLATES.get(event)
    if not template:
        custom_message = kwargs.get("message")
        if custom_message:
            return _escape_html(str(custom_message))
        return f"Skill Forge event: {_escape_html(event)}"

    # Escape all interpolated values for HTML.
    escaped_kwargs: Dict[str, Any] = {
        key: _escape_html(value) for key, value in kwargs.items()
    }

    try:
        return template.format(**escaped_kwargs)
    except KeyError as exc:
        logger.error(
            "Missing format argument {exc} for notification event '{event}'. "
            "Sending raw template without interpolation.",
            exc=exc,
            event=event,
        )
        return template


def notify(event: str, **kwargs: Any) -> None:
    """Format and send a notification for the given event.

    This is a synchronous convenience wrapper around the async Telegram
    client, making it easy to call from the rest of the agent code.
    """
    message = _build_message(event, **kwargs)
    try:
        asyncio.run(_send_telegram(message))
    except RuntimeError:
        # If already in an event loop, schedule the coroutine instead of running it.
        logger.warning(
            "Event loop already running; scheduling Telegram notification coroutine."
        )
        asyncio.create_task(_send_telegram(message))


def send_daily_summary(stats: Dict[str, Any]) -> None:
    """Send the daily summary report based on aggregated statistics.

    Expected keys in `stats`:
    - learned: int
    - failed: int
    - total: int
    - learned_list: str (multi-line bullet list, already formatted)
    - failed_list: str (multi-line bullet list, already formatted)
    - dashboard_url: str
    """
    learned = stats.get("learned", 0)
    failed = stats.get("failed", 0)
    total = stats.get("total", 0)
    learned_list = stats.get("learned_list", "")
    failed_list = stats.get("failed_list", "")
    dashboard_url = stats.get("dashboard_url", "")

    message = NOTIF_DAILY_SUMMARY.format(
        learned=_escape_html(str(learned)),
        learned_list=_escape_html(str(learned_list)),
        failed=_escape_html(str(failed)),
        failed_list=_escape_html(str(failed_list)),
        total=_escape_html(str(total)),
        dashboard_url=_escape_html(str(dashboard_url)),
    )

    try:
        asyncio.run(_send_telegram(message))
    except RuntimeError:
        logger.warning(
            "Event loop already running; scheduling daily summary notification coroutine."
        )
        asyncio.create_task(_send_telegram(message))


if __name__ == "__main__":
    test_domain = "notifier-test"
    logger.info("Sending Skill Forge notifier test message for domain: {d}", d=test_domain)
    notify("research_start", domain=test_domain)

