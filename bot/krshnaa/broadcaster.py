# © 2025 FtKrishna. All rights reserved.
# Channel  : https://t.me/NxMirror
# Contact  : @FTKrshna

import asyncio
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from bot.logger import setup_logger
from ..helpers import is_authorized
from ..modules import mongo_db
from config import DEFAULT_CHANNELS, DELETE_TIME

logger = setup_logger(__name__)

# ========================= STATES =========================
class BroadcastState(StatesGroup):
    WaitingForMessage = State()

# ========================= SEND MESSAGE FUNCTION =========================
async def send_to_channel_v2(bot, content: dict, channel_id: int):
    """Send content to a channel."""
    try:
        ctype = content.get("type")
        if ctype == "text":
            await bot.send_message(channel_id, content.get("text", ""), parse_mode=types.ParseMode.HTML)
        elif ctype == "photo":
            await bot.send_photo(channel_id, content.get("file_id"), caption=content.get("caption", ""))
        elif ctype == "video":
            await bot.send_video(channel_id, content.get("file_id"), caption=content.get("caption", ""))
        elif ctype == "document":
            await bot.send_document(channel_id, content.get("file_id"), caption=content.get("caption", ""))
        else:
            return False
        return True
    except Exception as e:
        logger.error(f"Error sending to channel {channel_id}: {str(e)}")
        return False

# ========================= DELETE HELPER =========================
async def delete_after_delay(bot, chat_id, message_id):
    try:
        await asyncio.sleep(DELETE_TIME)
        await bot.delete_message(chat_id, message_id)
        logger.info(f"Deleted message {message_id} in chat {chat_id}")
    except Exception as e:
        logger.warning(f"Failed to delete message {message_id} in chat {chat_id}: {e}")

# ========================= GET CHANNELS =========================
async def get_all_channels(bot):
    db_channels = await mongo_db.get_channels()
    channels = db_channels if db_channels else []
    default_channels = []
    if DEFAULT_CHANNELS:
        for ch_id in DEFAULT_CHANNELS:
            try:
                chat = await bot.get_chat(ch_id)
                if chat.type == "channel":
                    default_channels.append({"channel_id": ch_id, "title": chat.title})
            except:
                continue
        channel_ids = {ch["channel_id"] for ch in channels}
        for ch in default_channels:
            if ch["channel_id"] not in channel_ids:
                channels.append(ch)
    return channels

# ========================= BROADCAST COMMAND =========================
async def broadcast_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ You are not authorized to use this command.")
        return

    data = await state.get_data()
    saved_content = data.get("content")

    # -------------------- REPLY-TO MESSAGE --------------------
    if message.reply_to_message:
        reply_msg = message.reply_to_message
        content = {}
        if reply_msg.text:
            content["type"] = "text"
            content["text"] = reply_msg.text
        elif reply_msg.photo:
            content["type"] = "photo"
            content["file_id"] = reply_msg.photo[-1].file_id
            content["caption"] = reply_msg.caption or ""
        elif reply_msg.video:
            content["type"] = "video"
            content["file_id"] = reply_msg.video.file_id
            content["caption"] = reply_msg.caption or ""
        elif reply_msg.document:
            content["type"] = "document"
            content["file_id"] = reply_msg.document.file_id
            content["caption"] = reply_msg.caption or ""
        else:
            await message.reply("❌ Unsupported content type in reply.")
            return

        # Delete admin's reply message automatically
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, reply_msg.chat.id, reply_msg.message_id))

        # Broadcast immediately
        channels = await get_all_channels(message.bot)
        success, fail = 0, []
        for ch in channels:
            sent = await send_to_channel_v2(message.bot, content, ch["channel_id"])
            if sent:
                success += 1
            else:
                fail.append(ch["channel_id"])

        result = f"✅ Broadcast finished: {success}/{len(channels)} successful."
        if fail:
            result += "\n❌ Failed:\n" + "\n".join(str(cid) for cid in fail)
        result_msg = await message.reply(result)
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, result_msg.chat.id, result_msg.message_id))
        return

    # -------------------- SAVED MESSAGE IN STATE --------------------
    elif saved_content:
        channels = await get_all_channels(message.bot)
        success, fail = 0, []
        for ch in channels:
            sent = await send_to_channel_v2(message.bot, saved_content, ch["channel_id"])
            if sent:
                success += 1
            else:
                fail.append(ch["channel_id"])

        result = f"✅ Broadcast finished: {success}/{len(channels)} successful."
        if fail:
            result += "\n❌ Failed:\n" + "\n".join(str(cid) for cid in fail)
        result_msg = await message.reply(result)
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, result_msg.chat.id, result_msg.message_id))
        await state.finish()
        return

    # -------------------- ASK ADMIN FOR NEW MESSAGE --------------------
    else:
        msg = await message.reply("📣 Please send the message you want to broadcast (text, photo, video, or document).")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))
        await BroadcastState.WaitingForMessage.set()
        await state.update_data(user_id=user_id)

# ========================= RECEIVE BROADCAST MESSAGE =========================
async def receive_broadcast_message(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        return

    content = {}
    if message.text:
        content["type"] = "text"
        content["text"] = message.text
    elif message.photo:
        content["type"] = "photo"
        content["file_id"] = message.photo[-1].file_id
        content["caption"] = message.caption or ""
    elif message.video:
        content["type"] = "video"
        content["file_id"] = message.video.file_id
        content["caption"] = message.caption or ""
    elif message.document:
        content["type"] = "document"
        content["file_id"] = message.document.file_id
        content["caption"] = message.caption or ""
    else:
        error_msg = await message.reply("❌ Unsupported content type. Send text, photo, video, or document.")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, error_msg.chat.id, error_msg.message_id))
        await state.finish()
        return

    # Delete admin's message automatically
    if DELETE_TIME > 0:
        asyncio.create_task(delete_after_delay(message.bot, message.chat.id, message.message_id))

    await state.update_data(content=content)

    # Send immediately
    channels = await get_all_channels(message.bot)
    success, fail = 0, []
    for ch in channels:
        sent = await send_to_channel_v2(message.bot, content, ch["channel_id"])
        if sent:
            success += 1
        else:
            fail.append(ch["channel_id"])

    result = f"✅ Broadcast finished: {success}/{len(channels)} successful."
    if fail:
        result += "\n❌ Failed:\n" + "\n".join(str(cid) for cid in fail)
    result_msg = await message.reply(result)
    if DELETE_TIME > 0:
        asyncio.create_task(delete_after_delay(message.bot, result_msg.chat.id, result_msg.message_id))

    await state.finish()
