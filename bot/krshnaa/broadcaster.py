# © 2025 FtKrishna. All rights reserved.
# Channel  : https://t.me/NxMirror
# Contact  : @FTKrshna

import asyncio
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import TelegramAPIError

from bot.logger import setup_logger
from ..helpers import is_authorized, send_preview, send_to_channel
from ..modules import mongo_db
from config import DEFAULT_CHANNELS, DELETE_TIME

logger = setup_logger(__name__)

# ========================= STATES =========================
class BroadcastState(StatesGroup):
    WaitingForMessage = State()

# ========================= COMMAND =========================
async def broadcast_command(message: types.Message, state: FSMContext, from_button=False, user_id=None):
    effective_user_id = user_id or message.from_user.id
    logger.info(f"Received /broadcast from user {effective_user_id} (from_button={from_button})")

    if not is_authorized(effective_user_id):
        await message.reply("❌ You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {effective_user_id} attempted /broadcast")
        return

    try:
        # ------------------ Method 1: Reply message ------------------
        if message.reply_to_message:
            reply_msg = message.reply_to_message
            channels = await get_all_channels(message.bot)
            sent, failed = 0, []

            for ch in channels:
                try:
                    await reply_msg.copy(chat_id=ch["channel_id"])
                    sent += 1
                except Exception as e:
                    failed.append((ch["channel_id"], str(e)))

            result = f"✅ Broadcast finished: {sent}/{len(channels)} successful."
            if failed:
                result += "\n❌ Failed:\n" + "\n".join(f"{c}: {err}" for c, err in failed)

            await message.reply(result)
            return

        # ------------------ Method 2: Ask for new message ------------------
        msg = await message.reply("Please send the message you want to broadcast (text, media, or media with captions).")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))

        await BroadcastState.WaitingForMessage.set()
        await state.update_data(user_id=effective_user_id)
        logger.info(f"Prompted user {effective_user_id} for broadcast message")

    except Exception as e:
        await message.reply("❌ Error starting broadcast.")
        logger.error(f"Error in /broadcast: {str(e)}")
        await state.finish()

# ========================= CHANNELS =========================
async def get_all_channels(bot):
    db_channels = await mongo_db.get_channels()
    channels = db_channels if db_channels else []
    default_channels = []

    if DEFAULT_CHANNELS:
        for channel_id in DEFAULT_CHANNELS:
            try:
                chat = await bot.get_chat(channel_id)
                if chat.type == "channel":
                    default_channels.append({"channel_id": channel_id, "title": chat.title})
            except TelegramAPIError as e:
                logger.error(f"Error fetching default channel {channel_id}: {str(e)}")

        existing_ids = {ch["channel_id"] for ch in channels}
        for def_ch in default_channels:
            if def_ch["channel_id"] not in existing_ids:
                channels.append(def_ch)

    logger.info(f"Total channels available for broadcast: {len(channels)}")
    return channels

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
        msg = await message.reply("❌ Unsupported content type. Send text, photo, video, or document.")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))
        await state.finish()
        return

    await state.update_data(content=content)

    # Show preview
    preview_msg = await send_preview(message.bot, content, None, message.chat.id)
    if DELETE_TIME > 0:
        asyncio.create_task(delete_after_delay(message.bot, preview_msg.chat.id, preview_msg.message_id))

    # Broadcast immediately
    channels = await get_all_channels(message.bot)
    sent, failed = 0, []

    for ch in channels:
        try:
            await send_to_channel(message.bot, content, None, ch["channel_id"])
            sent += 1
        except TelegramAPIError as e:
            failed.append((ch["channel_id"], str(e)))

    result = f"✅ Broadcast finished: {sent}/{len(channels)} successful."
    if failed:
        result += "\n❌ Failed:\n" + "\n".join(f"{c}: {err}" for c, err in failed)

    await message.reply(result)
    await state.finish()

# ========================= DELETE HELPER =========================
async def delete_after_delay(bot, chat_id, message_id):
    try:
        await asyncio.sleep(DELETE_TIME)
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
