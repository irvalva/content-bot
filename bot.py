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
    de longitud entre 'detect' y 'replace'. Esta función recorre cada entity
    y, para cada ocurrencia de 'detect' en el texto original, ajusta los offsets.
    
    Nota: Es una solución sencilla y puede no cubrir casos muy complejos.
    """
    diff = len(replace) - len(detect)
    new_entities = []
    for ent in entities:
        new_offset = ent.offset
        new_length = ent.length
        pos = 0
        while True:
            idx = original.find(detect, pos)
            if idx == -1:
                break
            if idx < ent.offset:
                new_offset += diff
            elif ent.offset <= idx < ent.offset + ent.length:
                new_length += diff
            pos = idx + len(detect)
        ent_dict = ent.to_dict()
        ent_dict["offset"] = new_offset
        ent_dict["length"] = new_length
        new_entities.append(MessageEntity.de_json(ent_dict, None))
    return new_entities

def filter_entities(new_text: str, entities, replaced: str):
    """
    Recorre la lista de entities y, para cada ocurrencia de 'replaced' en el nuevo texto,
    recorta la entity que se solape (es decir, ajusta su longitud para que termine en el inicio
    de la ocurrencia). Si una entity queda sin contenido, se elimina.
    """
    occurrences = []
    start = 0
    while True:
        pos = new_text.find(replaced, start)
        if pos == -1:
            break
        occurrences.append((pos, pos + len(replaced)))
        start = pos + len(replaced)
    filtered = []
    for ent in entities:
        ent_start = ent.offset
        ent_end = ent.offset + ent.length
        modified = False
        for occ in occurrences:
            # Si la entity comienza antes de la ocurrencia y se extiende más allá de su inicio...
            if ent_start < occ[0] < ent_end:
                new_length = occ[0] - ent_start
                if new_length > 0:
                    ent_dict = ent.to_dict()
                    ent_dict["length"] = new_length
                    ent = MessageEntity.de_json(ent_dict, None)
                    modified = True
                else:
                    ent = None
                break
            # Si la entity está completamente dentro de la ocurrencia, eliminarla.
            elif ent_start >= occ[0] and ent_end <= occ[1]:
                ent = None
                break
        if ent is not None:
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
            await asyncio.sleep(1)  # Espera 1 segundo para que se reciban todas las partes del álbum
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
                    await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_i
