import logging, asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaAnimation, MessageEntity
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración por usuario: "detect" y "replace"
user_config = {}

def process_text(text, entities, detect, replace):
    """
    Busca la primera ocurrencia de `detect` en `text` y la reemplaza por `replace`.
    Luego ajusta la lista de entities para que:
      - Las entities antes de la ocurrencia se conservan.
      - Las entities después se desplazan.
      - Las que se solapan con la ocurrencia se recortan para que no abarquen el reemplazo.
    Devuelve (new_text, new_entities).
    Se asume una única ocurrencia.
    """
    idx = text.find(detect)
    if idx == -1:
        return text, entities
    new_text = text[:idx] + replace + text[idx+len(detect):]
    diff = len(replace) - len(detect)
    new_entities = []
    for ent in entities:
        start = ent.offset
        end = ent.offset + ent.length
        if end <= idx:
            # Entity antes: se mantiene
            new_entities.append(ent)
        elif start >= idx+len(detect):
            # Entity después: se desplaza
            ent_dict = ent.to_dict()
            ent_dict["offset"] = start + diff
            new_entities.append(MessageEntity.de_json(ent_dict, None))
        elif start < idx and end > idx+len(detect):
            # Entity abarca la ocurrencia: se recorta para que termine en idx
            new_length = idx - start
            if new_length > 0:
                ent_dict = ent.to_dict()
                ent_dict["length"] = new_length
                new_entities.append(MessageEntity.de_json(ent_dict, None))
        elif start < idx and end > idx:
            # Entity que termina en medio de detect: recortar para que termine en idx
            new_length = idx - start
            if new_length > 0:
                ent_dict = ent.to_dict()
                ent_dict["length"] = new_length
                new_entities.append(MessageEntity.de_json(ent_dict, None))
        # Entities que empiezan dentro del detect se descartan.
    return new_text, new_entities

async def setdetect(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /setdetect <palabra>")
        return
    detect = " ".join(context.args)
    user_config.setdefault(update.message.from_user.id, {})["detect"] = detect
    await update.message.reply_text(f"Palabra a detectar configurada: {detect}")

async def setreplace(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /setreplace <palabra>")
        return
    replace = " ".join(context.args)
    user_config.setdefault(update.message.from_user.id, {})["replace"] = replace
    await update.message.reply_text(f"Palabra de reemplazo configurada: {replace}")

async def reset(update: Update, context: CallbackContext) -> None:
    user_config.pop(update.message.from_user.id, None)
    await update.message.reply_text("Configuración reiniciada.")

async def process_posts(update: Update, context: CallbackContext) -> None:
    config = user_config.get(update.message.from_user.id)
    if not config:
        return
    detect = config.get("detect")
    replace = config.get("replace")
    if not detect or not replace:
        return

    # Procesamiento de álbumes
    if update.message.media_group_id:
        group_id = update.message.media_group_id
        group = context.bot_data.setdefault(group_id, [])
        group.append(update.message)
        if "scheduled_album_tasks" not in context.bot_data:
            context.bot_data["scheduled_album_tasks"] = {}
        if group_id in context.bot_data["scheduled_album_tasks"]:
            return
        async def process_album():
            await asyncio.sleep(1)
            album = context.bot_data.pop(group_id, [])
            context.bot_data["scheduled_album_tasks"].pop(group_id, None)
            media_list = []
            for msg in album:
                if msg.caption:
                    orig = msg.caption
                    new_caption, new_entities = process_text(orig, msg.caption_entities or [], detect, replace)
                else:
                    new_caption, new_entities = None, None
                if msg.photo:
                    media_list.append(InputMediaPhoto(msg.photo[-1].file_id, caption=new_caption, caption_entities=new_entities))
                elif msg.video:
                    media_list.append(InputMediaVideo(msg.video.file_id, caption=new_caption, caption_entities=new_entities))
                elif hasattr(msg, "animation") and msg.animation is not None:
                    media_list.append(InputMediaAnimation(msg.animation.file_id, caption=new_caption, caption_entities=new_entities))
            if media_list:
                await context.bot.send_media_group(chat_id=update.message.chat_id, media=media_list)
            for msg in album:
                try:
                    await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
                except Exception:
                    pass
        task = asyncio.create_task(process_album())
        context.bot_data["scheduled_album_tasks"][group_id] = task
        return

    # Procesamiento individual
    if update.message.text:
        orig = update.message.text
        new_text, new_entities = process_text(orig, update.message.entities or [], detect, replace)
        await update.message.reply_text(new_text, entities=new_entities)
    elif update.message.photo:
        caption = update.message.caption or ""
        new_caption, new_entities = process_text(caption, update.message.caption_entities or [], detect, replace)
        await context.bot.send_photo(chat_id=update.message.chat_id, photo=update.message.photo[-1].file_id, caption=new_caption, caption_entities=new_entities)
    elif update.message.video:
        caption = update.message.caption or ""
        new_caption, new_entities = process_text(caption, update.message.caption_entities or [], detect, replace)
        await context.bot.send_video(chat_id=update.message.chat_id, video=update.message.video.file_id, caption=new_caption, caption_entities=new_entities)
    elif update.message.animation:
        caption = update.message.caption or ""
        new_caption, new_entities = process_text(caption, update.message.caption_entities or [], detect, replace)
        await context.bot.send_animation(chat_id=update.message.chat_id, animation=update.message.animation.file_id, caption=new_caption, caption_entities=new_entities)
    else:
        try:
            await context.bot.copy_message(chat_id=update.message.chat_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception:
            pass
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
    except Exception:
        pass

def main():
    TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("setdetect", setdetect))
    app.add_handler(CommandHandler("setreplace", setreplace))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.ALL, process_posts))
    app.run_polling()

if __name__ == "__main__":
    main()
