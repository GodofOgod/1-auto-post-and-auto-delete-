# © 2025 FtKrishna. All rights reserved.
# Channel  : https://t.me/NxMirror
# Contact  : @FTKrshna

from bot.logger import setup_logger
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import TelegramAPIError
from config import DEFAULT_CHANNELS
from Scripts import FtKrshna
from ..modules import mongo_db
from .keyboards import (
    create_channel_selection_keyboard,
    create_button_keyboard,
    create_confirm_keyboard,
    create_start_keyboard,
    create_default_buttons_keyboard,
    create_my_channels_keyboard,
    create_help_keyboard
)
from ..helpers import is_authorized, send_preview, send_to_channel
from .broadcaster import (
    broadcast_command,
    BroadcastState,
    receive_broadcast_message
)

logger = setup_logger(__name__)

class PostState(StatesGroup):
    WaitingForChannel = State()
    WaitingForMessage = State()
    WaitingForButtons = State()
    WaitingForPreview = State()

class EditState(StatesGroup):
    WaitingForChannel = State()
    WaitingForMessageId = State()
    WaitingForContent = State()
    WaitingForButtons = State()
    WaitingForPreview = State()

class DefaultButtonsState(StatesGroup):
    WaitingForButtons = State()

async def start_command(message: types.Message, state: FSMContext):
    logger.info(f"Received /start from user {message.from_user.id}")
    await state.finish()
    await message.reply(
        FtKrshna.START_TEXT,
        parse_mode=types.ParseMode.MARKDOWN,
        reply_markup=create_start_keyboard()
    )

async def help_command(message: types.Message, state: FSMContext):
    """Send a beginner-friendly help message with examples for all commands and features."""
    logger.info(f"Received /help from user {message.from_user.id}")
    await state.finish()
    try:
        await message.reply(
            FtKrshna.HELP_TEXT,
            parse_mode=types.ParseMode.MARKDOWN,
            reply_markup=create_help_keyboard()
        )
        logger.info(f"Sent help message to user {message.from_user.id}")
    except Exception as e:
        await message.reply("Error sending help message. Please try again.")
        logger.error(f"Error in help_command for user {message.from_user.id}: {str(e)}")

async def add_channel_command(message: types.Message):
    logger.info(f"Received /add from user {message.from_user.id}")
    if not is_authorized(message.from_user.id):
        await message.reply("You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {message.from_user.id} attempted /add")
        return
    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].startswith("-100"):
            await message.reply("Usage: /add -100xxxxxx")
            logger.error(f"Invalid /add command format: {message.text}")
            return
        channel_id = int(args[1])
        chat = await message.bot.get_chat(channel_id)
        if chat.type != "channel":
            await message.reply("The provided ID is not a channel.")
            logger.error(f"ID {channel_id} is not a channel")
            return
        if await mongo_db.add_channel(channel_id, chat.title):
            await message.reply(f"✅ Channel '{chat.title}' has been added to the database.")
        else:
            await message.reply(f"Channel '{chat.title}' already exists.")
    except TelegramAPIError as e:
        await message.reply(f"Error: {str(e)}")
        logger.error(f"Telegram API error adding channel: {str(e)}")
    except ValueError:
        await message.reply("Invalid channel ID format.")
        logger.error(f"Invalid channel ID format: {args[1]}")
    except Exception as e:
        await message.reply("An unexpected error occurred.")
        logger.error(f"Unexpected error in /add: {str(e)}")

async def set_default_buttons_command(message: types.Message, state: FSMContext, from_button=False, user_id=None):
    logger.info(f"Received /setdefaultbtns from user {user_id or message.from_user.id} (from_button={from_button})")
    effective_user_id = user_id or message.from_user.id
    if not is_authorized(effective_user_id):
        await message.reply("You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {effective_user_id} attempted /setdefaultbtns")
        return
    try:
        await message.reply(
            FtKrshna.DEFAULT_BUTTONS_TEXT,
            parse_mode=types.ParseMode.MARKDOWN,
            reply_markup=create_channel_selection_keyboard([], show_back=from_button, show_close=True)
        )
        await DefaultButtonsState.WaitingForButtons.set()
        await state.update_data(user_id=effective_user_id)
        logger.info(f"Prompted user {effective_user_id} for default buttons")
    except Exception as e:
        await message.reply("Error initiating default buttons setup.")
        logger.error(f"Error in set_default_buttons_command: {str(e)}")
        await state.finish()

async def receive_default_buttons(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        logger.warning(f"User mismatch: {message.from_user.id} != {user_data.get('user_id')}")
        return
    logger.info(f"Received default buttons from user {message.from_user.id}: {message.text}")
    try:
        button_text = message.text.strip()
        if button_text.lower() == "none":
            if await mongo_db.delete_default_buttons(message.from_user.id):
                await message.reply("Default buttons cleared successfully.")
                logger.info(f"Cleared default buttons for user {message.from_user.id}")
            else:
                await message.reply("No default buttons were set.")
                logger.info(f"No default buttons to clear for user {message.from_user.id}")
        else:
            create_button_keyboard(button_text, for_preview=True)
            if await mongo_db.set_default_buttons(message.from_user.id, button_text):
                await message.reply("Default buttons set successfully.")
                logger.info(f"Set default buttons for user {message.from_user.id}")
            else:
                await message.reply("Failed to set default buttons.")
                logger.error(f"Failed to set default buttons for user {message.from_user.id}")
        await state.finish()
    except ValueError as e:
        await message.reply("Invalid button format. Please use the specified format or send 'none'.")
        logger.error(f"Invalid button format from user {message.from_user.id}: {str(e)}")
    except Exception as e:
        await message.reply("Error processing default buttons.")
        logger.error(f"Error in receive_default_buttons: {str(e)}")
        await state.finish()

async def get_channels_for_selection(bot, for_my_channels=False):
    db_channels = await mongo_db.get_channels()
    channels = db_channels if db_channels else []
    if not for_my_channels:
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
                logger.info(f"Combined channels: {len(channels)} (DB: {len(db_channels)}, Default: {len(default_channels)})")
        except NameError:
            logger.info("DEFAULT_CHANNELS not defined, using only database channels")
    else:
        logger.info(f"Returning only database channels for My Channels: {len(channels)}")
    return channels

async def my_channels_command(message: types.Message, state: FSMContext, from_button=False, user_id=None):
    logger.info(f"Received My Channels request from user {user_id or message.from_user.id} (from_button={from_button})")
    effective_user_id = user_id or message.from_user.id
    if not is_authorized(effective_user_id):
        await message.reply("You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {effective_user_id} attempted My Channels")
        return
    channels = await get_channels_for_selection(message.bot, for_my_channels=True)
    if not channels:
        await message.reply("No channels saved in the database. Use /add to add a channel.")
        logger.info("No saved channels found for My Channels")
        return
    try:
        await message.reply(
            "Your saved channels:",
            reply_markup=create_my_channels_keyboard(channels)
        )
        logger.info(f"Sent My Channels keyboard to user {effective_user_id}")
    except Exception as e:
        await message.reply("Error displaying channels.")
        logger.error(f"Error in my_channels_command: {str(e)}")

async def post_command(message: types.Message, state: FSMContext, from_button=False, user_id=None):
    logger.info(f"Received /post from user {user_id or message.from_user.id} (from_button={from_button})")
    effective_user_id = user_id or message.from_user.id
    logger.debug(f"Checking authorization for user {effective_user_id}")
    if not is_authorized(effective_user_id):
        await message.reply("You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {effective_user_id} attempted /post")
        return
    channels = await get_channels_for_selection(message.bot)
    if not channels:
        await message.reply(FtKrshna.NO_CHANNELS_TEXT)
        logger.info("No channels found for /post")
        await state.finish()
        return
    try:
        await message.reply(
            "Please select a channel:",
            reply_markup=create_channel_selection_keyboard(channels, show_back=False)
        )
        await PostState.WaitingForChannel.set()
        await state.update_data(user_id=effective_user_id, flow="post")
        logger.info(f"Sent channel selection keyboard to user {effective_user_id}")
    except Exception as e:
        await message.reply("Error displaying channel selection.")
        logger.error(f"Error in /post: {str(e)}")
        await state.finish()

async def edit_command(message: types.Message, state: FSMContext, from_button=False, user_id=None):
    logger.info(f"Received /edit from user {user_id or message.from_user.id} (from_button={from_button})")
    effective_user_id = user_id or message.from_user.id
    logger.debug(f"Checking authorization for user {effective_user_id}")
    if not is_authorized(effective_user_id):
        await message.reply("You are not authorized to use this command.")
        logger.warning(f"Unauthorized user {effective_user_id} attempted /edit")
        return
    channels = await get_channels_for_selection(message.bot)
    if not channels:
        await message.reply(FtKrshna.NO_CHANNELS_TEXT)
        logger.info("No channels found for /edit")
        await state.finish()
        return
    try:
        await message.reply(
            FtKrshna.SELECT_CHANNEL_TEXT,
            reply_markup=create_channel_selection_keyboard(channels, show_back=False)
        )
        await EditState.WaitingForChannel.set()
        await state.update_data(user_id=effective_user_id, flow="edit")
        logger.info(f"Sent channel selection keyboard for edit to user {effective_user_id}")
    except Exception as e:
        await message.reply("Error displaying channel selection.")
        logger.error(f"Error in /edit: {str(e)}")
        await state.finish()


async def start_button_callback(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    logger.info(f"Received start button callback from user {user_id}: {callback_query.data}")
    try:
        if callback_query.data == "start_post":
            logger.debug(f"Triggering post_command for user {user_id}")
            await post_command(
                message=callback_query.message,
                state=state,
                from_button=True,
                user_id=user_id
            )
        elif callback_query.data == "start_edit":
            logger.debug(f"Triggering edit_command for user {user_id}")
            await edit_command(
                message=callback_query.message,
                state=state,
                from_button=True,
                user_id=user_id
            )
        elif callback_query.data == "start_broadcast":
            logger.debug(f"Triggering broadcast_command for user {user_id}")
            await broadcast_command(
                message=callback_query.message,
                state=state,
                from_button=True,
                user_id=user_id
            )
        elif callback_query.data == "start_default_buttons":
            logger.debug(f"Showing default buttons keyboard for user {user_id}")
            default_buttons = await mongo_db.get_default_buttons(user_id)
            message_text = "Manage your default buttons:"
            if default_buttons:
                message_text += f"\n\nCurrent default buttons:\n{default_buttons}"
            await callback_query.message.edit_text(
                message_text,
                reply_markup=create_default_buttons_keyboard()
            )
            await callback_query.answer()
        elif callback_query.data == "start_my_channels":
            logger.debug(f"Triggering my_channels_command for user {user_id}")
            await my_channels_command(
                message=callback_query.message,
                state=state,
                from_button=True,
                user_id=user_id
            )
            await callback_query.answer()

        elif callback_query.data == "start_help":
            logger.debug(f"Showing help guide for user {user_id}")
            await callback_query.message.edit_text(
                FtKrshna.HELP_TEXT,
                parse_mode=types.ParseMode.MARKDOWN,
                reply_markup=create_help_keyboard()
            )
            await state.finish()
            await callback_query.answer()
        
        elif callback_query.data == "close_message":
            await callback_query.message.delete()
            logger.info(f"Deleted /start message for user {user_id}")
            await callback_query.answer()
        elif callback_query.data == "back_to_start":
            await callback_query.message.edit_text(
                "Welcome! Use the buttons below to post, edit, broadcast, manage default buttons, or view your channels.",
                reply_markup=create_start_keyboard()
            )
            await state.finish()
            await callback_query.answer()
    except Exception as e:
        await callback_query.message.reply("Error processing action.")
        logger.error(f"Error in start_button_callback for user {user_id}: {str(e)}")
        await callback_query.answer()

async def my_channels_callback(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    logger.info(f"Received My Channels callback from user {user_id}: {callback_query.data}")
    if not is_authorized(user_id):
        await callback_query.answer("You are not authorized.")
        logger.warning(f"Unauthorized user {user_id} attempted My Channels action")
        return
    try:
        if callback_query.data.startswith("delete_channel:"):
            _, channel_id = callback_query.data.split(":", 1)
            channel_id = int(channel_id)
            if await mongo_db.remove_channel(channel_id):
                channels = await get_channels_for_selection(callback_query.bot, for_my_channels=True)
                if channels:
                    await callback_query.message.edit_text(
                        "Channel deleted. Your saved channels:",
                        reply_markup=create_my_channels_keyboard(channels)
                    )
                else:
                    await callback_query.message.edit_text(
                        "Channel deleted. No saved channels left.",
                        reply_markup=create_start_keyboard()
                    )
                logger.info(f"Deleted channel {channel_id} by user {user_id}")
            else:
                await callback_query.answer("Failed to delete channel.")
                logger.error(f"Failed to delete channel {channel_id} by user {user_id}")
            await callback_query.answer()
        elif callback_query.data == "clear_all_channels":
            deleted_count = await mongo_db.clear_all_channels()
            await callback_query.message.edit_text(
                f"Cleared {deleted_count} channel(s). No saved channels left.",
                reply_markup=create_start_keyboard()
            )
            logger.info(f"Cleared {deleted_count} channels by user {user_id}")
            await callback_query.answer()
        elif callback_query.data.startswith("view_channel:"):
            await callback_query.answer("Channel selected. No further action available.")
        elif callback_query.data == "back_to_start":
            await callback_query.message.edit_text(
                "Welcome! Use the buttons below to post, edit, broadcast, manage default buttons, or view your channels.",
                reply_markup=create_start_keyboard()
            )
            await state.finish()
            await callback_query.answer()
    except ValueError as e:
        await callback_query.answer("Invalid channel ID.")
        logger.error(f"ValueError in my_channels_callback: {str(e)}")
    except TelegramAPIError as e:
        await callback_query.message.reply("Error processing action.")
        logger.error(f"TelegramAPIError in my_channels_callback: {str(e)}")
        await callback_query.answer()
    except Exception as e:
        await callback_query.message.reply("Error processing action.")
        logger.error(f"Unexpected error in my_channels_callback: {str(e)}")
        await callback_query.answer()

async def default_buttons_callback(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    logger.info(f"Received default buttons callback from user {user_id}: {callback_query.data}")
    try:
        if callback_query.data == "set_default_buttons":
            await set_default_buttons_command(
                message=callback_query.message,
                state=state,
                from_button=True,
                user_id=user_id
            )
        elif callback_query.data == "clear_default_buttons":
            if await mongo_db.delete_default_buttons(user_id):
                await callback_query.message.edit_text(
                    "Default buttons cleared successfully.",
                    reply_markup=create_default_buttons_keyboard()
                )
                logger.info(f"Cleared default buttons for user {user_id}")
            else:
                await callback_query.message.edit_text(
                    "No default buttons were set.",
                    reply_markup=create_default_buttons_keyboard()
                )
                logger.info(f"No default buttons to clear for user {user_id}")
            await callback_query.answer()
        elif callback_query.data == "back_to_start":
            await callback_query.message.edit_text(
                "Welcome! Use the buttons below to post, edit, broadcast, manage default buttons, or view your channels.",
                reply_markup=create_start_keyboard()
            )
            await state.finish()
            await callback_query.answer()
    except Exception as e:
        await callback_query.message.reply("Error processing default buttons action.")
        logger.error(f"Error in default_buttons_callback: {str(e)}")
        await callback_query.answer()

async def select_channel(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Received select_channel callback from user {callback_query.from_user.id}: {callback_query.data}")
    if not is_authorized(callback_query.from_user.id):
        await callback_query.answer("You are not authorized.")
        logger.warning(f"Unauthorized user {callback_query.from_user.id} attempted channel selection")
        return
    try:
        if not callback_query.data.startswith("select_channel:"):
            await callback_query.answer("Invalid selection.")
            logger.error(f"Invalid callback data in select_channel: {callback_query.data}")
            return
        _, channel_id = callback_query.data.split(":", 1)
        channel_id = int(channel_id)
        logger.info(f"User {callback_query.from_user.id} selected channel {channel_id}")
        user_data = await state.get_data()
        flow = user_data.get("flow")
        await state.update_data(channel_id=channel_id)
        if flow == "post":
            await callback_query.message.edit_text(
                "Please send the message you want to post (text, media, or media with captions).",
                reply_markup=create_channel_selection_keyboard([], show_back=False, show_close=True)
            )
            await PostState.WaitingForMessage.set()
        elif flow == "edit":
            await callback_query.message.edit_text(
                "Please send the message ID of the channel post you want to edit. You can find it in the channel or in the bot logs.",
                reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
            )
            await EditState.WaitingForMessageId.set()
        await callback_query.answer()
    except ValueError as e:
        await callback_query.answer("Invalid channel ID.")
        logger.error(f"ValueError in select_channel: {str(e)}")
    except TelegramAPIError as e:
        await callback_query.answer("Error processing selection.")
        logger.error(f"TelegramAPIError in select_channel: {str(e)}")
    except Exception as e:
        await callback_query.answer("An unexpected error occurred.")
        logger.error(f"Unexpected error in select_channel: {str(e)}")
        await state.finish()

async def back_action(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Received back_action callback from user {callback_query.from_user.id}")
    user_data = await state.get_data()
    flow = user_data.get("flow")
    current_state = await state.get_state()
    try:
        if flow == "post":
            if current_state == PostState.WaitingForMessage.state:
                channels = await get_channels_for_selection(callback_query.bot)
                await callback_query.message.edit_text(
                    FtKrshna.SELECT_CHANNEL_TEXT,
                    reply_markup=create_channel_selection_keyboard(channels)
                )
                await PostState.WaitingForChannel.set()
            elif current_state == PostState.WaitingForButtons.state:
                await callback_query.message.edit_text(
                    "Please send the message you want to post (text, media, or media with captions).",
                    reply_markup=create_channel_selection_keyboard([], show_back=False, show_close=True)
                )
                await PostState.WaitingForMessage.set()
            elif current_state == PostState.WaitingForPreview.state:
                await callback_query.message.edit_text(
                    FtKrshna.DEFAULT_BUTTONS_TEXT,
                    parse_mode=types.ParseMode.MARKDOWN,
                    reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
                )
                await PostState.WaitingForButtons.set()
        elif flow == "edit":
            if current_state == EditState.WaitingForMessageId.state:
                channels = await get_channels_for_selection(callback_query.bot)
                await callback_query.message.edit_text(
                    FtKrshna.SELECT_CHANNEL_TEXT,
                    reply_markup=create_channel_selection_keyboard(channels)
                )
                await EditState.WaitingForChannel.set()
            elif current_state == EditState.WaitingForContent.state:
                await callback_query.message.edit_text(
                    "Please send the message ID of the channel post you want to edit.",
                    reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
                )
                await EditState.WaitingForMessageId.set()
            elif current_state == EditState.WaitingForButtons.state:
                await callback_query.message.edit_text(
                    "Send the new content (text, photo, video, or document) or type 'keep' to keep the existing content.",
                    reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
                )
                await EditState.WaitingForContent.set()
            elif current_state == EditState.WaitingForPreview.state:
                await callback_query.message.edit_text(
                    FtKrshna.DEFAULT_BUTTONS_TEXT,
                    parse_mode=types.ParseMode.MARKDOWN,
                    reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
                )
                await EditState.WaitingForButtons.set()
        elif flow == "broadcast":
            if current_state == BroadcastState.WaitingForButtons.state:
                await callback_query.message.edit_text(
                    "Please send the message you want to broadcast (text, media, or media with captions).",
                    reply_markup=create_channel_selection_keyboard([], show_back=False, show_close=True)
                )
                await BroadcastState.WaitingForMessage.set()
            elif current_state == BroadcastState.WaitingForPreview.state:
                await callback_query.message.edit_text(
                    FtKrshna.DEFAULT_BUTTONS_TEXT,
                    parse_mode=types.ParseMode.MARKDOWN,
                    reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
                )
                await BroadcastState.WaitingForButtons.set()
        elif current_state == DefaultButtonsState.WaitingForButtons.state:
            await callback_query.message.edit_text(
                "Manage your default buttons:",
                reply_markup=create_default_buttons_keyboard()
            )
            await state.finish()
        await callback_query.answer()
    except TelegramAPIError as e:
        await callback_query.message.reply("Error navigating back.")
        logger.error(f"TelegramAPIError in back_action: {str(e)}")
    except Exception as e:
        await callback_query.message.reply("Error navigating back.")
        logger.error(f"Unexpected error in back_action: {str(e)}")
        await state.finish()

async def cancel_action(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Received cancel_action callback from user {callback_query.from_user.id}")
    try:
        await callback_query.message.reply("Operation canceled. Use /start to begin again.")
        await callback_query.message.delete()
        await state.finish()
        logger.info(f"User {callback_query.from_user.id} canceled operation")
        await callback_query.answer()
    except TelegramAPIError as e:
        await callback_query.message.reply("Error canceling operation.")
        logger.error(f"TelegramAPIError in cancel_action: {str(e)}")
        await state.finish()

async def close_message(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Received close_message callback from user {callback_query.from_user.id}")
    try:
        await callback_query.message.delete()
        await state.finish()
        logger.info(f"User {callback_query.from_user.id} closed message")
        await callback_query.answer()
    except TelegramAPIError as e:
        await callback_query.message.reply("Error closing message.")
        logger.error(f"TelegramAPIError in close_message: {str(e)}")
        await state.finish()

async def debug_callback(callback_query: types.CallbackQuery):
    logger.info(f"DEBUG: Received callback query from user {callback_query.from_user.id}: {callback_query.data}")
    await callback_query.answer(f"Received callback: {callback_query.data}")

async def receive_post_message(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        logger.warning(f"User mismatch: {message.from_user.id} != {user_data.get('user_id')}")
        return

    logger.info(f"Received message from user {message.from_user.id} for posting")

    content = {}
    full_text = ""
    media_type = None
    file_id = None

    if message.text:
        full_text = message.text
        media_type = "text"
    elif message.photo:
        full_text = message.caption or ""
        media_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        full_text = message.caption or ""
        media_type = "video"
        file_id = message.video.file_id
    elif message.document:
        full_text = message.caption or ""
        media_type = "document"
        file_id = message.document.file_id
    else:
        await message.reply("Unsupported content type. Please send text, photo, video, or document.")
        logger.error(f"Unsupported content type from user {message.from_user.id}")
        await state.finish()
        return

    lines = full_text.splitlines()
    content_lines = []
    button_lines = []
    format_started = False

    for line in lines:
        if line.strip().lower().startswith(("format=", "formet=")):
            format_started = True
            button_lines.append(line.split("=", 1)[1].strip())
        elif format_started:
            button_lines.append(line.strip())
        else:
            content_lines.append(line.strip())

    caption = "\n".join(content_lines).strip()
    button_text = "\n".join(button_lines).strip() if button_lines else None

    if media_type == "text":
        content["type"] = "text"
        content["text"] = caption
    else:
        content["type"] = media_type
        content["file_id"] = file_id
        content["caption"] = caption

    try:
        if button_text:
            default_buttons = await mongo_db.get_default_buttons(message.from_user.id)
            combined_button_text = button_text
            if default_buttons:
                combined_button_text += "\n" + default_buttons
            reply_markup = create_button_keyboard(combined_button_text, for_preview=True)
            logger.info(f"Parsed buttons from Format= for user {message.from_user.id}, included default buttons: {default_buttons is not None}")
            preview_message = await send_preview(message.bot, content, reply_markup, message.chat.id)
            await state.update_data(
                content=content,
                reply_markup=reply_markup,
                preview_message_id=preview_message.message_id
            )
            await message.reply(
                "Preview sent. Please confirm or cancel:",
                reply_markup=create_confirm_keyboard()
            )
            await PostState.WaitingForPreview.set()
        else:
            await state.update_data(content=content)
            await message.reply(
                FtKrshna.DEFAULT_BUTTONS_TEXT,
                parse_mode=types.ParseMode.MARKDOWN,
                reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
            )
            await PostState.WaitingForButtons.set()
    except Exception as e:
        await message.reply("Error processing message.")
        logger.error(f"Error in receive_post_message: {str(e)}")
        await state.finish()

async def receive_message_id(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        logger.warning(f"User mismatch: {message.from_user.id} != {user_data.get('user_id')}")
        return
    logger.info(f"Received message ID from user {message.from_user.id}: {message.text}")
    try:
        message_id = int(message.text.strip())
        channel_id = user_data.get("channel_id")
        try:
            chat = await message.bot.get_chat(channel_id)
            await message.bot.get_chat_member(channel_id, message.bot.id)
            await message.bot.edit_message_reply_markup(
                chat_id=channel_id,
                message_id=message_id,
                reply_markup=None
            )
        except TelegramAPIError as e:
            if "message is not modified" in str(e).lower():
                logger.info(f"Message ID {message_id} in channel {channel_id} has no reply_markup, proceeding")
            else:
                await message.reply("Invalid message ID. The message may not exist, the bot lacks permission, or it's not in the specified channel.")
                logger.error(f"Error validating message ID {message_id} in channel {channel_id}: {str(e)}")
                return
        await state.update_data(edit_message_id=message_id)
        await message.reply(
            "Send the new content (text, photo, video, or document) or type 'keep' to keep the existing content.",
            reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
        )
        await EditState.WaitingForContent.set()
    except ValueError:
        await message.reply("Invalid message ID. Please send a numeric message ID.")
        logger.error(f"Invalid message ID from user {message.from_user.id}: {message.text}")
    except Exception as e:
        await message.reply("Error validating message ID. Please try again or use /cancel.")
        logger.error(f"Unexpected error validating message ID for user {message.from_user.id}: {str(e)}")

async def receive_edit_content(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        logger.warning(f"User mismatch: {message.from_user.id} != {user_data.get('user_id')}")
        return
    logger.info(f"Received edit content from user {message.from_user.id}")
    try:
        if message.text and message.text.lower() == "keep":
            await state.update_data(keep_content=True)
        else:
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
                await message.reply("Unsupported content type. Please send text, photo, video, document, or 'keep'.")
                logger.error(f"Unsupported content type from user {message.from_user.id}")
                await state.finish()
                return
            await state.update_data(content=content, keep_content=False)
        await message.reply(
            "Send the new buttons in the same format as before, or type 'keep' to keep the existing buttons.",
            reply_markup=create_channel_selection_keyboard([], show_back=True, show_close=True)
        )
        await EditState.WaitingForButtons.set()
        logger.info(f"Prompted user {message.from_user.id} for edit buttons")
    except Exception as e:
        await message.reply("Error processing content.")
        logger.error(f"Error in receive_edit_content: {str(e)}")
        await state.finish()

async def receive_edit_buttons(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        logger.warning(f"User mismatch: {message.from_user.id} != {user_data.get('user_id')}")
        return
    current_state = await state.get_state()
    logger.info(f"Received edit buttons from user {message.from_user.id} in state {current_state}: {message.text}")
    logger.debug(f"FSM data: {user_data}")
    try:
        reply_markup = None
        keep_buttons = False
        if message.text.lower() == "keep":
            keep_buttons = True
        elif message.text.lower() != "none":
            reply_markup = create_button_keyboard(message.text, for_preview=True)
        await state.update_data(reply_markup=reply_markup, keep_buttons=keep_buttons)
        if user_data.get("keep_content") and keep_buttons and not reply_markup:
            await message.reply("No changes provided. Please update content or buttons.")
            logger.error(f"No changes provided by user {message.from_user.id}")
            await state.finish()
            return
        content = user_data.get("content") if not user_data.get("keep_content") else {}
        try:
            preview_message = await send_preview(
                message.bot,
                content=content,
                reply_markup=reply_markup,
                chat_id=message.chat.id,
                keep_content=user_data.get("keep_content", False)
            )
            await state.update_data(preview_message_id=preview_message.message_id)
            await message.reply(
                "Preview sent. Please confirm or cancel:",
                reply_markup=create_confirm_keyboard()
            )
            await EditState.WaitingForPreview.set()
            logger.info(f"Sent edit preview to user {message.from_user.id}, preview_message_id={preview_message.message_id}")
        except TelegramAPIError as e:
            await message.reply(
                "Failed to send preview. The channel message ID may be invalid, the post may not exist, "
                "or the bot lacks permission to edit it."
            )
            logger.error(f"TelegramAPIError in receive_edit_buttons: {str(e)}")
            await state.finish()
        except ValueError as e:
            await message.reply("Invalid content or button format. Please try again or use /cancel.")
            logger.error(f"ValueError in receive_edit_buttons: {str(e)}")
            await state.finish()
    except Exception as e:
        await message.reply("Error processing buttons. Please try again or use /cancel.")
        logger.error(f"Error in receive_edit_buttons: {str(e)}")
        await state.finish()

async def receive_post_buttons(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.from_user.id != user_data.get("user_id"):
        logger.warning(f"User mismatch: {message.from_user.id} != {user_data.get('user_id')}")
        return
    current_state = await state.get_state()
    logger.info(f"Received buttons from user {message.from_user.id} in state {current_state}: {message.text}")
    if current_state != PostState.WaitingForButtons.state:
        logger.warning(f"Unexpected state {current_state} for user {message.from_user.id}")
        await message.reply("Bot is in an unexpected state. Please start over with /post or use /cancel.")
        await state.finish()
        return
    content = user_data.get("content")
    if not content:
        await message.reply("Error: No message content found. Please start over with /post.")
        logger.error(f"No content found for user {message.from_user.id}")
        await state.finish()
        return
    try:
        reply_markup = None
        button_text = message.text.strip()
        if button_text.lower() == "none":
            logger.info(f"User {message.from_user.id} chose no buttons")
        else:
            default_buttons = await mongo_db.get_default_buttons(message.from_user.id)
            combined_button_text = button_text
            if default_buttons:
                combined_button_text += "\n" + default_buttons
            reply_markup = create_button_keyboard(combined_button_text, for_preview=True)
            logger.debug(f"Generated preview reply_markup for user {message.from_user.id}, default buttons included: {default_buttons is not None}")
        preview_message = await send_preview(message.bot, content, reply_markup, message.chat.id)
        await state.update_data(preview_message_id=preview_message.message_id, reply_markup=reply_markup)
        await message.reply(
            "Preview sent. Please confirm or cancel:",
            reply_markup=create_confirm_keyboard()
        )
        await PostState.WaitingForPreview.set()
        logger.info(f"Sent preview to user {message.from_user.id}")
    except TelegramAPIError as e:
        await message.reply(f"Error sending preview: {str(e)}")
        logger.error(f"TelegramAPIError in receive_post_buttons: {str(e)}")
        await state.finish()
    except ValueError as e:
        await message.reply("Invalid button format. Please use the specified format or send 'none'.")
        logger.error(f"ValueError in receive_post_buttons: {str(e)}")
        await state.finish()
    except Exception as e:
        await message.reply("Error processing buttons. Please try again or use /cancel.")
        logger.error(f"Unexpected error in receive_post_buttons: {str(e)}")
        await state.finish()

async def handle_edit_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if callback_query.from_user.id != user_data.get("user_id"):
        await callback_query.answer()
        logger.warning(f"User mismatch in edit confirmation: {callback_query.from_user.id} != {user_data.get('user_id')}")
        return
    logger.info(f"Received edit confirmation from user {callback_query.from_user.id}: {callback_query.data}")
    try:
        content = user_data.get("content") if not user_data.get("keep_content") else {}
        reply_markup = user_data.get("reply_markup")
        channel_id = user_data.get("channel_id")
        edit_message_id = user_data.get("edit_message_id")
        preview_message_id = user_data.get("preview_message_id")
        if callback_query.data == "confirm_post":
            await send_to_channel(
                callback_query.bot,
                content=content,
                reply_markup=reply_markup,
                channel_id=channel_id,
                edit_message_id=edit_message_id,
                keep_content=user_data.get("keep_content", False)
            )
            await callback_query.message.reply("Post edited successfully!")
            logger.info(f"Edited post {edit_message_id} in channel {channel_id} by user {callback_query.from_user.id}")
        else:
            await callback_query.message.reply("Edit canceled.")
            logger.info(f"Edit canceled by user {callback_query.from_user.id}")
        try:
            await callback_query.bot.delete_message(chat_id=callback_query.message.chat.id, message_id=preview_message_id)
        except Exception as e:
            logger.warning(f"Failed to delete preview message: {str(e)}")
        await callback_query.message.delete()
        await state.finish()
        await callback_query.answer()
    except TelegramAPIError as e:
        await callback_query.message.reply(
            "Failed to edit the post. The message ID may be invalid, the post may not exist, "
            "or the bot lacks permission."
        )
        logger.error(f"TelegramAPIError in handle_edit_confirmation: {str(e)}")
        await state.finish()
    except Exception as e:
        await callback_query.message.reply("Error processing confirmation.")
        logger.error(f"Unexpected error in handle_edit_confirmation: {str(e)}")
        await state.finish()

async def handle_preview_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if callback_query.from_user.id != user_data.get("user_id"):
        await callback_query.answer()
        logger.warning(f"User mismatch in preview confirmation: {callback_query.from_user.id} != {user_data.get('user_id')}")
        return
    logger.info(f"Received preview confirmation from user {callback_query.from_user.id}: {callback_query.data}")
    content = user_data.get("content")
    reply_markup = user_data.get("reply_markup")
    channel_id = user_data.get("channel_id")
    preview_message_id = user_data.get("preview_message_id")
    try:
        if callback_query.data == "confirm_post":
            await send_to_channel(callback_query.bot, content, reply_markup, channel_id)
            await callback_query.message.reply("Message posted to the channel successfully!")
            logger.info(f"Posted message to channel {channel_id} by user {callback_query.from_user.id}")
        else:
            await callback_query.message.reply("Post canceled.")
            logger.info(f"Post canceled by user {callback_query.from_user.id}")
        try:
            await callback_query.bot.delete_message(chat_id=callback_query.message.chat.id, message_id=preview_message_id)
        except Exception as e:
            logger.warning(f"Failed to delete preview message: {str(e)}")
        await callback_query.message.delete()
        await state.finish()
        await callback_query.answer()
    except TelegramAPIError as e:
        await callback_query.message.reply(f"Error posting message: {str(e)}")
        logger.error(f"TelegramAPIError in handle_preview_confirmation: {str(e)}")
        await state.finish()
    except Exception as e:
        await callback_query.message.reply("Error processing confirmation.")
        logger.error(f"Unexpected error in handle_preview_confirmation: {str(e)}")
        await state.finish()

async def button_callback(callback_query: types.CallbackQuery):
    logger.info(f"Received button callback from user {callback_query.from_user.id}: {callback_query.data}")
    try:
        if callback_query.data.startswith(("popup:", "alert:")):
            action, text = callback_query.data.split(":", 1)
            if action == "popup":
                await callback_query.answer(text=text, show_alert=False)
            elif action == "alert":
                await callback_query.answer(text=text, show_alert=True)
            logger.info(f"Processed {action} callback for user {callback_query.from_user.id}")
    except Exception as e:
        await callback_query.answer("Error processing button.")
        logger.error(f"Error in button_callback: {str(e)}")

async def cancel_command(message: types.Message, state: FSMContext):
    logger.info(f"Received /cancel from user {message.from_user.id}")
    await state.finish()
    await message.reply("Operation canceled. Use /start to begin again.")
    logger.info(f"User {message.from_user.id} canceled operation")

async def fallback_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    user_data = await state.get_data()
    logger.warning(
        f"Unhandled message from user {message.from_user.id} in state {current_state}: "
        f"{message.text or message.content_type}, FSM data: {user_data}, "
        f"Raw message: {message.to_python()}, Entities: {message.entities}"
    )
    await message.reply("Unexpected input. Please continue with the current operation or use /cancel to reset.")

def register_handlers(dp: Dispatcher):
    logger.info("Registering handlers")
    dp.register_message_handler(start_command, commands=["start"])
    dp.register_message_handler(help_command, commands=["help"])
    dp.register_message_handler(add_channel_command, commands=["add"])
    dp.register_message_handler(post_command, commands=["post"])
    dp.register_message_handler(edit_command, commands=["edit"])
    dp.register_message_handler(broadcast_command, commands=["broadcast"])
    dp.register_message_handler(set_default_buttons_command, commands=["setdefaultbtns"])
    dp.register_message_handler(cancel_command, commands=["cancel"])
    dp.register_callback_query_handler(
        start_button_callback,
        lambda c: c.data in [
            "start_post",
            "start_edit",
            "start_broadcast",
            "start_default_buttons",
            "start_my_channels",
            "start_help",
            "close_message",
            "back_to_start"
        ]
    )
    dp.register_callback_query_handler(
        default_buttons_callback,
        lambda c: c.data in ["set_default_buttons", "clear_default_buttons", "back_to_start"]
    )
    dp.register_callback_query_handler(
        my_channels_callback,
        lambda c: c.data.startswith(("delete_channel:", "view_channel:")) or c.data in ["clear_all_channels", "back_to_start"]
    )
    dp.register_callback_query_handler(
        select_channel,
        lambda c: c.data.startswith("select_channel:"),
        state=[PostState.WaitingForChannel, EditState.WaitingForChannel]
    )
    dp.register_callback_query_handler(
        back_action,
        lambda c: c.data == "back_action",
        state=[
            PostState.WaitingForMessage,
            PostState.WaitingForButtons,
            PostState.WaitingForPreview,
            EditState.WaitingForMessageId,
            EditState.WaitingForContent,
            EditState.WaitingForButtons,
            EditState.WaitingForPreview,
            BroadcastState.WaitingForMessage,
            BroadcastState.WaitingForButtons,
            BroadcastState.WaitingForPreview,
            DefaultButtonsState.WaitingForButtons
        ]
    )
    dp.register_callback_query_handler(
        cancel_action,
        lambda c: c.data == "cancel_action",
        state="*"
    )
    dp.register_callback_query_handler(
        close_message,
        lambda c: c.data == "close_message",
        state="*"
    )
    dp.register_callback_query_handler(debug_callback)
    dp.register_message_handler(
        receive_post_message,
        content_types=[
            types.ContentType.TEXT,
            types.ContentType.PHOTO,
            types.ContentType.VIDEO,
            types.ContentType.DOCUMENT
        ],
        state=PostState.WaitingForMessage
    )
    dp.register_message_handler(
        receive_post_buttons,
        content_types=[types.ContentType.TEXT],
        state=PostState.WaitingForButtons
    )
    dp.register_message_handler(receive_message_id, state=EditState.WaitingForMessageId)
    dp.register_message_handler(
        receive_edit_content,
        content_types=[
            types.ContentType.TEXT,
            types.ContentType.PHOTO,
            types.ContentType.VIDEO,
            types.ContentType.DOCUMENT
        ],
        state=EditState.WaitingForContent
    )
    dp.register_message_handler(
        receive_edit_buttons,
        content_types=[types.ContentType.TEXT],
        state=EditState.WaitingForButtons
    )
    dp.register_message_handler(
        receive_broadcast_message,
        content_types=[
            types.ContentType.TEXT,
            types.ContentType.PHOTO,
            types.ContentType.VIDEO,
            types.ContentType.DOCUMENT
        ],
        state=BroadcastState.WaitingForMessage
    )
    dp.register_message_handler(
        receive_broadcast_buttons,
        content_types=[types.ContentType.TEXT],
        state=BroadcastState.WaitingForButtons
    )
    dp.register_message_handler(
        receive_default_buttons,
        content_types=[types.ContentType.TEXT],
        state=DefaultButtonsState.WaitingForButtons
    )
    dp.register_callback_query_handler(
        handle_preview_confirmation,
        lambda c: c.data in ["confirm_post", "cancel_action"],
        state=PostState.WaitingForPreview
    )
    dp.register_callback_query_handler(
        handle_edit_confirmation,
        lambda c: c.data in ["confirm_post", "cancel_action"],
        state=EditState.WaitingForPreview
    )
    dp.register_callback_query_handler(
        handle_broadcast_confirmation,
        lambda c: c.data in ["confirm_post", "cancel_action"],
        state=BroadcastState.WaitingForPreview
    )
    dp.register_callback_query_handler(
        button_callback,
        lambda c: c.data.startswith(("popup:", "alert:"))
    )
    dp.register_message_handler(fallback_handler)
