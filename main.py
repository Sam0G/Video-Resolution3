import os
import asyncio
from aiohttp import web
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

API_ID = 38831490              # Replace with your Telegram API ID
API_HASH = "d8f0dfa3edfa244df7f5623fef10826b"     # Replace with your Telegram API HASH
BOT_TOKEN = "8953003387:AAEUDPy1HTWbc35-lvgfeYxHzQ8qbEOE4aI"   # Replace with your Bot Token

bot = TelegramClient('bot_session', API_ID, API_HASH)

def generate_response(width: int, height: int, file_ext: str = "Video") -> str:
    p_value = min(width, height)
    orientation = "Portrait (Vertical)" if height > width else "Landscape (Horizontal)"

    if p_value >= 2160:
        standard = "4K UHD"
    elif p_value >= 1440:
        standard = "2K QHD"
    elif p_value >= 1080:
        standard = "1080p (Full HD)"
    elif p_value >= 720:
        standard = "720p (HD)"
    elif p_value >= 480:
        standard = "480p (SD)"
    elif p_value >= 360:
        standard = "360p"
    else:
        standard = "Low Resolution"

    ratio = round(max(width, height) / min(width, height), 2)

    return (
        f"🎯 **Exact Resolution:** `{p_value}p`\n\n"
        f"📋 **Detailed Specifications:**\n"
        f"• **Dimensions:** `{width}x{height}` px\n"
        f"• **Orientation:** `{orientation}`\n"
        f"• **Nearest Standard:** `{standard}`\n"
        f"• **Aspect Ratio:** `~{ratio}:1`\n"
        f"• **Container Format:** `{file_ext.upper()}`"
    )

def extract_metadata_stream(file_path: str):
    """Pure Python container header inspection without OS dependencies."""
    try:
        parser = createParser(file_path)
        if parser:
            with parser:
                metadata = extractMetadata(parser)
                if metadata:
                    w, h = None, None
                    for line in metadata.exportPlaintext():
                        if "Image width:" in line:
                            w = int(line.split(":")[1].replace("pixels", "").strip())
                        elif "Image height:" in line:
                            h = int(line.split(":")[1].replace("pixels", "").strip())
                    if w and h:
                        return w, h
    except Exception:
        pass
    return None, None

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply(
        "👋 **Video Resolution Inspector Bot**\n\n"
        "Send or forward any video or document file (MP4, MKV, AVI, FLV, TS, MOV, WMV, etc.).\n"
        "I will detect the exact **p** resolution and provide both a quick summary and full technical breakdown."
    )

@bot.on(events.NewMessage)
async def check_resolution(event):
    if event.text and event.text.startswith('/'):
        return

    msg = event.message
    if not (msg.video or msg.document):
        return

    file_ext = "Video"
    if msg.document:
        for attr in msg.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                _, ext = os.path.splitext(attr.file_name)
                file_ext = ext.lstrip('.').lower() or "Document"
                break

    width, height = None, None

    # Step 1: Check pre-parsed Telegram attributes
    target = msg.video or msg.document
    for attr in target.attributes:
        if isinstance(attr, DocumentAttributeVideo):
            if attr.w and attr.h:
                width, height = attr.w, attr.h
                break

    # Step 2: Read header sample (first 1MB chunk)
    if not (width and height):
        status_msg = await event.reply("🔍 Inspecting video stream header...")
        temp_file = f"sample_{msg.id}.bin"
        try:
            with open(temp_file, 'wb') as f:
                async for chunk in bot.iter_download(msg.media, request_size=1048576):
                    f.write(chunk)
                    break
            
            width, height = extract_metadata_stream(temp_file)
            if os.path.exists(temp_file):
                os.remove(temp_file)
            await status_msg.delete()
        except Exception:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            await status_msg.delete()

    if width and height:
        response_text = generate_response(width, height, file_ext)
        await event.reply(response_text, parse_mode='markdown')
    else:
        await event.reply(
            "⚠️ **Could not determine video dimensions.**\n"
            "The file header might be missing or corrupted."
        )

# Keep-alive web server for Render Free tier
async def dummy_web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    await dummy_web_server()
    print("Bot is up and listening for all formats...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
