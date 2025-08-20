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
    logger.info(f"Received /broadcast from user {user_id or message.from_user.id} (from_button={from_button})")
    effective_user_id = user_id or message.from_user.id

    if not is_authorized(effective_user_id):
        await message.reply("You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {effective_user_id} attempted /broadcast")
        return

    try:
        data = await state.get_data()
        saved_content = data.get("content")

        if saved_content:
            # ✅ Method 1: Send already saved message
            channels = await get_all_channels(message.bot)
            success, fail = 0, []
            for channel in channels:
                try:
                    await send_to_channel(message.bot, saved_content, None, channel["channel_id"])
                    success += 1
                except TelegramAPIError as e:
                    fail.append((channel["channel_id"], str(e)))

            result = f"✅ Broadcast sent: {success}/{len(channels)} successful."
            if fail:
                result += "\n❌ Failed:\n" + "\n".join(f"{c}: {err}" for c, err in fail)

            await message.reply(result)
            await state.finish()

        else:
            # ✅ Method 2: Ask for new message
            msg = await message.reply("Please send the message you want to broadcast (text, media, or media with captions).")
            if DELETE_TIME > 0:
                asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))

            await BroadcastState.WaitingForMessage.set()
            await state.update_data(user_id=effective_user_id)
            logger.info(f"Prompted user {effective_user_id} for broadcast message")

    except Exception as e:
        await message.reply("Error starting broadcast.")
        logger.error(f"Error in /broadcast: {str(e)}")
        await state.finish()

# ========================= CHANNELS =========================
async def get_all_channels(bot):
    db_channels = await mongo_db.get_channels()
    channels = db_channels if db_channels else []
    default_channels = []
    try:
        if DEFAULT_CHANNELS:
            for channel_id in DEFAULT_CHANNELS:
                try:
                    chat = await bot.get_chat(channel_id)
                    if chat.type == "channel":
                        default_channels.append({"channel_id": channel_id, "title": chat.title})
                    else:
                        logger.warning(f"Default channel ID {channel_id} is not a channel")
                except TelegramAPIError as e:
                    logger.error(f"Error fetching default channel {channel_id}: {str(e)}")
            channel_ids = {ch["channel_id"] for ch in channels}
            for def_ch in default_channels:
                if def_ch["channel_id"] not in channel_ids:
                    channels.append(def_ch)
            logger.info(f"Combined channels for broadcast: {len(channels)}")
    except NameError:
        logger.info("DEFAULT_CHANNELS not defined, using only database channels")
    return channels

# ========================= RECEIVE BROADCAST =========================
async def receive_broadcast_message(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        return

    logger.info(f"Received broadcast message from user {message.from_user.id}: {message.text if message.text else message.content_type}")
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
        msg = await message.reply("Unsupported content type. Please send text, photo, video, or document.")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))
        await state.finish()
        return

    try:
        # Save message for Method 1
        await state.update_data(content=content)

        # Show preview
        preview_message = await send_preview(message.bot, content, None, message.chat.id)
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, preview_message.chat.id, preview_message.message_id))

        # Immediately broadcast (Method 2)
        channels = await get_all_channels(message.bot)
        success, fail = 0, []
        for channel in channels:
            try:
                await send_to_channel(message.bot, content, None, channel["channel_id"])
                success += 1
            except TelegramAPIError as e:
                fail.append((channel["channel_id"], str(e)))

        result = f"✅ Broadcast sent: {success}/{len(channels)} successful."
        if fail:
            result += "\n❌ Failed:\n" + "\n".join(f"{c}: {err}" for c, err in fail)

        await message.reply(result)
        await state.finish()

    except Exception as e:
        await message.reply("Error processing broadcast.")
        logger.error(f"Error in receive_broadcast_message: {str(e)}")
        await state.finish()

# ========================= DELETE HELPER =========================
async def delete_after_delay(bot, chat_id, message_id):
    try:
        await asyncio.sleep(DELETE_TIME)
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
