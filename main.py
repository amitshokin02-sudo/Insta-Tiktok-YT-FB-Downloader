import os
import base64
import threading
import logging
import uuid
from urllib.parse import urlparse

from flask import Flask
import telebot
from telebot import types
import yt_dlp


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("8925499985:AAHzGIwKCG_JviunyfMuIn0KT1Bll_PraF8")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

PORT = int(os.getenv("PORT", "10000"))

CHANNEL_USERNAME = "@BLACK_KNOWLEDGE_190"

# ============================================================
# SECURED LINKS
# Required Base64 strings
# ============================================================

YOUTUBE_B64 = (
    "aHR0cHM6Ly95b3V0dWJlLmNvbS9AYmxhY2trbm93bGVkZ2VfMTkwP3NpPTlFd2tNUEdiLWxIUnpaZHE="
)

SUPPORT_B64 = (
    "aHR0cHM6Ly90Lm1lL0JMQUNLX0tub3dsZWRnZV8xOTA="
)

YOUTUBE_LINK = base64.b64decode(YOUTUBE_B64).decode("utf-8")
SUPPORT_LINK = base64.b64decode(SUPPORT_B64).decode("utf-8")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# TELEGRAM BOT
# ============================================================

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)


# ============================================================
# FLASK KEEP-ALIVE SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "BLACK KNOWLEDGE BOT is running.", 200


@app.route("/health")
def health():
    return "OK", 200


def keep_alive():
    """
    Runs Flask in a separate thread so Telegram polling
    and the web server can run simultaneously.
    """
    app.run(
        host="0.0.0.0",
        port=PORT,
        threaded=True
    )


# ============================================================
# START MENU
# ============================================================

def start_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    subscribe_btn = types.InlineKeyboardButton(
        "📢 SUBSCRIBE CHANNEL",
        url=YOUTUBE_LINK
    )

    tutorials_btn = types.InlineKeyboardButton(
        "🎓 ALL TUTORIALS",
        url=YOUTUBE_LINK
    )

    contact_btn = types.InlineKeyboardButton(
        "👤 CONTACT OWNER",
        url=SUPPORT_LINK
    )

    keyboard.add(
        subscribe_btn,
        tutorials_btn,
        contact_btn
    )

    return keyboard


@bot.message_handler(commands=["start"])
def start_command(message):
    welcome_text = f"""
<b>👑 BLACK KNOWLEDGE 190</b>

━━━━━━━━━━━━━━━━━━━━
🔥 <b>PREMIUM VIDEO DOWNLOADER</b>
━━━━━━━━━━━━━━━━━━━━

Welcome to <b>{CHANNEL_USERNAME}</b> 🚀

Send me an Instagram Reel or Facebook video link and I'll
download it for you in high quality.

<b>Supported Platforms:</b>
• Instagram Reels
• Facebook Videos

⚡ Fast Processing
🎬 High Quality
🧹 Automatic File Cleanup

━━━━━━━━━━━━━━━━━━━━
<b>Send your video link below 👇</b>
━━━━━━━━━━━━━━━━━━━━
"""

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=start_keyboard()
    )


# ============================================================
# URL VALIDATION
# ============================================================

def is_supported_url(url):
    """
    Allows only Instagram and Facebook URLs.
    This prevents the bot from becoming a generic arbitrary
    URL downloader.
    """

    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        hostname = (parsed.hostname or "").lower()

        supported_domains = (
            "instagram.com",
            "www.instagram.com",
            "facebook.com",
            "www.facebook.com",
            "fb.watch",
            "m.facebook.com",
            "web.facebook.com"
        )

        return hostname in supported_domains or any(
            hostname.endswith("." + domain)
            for domain in (
                "instagram.com",
                "facebook.com"
            )
        )

    except Exception:
        return False


# ============================================================
# FILE DOWNLOAD
# ============================================================

def download_video(url):
    """
    Downloads a video using yt-dlp.

    Returns:
        filepath, title
    """

    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)

    unique_id = uuid.uuid4().hex

    output_template = os.path.join(
        download_dir,
        f"{unique_id}.%(ext)s"
    )

    ydl_opts = {
        "outtmpl": output_template,

        # Best video + audio where available.
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",

        "merge_output_format": "mp4",

        "noplaylist": True,

        # Better compatibility with social media.
        "quiet": True,
        "no_warnings": True,

        # Avoid huge unnecessary files when possible.
        "restrictfilenames": True,

        # Don't leave partial files.
        "overwrites": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        title = info.get("title") or "Downloaded Video"

        filepath = ydl.prepare_filename(info)

        # yt-dlp can change the final extension after merging.
        if not os.path.exists(filepath):
            base = os.path.splitext(filepath)[0]

            possible_files = [
                base + ".mp4",
                base + ".mkv",
                base + ".webm",
                base + ".mov"
            ]

            for file in possible_files:
                if os.path.exists(file):
                    filepath = file
                    break

        if not os.path.exists(filepath):
            raise FileNotFoundError(
                "Downloaded video file could not be located."
            )

    return filepath, title


# ============================================================
# MESSAGE HELPERS
# ============================================================

def edit_status(chat_id, message_id, text):
    try:
        bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning("Could not edit status message: %s", e)


# ============================================================
# VIDEO HANDLER
# ============================================================

@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_video_link(message):

    url = message.text.strip()

    if not is_supported_url(url):
        bot.reply_to(
            message,
            """
❌ <b>Invalid Link</b>

Please send a valid:
• Instagram Reel link
• Facebook Video link
            """
        )
        return

    # Initial response.
    status_message = bot.reply_to(
        message,
        "🔍 <b>Analyzing...</b>"
    )

    filepath = None

    try:

        # ----------------------------------------------------
        # ANALYZING
        # ----------------------------------------------------

        edit_status(
            message.chat.id,
            status_message.message_id,
            "🔍 <b>Analyzing...</b>\n\nChecking video information..."
        )

        # ----------------------------------------------------
        # DOWNLOADING
        # ----------------------------------------------------

        edit_status(
            message.chat.id,
            status_message.message_id,
            "⬇️ <b>Downloading (50%)...</b>\n\nPlease wait..."
        )

        filepath, title = download_video(url)

        # ----------------------------------------------------
        # UPLOADING
        # ----------------------------------------------------

        edit_status(
            message.chat.id,
            status_message.message_id,
            "⬆️ <b>Uploading (100%)...</b>\n\nAlmost done..."
        )

        caption = (
            "Downloaded Successfully! "
            "Power by: @BLACK_KNOWLEDGE_190"
        )

        # Send video.
        with open(filepath, "rb") as video_file:
            bot.send_video(
                message.chat.id,
                video_file,
                caption=caption,
                supports_streaming=True
            )

        # ----------------------------------------------------
        # DELETE IMMEDIATELY AFTER SEND
        # ----------------------------------------------------

        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            filepath = None

        # Remove progress message after successful upload.
        try:
            bot.delete_message(
                message.chat.id,
                status_message.message_id
            )
        except Exception:
            pass

    except Exception as e:

        logger.exception("Download error")

        # Cleanup even if download/upload fails.
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as cleanup_error:
                logger.error(
                    "Cleanup failed: %s",
                    cleanup_error
                )

        error_message = """
❌ <b>Download Failed</b>

Possible reasons:
• The video is private
• The link has expired
• Instagram/Facebook blocked the request
• The video requires login
• yt-dlp could not extract the video

Please try another public video link.
"""

        edit_status(
            message.chat.id,
            status_message.message_id,
            error_message
        )


# ============================================================
# ERROR HANDLER
# ============================================================

@bot.message_handler(
    func=lambda message: False
)
def unused_handler(message):
    pass


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    logger.info("Starting Flask keep-alive server...")

    flask_thread = threading.Thread(
        target=keep_alive,
        daemon=True
    )

    flask_thread.start()

    logger.info("BLACK KNOWLEDGE 190 Telegram Bot started.")

    # Prevent polling from stopping because of temporary
    # Telegram/network errors.
    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as e:
            logger.exception(
                "Telegram polling crashed. Restarting..."
            )
