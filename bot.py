import logging
from telegram import Update, InputMediaPhoto, InputMediaVideo, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

# Configuración de logging (opcional, para depuración)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Diccionario para almacenar la configuración de cada usuario.
# Se espera que cada usuario configure dos parámetros:
#   "detect": la palabra a detectar.
#   "replace": la palabra de reemplazo.
user_config = {}

# ----- COMANDOS DE CONFIGURACIÓN -----

async def start(update: Update, context: CallbackContext) -> None:
    """Muestra el menú de opciones."""
    menu = (
        "Opciones:\n"
        "/setdetect <palabra> - Establecer palabra a detectar\n"
        "/setreplace <palabra> - Establecer palabra de reemplazo\n"
        "/reset - Reiniciar configuración\n"
        "/detener - Detener\n\n"
        "Envía un post (texto, foto, video o álbum) para procesarlo."
    )
    await update.message.reply_text(menu)

async def setdetect(update: Update, context: CallbackContext) -> None:
    """Configura la palabra a detectar."""
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("Uso: /setdetect <palabra>")
        return
    detect_word = " ".join(context.args)
    if user_id not in user_config:
        user_config[user_id] = {}
    user_config[user_id]["detect"] = detect_word
    await update.message.reply_text(f"Palabra a detectar configurada: {detect_word}")

async def setreplace(update: Update, context: CallbackContext) -> None:
    """Configura la palabra de reemplazo."""
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("Uso: /setreplace <palabra>")
        return
    replace_word = " ".join(context.args)
    if user_id not in user_config:
        user_config[user_id] = {}
    user_config[user_id]["replace"] = replace_word
    await update.message.reply_text(f"Palabra de reemplazo configurada: {replace_word}")

async def reset(update: Update, context: CallbackContext) -> None:
    """Reinicia la configuración del usuario."""
    user_id = update.message.from_user.id
    if user_id in user_config:
        del user_config[user_id]
    await update.message.reply_text("Configuración reiniciada.")

async def detener(update: Update, context: CallbackContext) -> None:
    """Opción de detener (sólo informa)."""
    await update.message.reply_text("Proceso detenido.")

# ----- PROCESAMIENTO DE POSTS -----

async def process_posts(update: Update, context: CallbackContext) -> None:
    """
    Procesa los mensajes recibidos (individuales o álbumes)
    y realiza el reemplazo en el texto o caption, conservando las entidades de formato.
    """
    user_id = update.message.from_user.id
    # Si el usuario no configuró detect y replace, no hacemos nada.
    if user_id not in user_config:
        return
    detect = user_config[user_id].get("detect")
    replace = user_config[user_id].get("replace")
    if not detect or not replace:
        return

    # ----- PROCESAMIENTO DE ÁLBUMES -----
    if update.message.media_group_id:
        group_id = update.message.media_group_id
        group = context.bot_data.get(group_id, [])
        group.append(update.message)
        context.bot_data[group_id] = group
        if len(group) < update.message.media_group_size:
            return  # Esperamos a recibir todos los mensajes del álbum

        transformed_media = []
        for msg in group:
            if msg.caption:
                # Se reemplaza el texto en el caption
                new_caption = msg.caption.replace(detect, replace) if detect in msg.caption else msg.caption
                # Se preservan las entidades de formato (aunque los offsets podrían variar si las longitudes cambian)
                entities = msg.caption_entities
            else:
                new_caption = None
                entities = None

            if msg.photo:
                transformed_media.append(
                    InputMediaPhoto(msg.photo[-1].file_id, caption=new_caption, caption_entities=entities)
                )
            elif msg.video:
                transformed_media.append(
                    InputMediaVideo(msg.video.file_id, caption=new_caption, caption_entities=entities)
                )
            else:
                # Se pueden agregar otros tipos de medios si es necesario.
                pass

        await context.bot.send_media_group(chat_id=update.message.chat_id, media=transformed_media)
        # Se elimina cada mensaje original del álbum
        for msg in group:
            try:
                await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
            except Exception:
                pass
        del context.bot_data[group_id]
        return

    # ----- PROCESAMIENTO DE MENSAJES INDIVIDUALES -----
    # Si es un mensaje de texto
    if update.message.text:
        original_text = update.message.text
        new_text = original_text.replace(detect, replace) if detect in original_text else original_text
        # Se conserva el formato (entidades)
        entities = update.message.entities
        await update.message.reply_text(new_text, entities=entities)
    # Si es una foto
    elif update.message.photo:
        caption = update.message.caption if update.message.caption else None
        if caption:
            new_caption = caption.replace(detect, replace) if detect in caption else caption
            entities = update.message.caption_entities
        else:
            new_caption = None
            entities = None
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=update.message.photo[-1].file_id,
            caption=new_caption,
            caption_entities=entities,
        )
    # Si es un video
    elif update.message.video:
        caption = update.message.caption if update.message.caption else None
        if caption:
            new_caption = caption.replace(detect, replace) if detect in caption else caption
            entities = update.message.caption_entities
        else:
            new_caption = None
            entities = None
        await context.bot.send_video(
            chat_id=update.message.chat_id,
            video=update.message.video.file_id,
            caption=new_caption,
            caption_entities=entities,
        )
    else:
        try:
            # Para otros tipos de mensajes, se reenvía sin modificación.
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

# ----- CONFIGURACIÓN Y EJECUCIÓN DEL BOT -----

def main():
    TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # Reemplaza con el token real de tu bot
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setdetect", setdetect))
    app.add_handler(CommandHandler("setreplace", setreplace))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("detener", detener))
    app.add_handler(MessageHandler(filters.ALL, process_posts))

    # Opcional: Establecer el menú de comandos para que aparezcan en Telegram al escribir "/"
    commands = [
        BotCommand("start", "Iniciar"),
        BotCommand("setdetect", "Config. detect"),
        BotCommand("setreplace", "Config. reemplazo"),
        BotCommand("reset", "Reiniciar"),
        BotCommand("detener", "Detener"),
    ]
    async def set_bot_commands(app):
        await app.bot.set_my_commands(commands)
    app.job_queue.run_once(lambda ctx: set_bot_commands(app), when=0)

    app.run_polling()

if __name__ == "__main__":
    main()
