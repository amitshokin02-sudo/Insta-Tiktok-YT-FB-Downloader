import os
import re
import uuid
import base64
import threading
import logging

import telebot
from telebot import types
from flask import Flask
from yt_dlp import YoutubeDL


# =========================================================
# CONFIGURATION
# =========================================================

# Render Environment Variable:
# BOT_TOKEN = your Telegram bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("8925499985:AAHzGIwKCG_JviunyfMuIn0KT1Bll_PraF8")

BOT_USERNAME = "@Insta_Tiktok_YT_FB_Downloader"

# Base64 encoded links - kept exactly as requested
YOUTUBE_B64 = (
    "aHR0cHM6Ly95b3V0dWJlLmNvbS9AYmxhY2trbm93bGVkZ2VfMTkwP3NpPTlFd2tNUEdiLWxIUnpaZHE="
)

SUPPORT_B64 = (
    "aHR0cHM6Ly90Lm1lL0JMQUNLX0tub3dsZWRnZV8xOTA="
)

YOUTUBE_LINK = base64.b64decode(YOUTUBE_B64).decode("utf-8")
SUPPORT_LINK = base64.b64decode(SUPPORT_B64).decode("utf-8")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


# =========================================================
# FLASK KEEP-ALIVE SERVER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Telegram Downloader Bot is running!"


@app.route("/health")
def health():
    return "OK"


def keep_alive():
    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False,
        use_reloader=False
    )


# =========================================================
# START COMMAND
# =========================================================

@bot.message_handler(commands=["start"])
def start_command(message):

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    subscribe_btn = types.InlineKeyboardButton(
        "📢 SUBSCRIBE CHANNEL",
        url=YOUTUBE_LINK
    )

    tutorials_btn = types.InlineKeyboardButton(
        "📚 ALL TUTORIALS",
        url=SUPPORT_LINK
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

    welcome_text = f"""
<b>🔥 Welcome to {BOT_USERNAME}</b>

🚀 <b>Premium Video Downloader</b>

Download videos easily from:

• Instagram Reels
• Facebook Videos
• YouTube Videos

<b>⚡ Fast • Simple • High Quality</b>

👇 Choose an option below or simply send me a video link.
"""

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=keyboard
    )


# =========================================================
# HELP COMMAND
# =========================================================

@bot.message_handler(commands=["help"])
def help_command(message):

    bot.send_message(
        message.chat.id,
        f"""
<b>📥 How to Download</b>

1️⃣ Copy an Instagram, Facebook or YouTube video link.

2️⃣ Send the link here.

3️⃣ Wait while I download your video.

4️⃣ Your video will be uploaded automatically.

<b>Supported:</b>
• Instagram
• Facebook
• YouTube

<b>Bot:</b> {BOT_USERNAME}
"""
    )


# =========================================================
# URL VALIDATION
# =========================================================

def is_supported_url(url):

    supported_domains = [
        "youtube.com",
        "youtu.be",
        "instagram.com",
        "facebook.com",
        "fb.watch",
        "m.facebook.com",
        "www.facebook.com",
        "www.instagram.com"
    ]

    url_lower = url.lower()

    return any(
        domain in url_lower
        for domain in supported_domains
    )


# =========================================================
# EXTRACT URL FROM MESSAGE
# =========================================================

def extract_url(text):

    url_pattern = r"https?://[^\s]+"

    match = re.search(url_pattern, text)

    if match:
        return match.group(0).rstrip(".,!?)]}")

    return None


# =========================================================
# DOWNLOAD VIDEO
# =========================================================

def download_video(url):

    file_id = uuid.uuid4().hex

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{file_id}.%(ext)s"
    )

    ydl_opts = {
        "outtmpl": output_template,

        # Try MP4-compatible format first.
        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/best"
        ),

        "merge_output_format": "mp4",

        "noplaylist": True,

        "quiet": True,
        "no_warnings": True,

        "restrictfilenames": True,

        # Useful for sites that require browser-like headers.
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            )
        }
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            url,
            download=True
        )

        downloaded_file = ydl.prepare_filename(info)

        # yt-dlp may merge the file into mp4.
        if not os.path.exists(downloaded_file):
            possible_mp4 = os.path.splitext(
                downloaded_file
            )[0] + ".mp4"

            if os.path.exists(possible_mp4):
                downloaded_file = possible_mp4

    if not os.path.exists(downloaded_file):
        raise FileNotFoundError(
            "Downloaded file could not be found."
        )

    return downloaded_file


# =========================================================
# VIDEO LINK HANDLER
# =========================================================

@bot.message_handler(
    func=lambda message: (
        message.text is not None
        and not message.text.startswith("/")
    )
)
def handle_video_link(message):

    url = extract_url(message.text)

    if not url:
        bot.reply_to(
            message,
            "❌ Please send a valid video URL."
        )
        return

    if not is_supported_url(url):
        bot.reply_to(
            message,
            """
❌ <b>Unsupported Link</b>

Currently supported platforms:

• Instagram
• Facebook
• YouTube
"""
        )
        return

    # Same message will be edited during the process.
    status_message = bot.reply_to(
        message,
        "🔎 <b>Analyzing...</b>"
    )

    threading.Thread(
        target=process_download,
        args=(message, status_message, url),
        daemon=True
    ).start()


# =========================================================
# DOWNLOAD PROCESS
# =========================================================

def process_download(message, status_message, url):

    file_path = None

    try:

        # -------------------------------------------------
        # ANALYZING
        # -------------------------------------------------

        try:
            bot.edit_message_text(
                "🔎 <b>Analyzing...</b>",
                chat_id=status_message.chat.id,
                message_id=status_message.message_id
            )
        except Exception:
            pass

        # -------------------------------------------------
        # DOWNLOADING
        # -------------------------------------------------

        try:
            bot.edit_message_text(
                "⬇️ <b>Downloading (50%)...</b>",
                chat_id=status_message.chat.id,
                message_id=status_message.message_id
            )
        except Exception:
            pass

        file_path = download_video(url)

        # -------------------------------------------------
        # UPLOADING
        # -------------------------------------------------

        try:
            bot.edit_message_text(
                "⬆️ <b>Uploading (100%)...</b>",
                chat_id=status_message.chat.id,
                message_id=status_message.message_id
            )
        except Exception:
            pass

        caption = (
            "Downloaded Successfully! "
            "Power by: @Insta_Tiktok_YT_FB_Downloader bot"
        )

        # -------------------------------------------------
        # SEND VIDEO
        # -------------------------------------------------

        with open(file_path, "rb") as video:

            bot.send_video(
                chat_id=message.chat.id,
                video=video,
                caption=caption,
                supports_streaming=True
            )

        # -------------------------------------------------
        # DELETE FILE IMMEDIATELY AFTER SENDING
        # -------------------------------------------------

        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            file_path = None

        # Delete progress message after successful upload.
        try:
            bot.delete_message(
                status_message.chat.id,
                status_message.message_id
            )
        except Exception:
            pass

    except Exception as error:

        logging.exception(
            "Download error: %s",
            error
        )

        # Cleanup if something failed.
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        try:
            bot.edit_message_text(
                """
❌ <b>Download Failed</b>

Something went wrong while processing this video.

Please check that:
• The link is public
• The video still exists
• The URL is correct

Then try again.
""",
                chat_id=status_message.chat.id,
                message_id=status_message.message_id
            )
        except Exception:
            pass


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.message_handler(
    content_types=[
        "photo",
        "audio",
        "document",
        "voice",
        "sticker",
        "location",
        "contact"
    ]
)
def unsupported_message(message):

    bot.reply_to(
        message,
        "📥 Please send an Instagram, Facebook or YouTube video link."
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # Start Flask in background.
    flask_thread = threading.Thread(
        target=keep_alive,
        daemon=True
    )

    flask_thread.start()

    logging.info(
        "Keep-alive Flask server started on port 10000."
    )

    logging.info(
        "Telegram bot started."
    )

    # Long polling
    bot.infinity_polling(
        skip_pending=True,
        timeout=60,
        long_polling_timeout=60
    )
