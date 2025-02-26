import logging
import asyncio
import re
from telegram import (
    Update,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAnimation,
    MessageEntity,
)
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Configuración del logging (opcional)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Diccionario para almacenar la configuración de cada usuario.
# Cada usuario define:
#   "detect": la palabra a detectar.
#   "replace": la palabra de reemplazo.
user_config = {}

def adjust_entities(original: str, new_text: str, entities, detect: str, replace: str):
    """
    Ajusta los offsets y longitudes de las entities en función de la diferencia
    de longitud entre 'detect' y 'replace'.
    Nota: Solución sencilla; si la entity no toca el detect, no se modifica.
    """
    diff = len(replace) - len(detect)
    new_entities = []
    for ent in entities:
        new_offset = ent.offset
        new_length = ent.length
        pos = 0
        # Solo se ajustan si detect aparece dentro del rango de la entity.
        while True:
            idx = original.find(detect, pos)
            if idx == -1:
                break
            if ent.offset <= idx < ent.offset + ent.length:
                new_length += diff
            pos = idx + len(detect)
        ent_dict = ent.to_dict()
        ent_dict["offset"] = new_offset
        ent_dict["length"] = new_length
        new_entities.append(MessageEntity.de_json(ent_dict, None))
    return new_entities

def filter_entities(new_text: str, entities, replaced: str):
    """
    Filtra y elimina de la lista de entities aquellas cuyo rango en el nuevo texto
    incluya (total o parcialmente) la cadena reemplazada.
    De esta forma, el texto resultante que provenga del reemplazo no conserva formato.
    """
    filtered = []
    for ent in entities:
        ent_text = new_text[ent.offset:ent.offset + ent.length]
        # Si la cadena reemplazada aparece en el texto de la entity, descartarla.
        if replaced in ent_text:
            continue
        filtered.append(ent)
    return filtered

# Comando: /setdetect <palabra>
async def setdetect(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /setdetect <palabra>")
        return
    detect = " ".join(context.args)
    user_config.setdefault(update.message.from_user.id, {})["detect"] = detect
    await update.message.reply_text(f"Palabra a detectar configurada: {detect}")

# Comando: /setreplace <palabra>
async def setreplace(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /setreplace <palabra>")
        return
    replace = " ".join(context.args)
    user_config.setdefault(update.message.from_user.id, {})["replace"] = replace
    await update.message.reply_text(f"Palabra de reemplazo configurada: {replace}")

# Comando: /reset
async def reset(update: Update, context: CallbackContext) -> None:
    user_config.pop(update.message.from_user.id, None)
    await update.message.reply_text("Configuración reiniciada.")

# Función para procesar mensajes y álbumes
async def process_posts(update: Update, context: CallbackContext) -> None:
    config = user_config.get(update.message.from_user.id)
    if not config:
        return
    detect = config.get("detect")
    replace = config.get("replace")
    if not detect or not replace:
        return

    # --- Procesamiento de álbumes (media_group) ---
    if update.message.media_group_id:
        group_id = update.message.media_group_id
        group = context.bot_data.setdefault(group_id, [])
        group.append(update.message)
        if "scheduled_album_tasks" not in context.bot_data:
            context.bot_data["scheduled_album_tasks"] = {}
        if group_id in context.bot_data["scheduled_album_tasks"]:
            return  # Ya se programó la tarea para este grupo

        async def process_album():
            await asyncio.sleep(1)  # Espera para recibir todas las partes del álbum
            album = context.bot_data.pop(group_id, [])
            context.bot_data["scheduled_album_tasks"].pop(group_id, None)
            media_list = []
            for msg in album:
                if msg.caption:
                    new_caption = msg.caption.replace(detect, replace) if detect in msg.caption else msg.caption
                    if msg.caption_entities:
                        new_entities = adjust_entities(msg.caption, new_caption, msg.caption_entities, detect, replace)
                        new_entities = filter_entities(new_caption, new_entities, replace)
                    else:
                        new_entities = None
                else:
                    new_caption, new_entities = None, None

                if msg.photo:
                    media_list.append(
                        InputMediaPhoto(msg.photo[-1].file_id, caption=new_caption, caption_entities=new_entities)
                    )
                elif msg.video:
                    media_list.append(
                        InputMediaVideo(msg.video.file_id, caption=new_caption, caption_entities=new_entities)
                    )
                elif hasattr(msg, "animation") and msg.animation is not None:
                    media_list.append(
                        InputMediaAnimation(msg.animation.file_id, caption=new_caption, caption_entities=new_entities)
                    )
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

    # --- Procesamiento de mensajes individuales ---
    if update.message.text:
        original = update.message.text
        new_text = original.replace(detect, replace)
        if update.message.entities:
            new_entities = adjust_entities(original, new_text, update.message.entities, detect, replace)
            new_entities = filter_entities(new_text, new_entities, replace)
        else:
            new_entities = None
        await update.message.reply_text(new_text, entities=new_entities)
    elif update.message.photo:
        caption = update.message.caption or ""
        new_caption = caption.replace(detect, replace) if detect in caption else caption
        if update.message.caption_entities:
            new_entities = adjust_entities(caption, new_caption, update.message.caption_entities, detect, replace)
            new_entities = filter_entities(new_caption, new_entities, replace)
        else:
            new_entities = None
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=update.message.photo[-1].file_id,
            caption=new_caption,
            caption_entities=new_entities,
        )
    elif update.message.video:
        caption = update.message.caption or ""
        new_caption = caption.replace(detect, replace) if detect in caption else caption
        if update.message.caption_entities:
            new_entities = adjust_entities(caption, new_caption, update.message.caption_entities, detect, replace)
            new_entities = filter_entities(new_caption, new_entities, replace)
        else:
            new_entities = None
        await context.bot.send_video(
            chat_id=update.message.chat_id,
            video=update.message.video.file_id,
            caption=new_caption,
            caption_entities=new_entities,
        )
    elif update.message.animation:
        caption = update.message.caption or ""
        new_caption = caption.replace(detect, replace) if detect in caption else caption
        if update.message.caption_entities:
            new_entities = adjust_entities(caption, new_caption, update.message.caption_entities, detect, replace)
            new_entities = filter_entities(new_caption, new_entities, replace)
        else:
            new_entities = None
        await context.bot.send_animation(
            chat_id=update.message.chat_id,
            animation=update.message.animation.file_id,
            caption=new_caption,
            caption_entities=new_entities,
        )
    else:
        try:
            await context.bot.copy_message(
                chat_id=update.message.chat_id,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id,
            )
        except Exception:
            pass

    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
    except Exception:
        pass

def main():
    TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # Reemplaza con el token real de tu bot
    app = Application.builder().token(TOKEN).build()

    # Registrar comandos
    app.add_handler(CommandHandler("setdetect", setdetect))
    app.add_handler(CommandHandler("setreplace", setreplace))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.ALL, process_posts))

    # Inicia el bot en modo polling (se ejecuta indefinidamente)
    app.run_polling()

if __name__ == "__main__":
    main()
