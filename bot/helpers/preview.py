# © 2025 FtKrishna. All rights reserved.
# Channel  : https://t.me/NxMirror
# Contact  : @FTKrshna

import asyncio
from bot.logger import setup_logger
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from aiogram.utils.exceptions import TelegramAPIError
from config import DELETE_TIME

logger = setup_logger(__name__)

async def send_preview(
    bot: Bot,
    content: dict,
    reply_markup: InlineKeyboardMarkup,
    chat_id: int,
    edit_message_id: int = None,
    keep_content: bool = False
):
    logger.info(
        f"Sending preview to chat_id={chat_id}, edit_message_id={edit_message_id}, "
        f"keep_content={keep_content}, content={content}"
    )
    try:
        if keep_content:
            message = await bot.send_message(
                chat_id=chat_id,
                text="Preview of existing content (content unchanged). Buttons updated below.",
                reply_markup=reply_markup
            )
            logger.info(f"Placeholder preview sent to chat_id={chat_id}, message_id={message.message_id}")
            return message

        if not content or "type" not in content:
            logger.error(f"Invalid content provided: {content}")
            raise ValueError("Content is empty or missing 'type' key")

        if content["type"] == "text":
            message = await bot.send_message(
                chat_id=chat_id,
                text=content["text"],
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
        elif content["type"] == "photo":
            message = await bot.send_photo(
                chat_id=chat_id,
                photo=content["file_id"],
                caption=content.get("caption", ""),
                reply_markup=reply_markup
            )
        elif content["type"] == "video":
            message = await bot.send_video(
                chat_id=chat_id,
                video=content["file_id"],
                caption=content.get("caption", ""),
                reply_markup=reply_markup
            )
        elif content["type"] == "document":
            message = await bot.send_document(
                chat_id=chat_id,
                document=content["file_id"],
                caption=content.get("caption", ""),
                reply_markup=reply_markup
            )
        else:
            raise ValueError(f"Unsupported content type: {content['type']}")

        logger.info(f"Preview sent successfully to chat_id={chat_id}, message_id={message.message_id}")
        return message

    except TelegramAPIError as e:
        logger.error(f"Error sending preview (edit_message_id={edit_message_id}): {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_preview: {str(e)}")
        raise


async def send_to_channel(
    bot: Bot,
    content: dict,
    reply_markup: InlineKeyboardMarkup,
    channel_id: int,
    edit_message_id: int = None,
    keep_content: bool = False,
    delete_after: int = DELETE_TIME   # ⬅️ default from info.py
):
    logger.info(
        f"Sending to channel_id={channel_id}, edit_message_id={edit_message_id}, "
        f"keep_content={keep_content}, delete_after={delete_after}, content={content}"
    )
    try:
        # --- Edit only buttons ---
        if edit_message_id and keep_content:
            message = await bot.edit_message_reply_markup(
                chat_id=channel_id,
                message_id=edit_message_id,
                reply_markup=reply_markup
            )
            logger.info(f"Edited message {edit_message_id} in channel {channel_id}")
            return message

        # --- Edit full message ---
        elif edit_message_id:
            if content["type"] == "text":
                message = await bot.edit_message_text(
                    chat_id=channel_id,
                    message_id=edit_message_id,
                    text=content["text"],
                    reply_markup=reply_markup,
                    disable_web_page_preview=False
                )
            elif content["type"] == "photo":
                message = await bot.edit_message_media(
                    chat_id=channel_id,
                    message_id=edit_message_id,
                    media=InputMediaPhoto(
                        media=content["file_id"],
                        caption=content.get("caption", "")
                    ),
                    reply_markup=reply_markup
                )
            elif content["type"] == "video":
                message = await bot.edit_message_media(
                    chat_id=channel_id,
                    message_id=edit_message_id,
                    media=InputMediaVideo(
                        media=content["file_id"],
                        caption=content.get("caption", "")
                    ),
                    reply_markup=reply_markup
                )
            elif content["type"] == "document":
                message = await bot.edit_message_media(
                    chat_id=channel_id,
                    message_id=edit_message_id,
                    media=InputMediaDocument(
                        media=content["file_id"],
                        caption=content.get("caption", "")
                    ),
                    reply_markup=reply_markup
                )
            else:
                raise ValueError(f"Unsupported content type: {content['type']}")
            logger.info(f"Edited message {edit_message_id} in channel {channel_id}")
        else:
            # --- Send new message ---
            if content["type"] == "text":
                message = await bot.send_message(
                    chat_id=channel_id,
                    text=content["text"],
                    reply_markup=reply_markup,
                    disable_web_page_preview=False
                )
            elif content["type"] == "photo":
                message = await bot.send_photo(
                    chat_id=channel_id,
                    photo=content["file_id"],
                    caption=content.get("caption", ""),
                    reply_markup=reply_markup
                )
            elif content["type"] == "video":
                message = await bot.send_video(
                    chat_id=channel_id,
                    video=content["file_id"],
                    caption=content.get("caption", ""),
                    reply_markup=reply_markup
                )
            elif content["type"] == "document":
                message = await bot.send_document(
                    chat_id=channel_id,
                    document=content["file_id"],
                    caption=content.get("caption", ""),
                    reply_markup=reply_markup
                )
            else:
                raise ValueError(f"Unsupported content type: {content['type']}")
            logger.info(f"Sent new message to channel {channel_id}, message_id={message.message_id}")

        # --- Auto-delete if requested ---
        if delete_after:
            async def auto_delete():
                try:
                    await asyncio.sleep(delete_after)
                    await bot.delete_message(chat_id=channel_id, message_id=message.message_id)
                    logger.info(f"Deleted message {message.message_id} from channel {channel_id} after {delete_after}s")
                except Exception as e:
                    logger.error(f"Failed to delete message {message.message_id}: {e}")

            asyncio.create_task(auto_delete())

        return message

    except TelegramAPIError as e:
        logger.error(f"Error sending to channel (edit_message_id={edit_message_id}): {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_to_channel: {str(e)}")
        raise
