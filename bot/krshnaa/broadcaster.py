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
from .keyboards import create_channel_selection_keyboard, create_button_keyboard, create_confirm_keyboard
from Scripts import FtKrshna

logger = setup_logger(__name__)

class BroadcastState(StatesGroup):
    WaitingForMessage = State()
    WaitingForButtons = State()
    WaitingForPreview = State()

async def broadcast_command(message: types.Message, state: FSMContext, from_button=False, user_id=None):
    logger.info(f"Received /broadcast from user {user_id or message.from_user.id} (from_button={from_button})")
    effective_user_id = user_id or message.from_user.id
    if not is_authorized(effective_user_id):
        await message.reply("You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {effective_user_id} attempted /broadcast")
        return
    try:
        msg = await message.reply(
            "Please send the message you want to broadcast (text, media, or media with captions).",
            reply_markup=create_channel_selection_keyboard([], show_back=False, show_close=True)
        )

        # ✅ Auto-delete the bot’s prompt
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))

        await BroadcastState.WaitingForMessage.set()
        await state.update_data(user_id=effective_user_id, flow="broadcast")
        logger.info(f"Prompted user {effective_user_id} for broadcast message")
    except Exception as e:
        await message.reply("Error starting broadcast.")
        logger.error(f"Error in /broadcast: {str(e)}")
        await state.finish()

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
            logger.info(f"Combined channels for broadcast: {len(channels)} (DB: {len(db_channels)}, Default: {len(default_channels)})")
    except NameError:
        logger.info("DEFAULT_CHANNELS not defined, using only database channels")
    return channels

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
        await state.update_data(content=content)
        msg = await message.reply(
            FtKrshna.DEFAULT_BUTTONS_TEXT,
            parse_mode=types.ParseMode.MARKDOWN,
            reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
        )

        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))

        await BroadcastState.WaitingForButtons.set()
    except Exception as e:
        await message.reply("Error processing message.")
        await state.finish()

async def receive_broadcast_buttons(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        return

    content = user_data.get("content")
    if not content:
        msg = await message.reply("Error: No message content found. Please start over with /broadcast.")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))
        await state.finish()
        return

    try:
        reply_markup = None
        if message.text.lower() != "none":
            reply_markup = create_button_keyboard(message.text, for_preview=True)

        preview_message = await send_preview(message.bot, content, reply_markup, message.chat.id)

        # ✅ Auto-delete preview message
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, preview_message.chat.id, preview_message.message_id))

        await state.update_data(preview_message_id=preview_message.message_id, reply_markup=reply_markup)

        confirm_msg = await message.reply(
            "Preview sent. Please confirm to broadcast to all channels or cancel:",
            reply_markup=create_confirm_keyboard()
        )
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, confirm_msg.chat.id, confirm_msg.message_id))

        await BroadcastState.WaitingForPreview.set()
    except Exception as e:
        msg = await message.reply("Error processing buttons. Please try again.")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(message.bot, msg.chat.id, msg.message_id))
        await state.finish()

async def handle_broadcast_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if callback_query.from_user.id != user_data.get("user_id"):
        await callback_query.answer()
        return

    content = user_data.get("content")
    reply_markup = user_data.get("reply_markup")

    try:
        if callback_query.data == "confirm_post":
            channels = await get_all_channels(callback_query.bot)
            if not channels:
                msg = await callback_query.message.reply("No channels available for broadcasting.")
                if DELETE_TIME > 0:
                    asyncio.create_task(delete_after_delay(callback_query.bot, msg.chat.id, msg.message_id))
                await state.finish()
                return

            success_count = 0
            failed_channels = []
            for channel in channels:
                channel_id = channel["channel_id"]
                try:
                    sent_msg = await send_to_channel(callback_query.bot, content, reply_markup, channel_id)
                    success_count += 1

                    # ✅ Auto-delete broadcasted message
                    if sent_msg and DELETE_TIME > 0:
                        asyncio.create_task(delete_after_delay(callback_query.bot, channel_id, sent_msg.message_id))

                except TelegramAPIError as e:
                    failed_channels.append((channel_id, str(e)))

            response = f"✅ Broadcast completed: {success_count}/{len(channels)} successful."
            if failed_channels:
                response += "\n❌ Failed:\n" + "\n".join(f"{ch[0]}: {ch[1]}" for ch in failed_channels)

            msg = await callback_query.message.reply(response)
            if DELETE_TIME > 0:
                asyncio.create_task(delete_after_delay(callback_query.bot, msg.chat.id, msg.message_id))

        else:
            msg = await callback_query.message.reply("Broadcast canceled.")
            if DELETE_TIME > 0:
                asyncio.create_task(delete_after_delay(callback_query.bot, msg.chat.id, msg.message_id))

        await state.finish()
        await callback_query.answer()

    except Exception as e:
        msg = await callback_query.message.reply("Error processing broadcast confirmation.")
        if DELETE_TIME > 0:
            asyncio.create_task(delete_after_delay(callback_query.bot, msg.chat.id, msg.message_id))
        await state.finish()

# ✅ Helper for delayed deletion
async def delete_after_delay(bot, chat_id, message_id):
    try:
        await asyncio.sleep(DELETE_TIME)
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
