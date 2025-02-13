import logging
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

# Configuración de logging (opcional)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Diccionario para almacenar la configuración de cada usuario.
# Cada usuario debe configurar:
#   "detect": la palabra a detectar.
#   "replace": la palabra de reemplazo.
user_config = {}

# ----- COMANDOS DE CONFIGURACIÓN Y MENÚ -----

async def start(update: Update, context: CallbackContext) -> None:
    """Muestra el menú de opciones."""
    menu = (
        "Opciones:\n"
        "/setdetect <palabra> - Configurar palabra a detectar\n"
        "/setreplace <palabra> - Configurar palabra de reemplazo\n"
        "/reset - Reiniciar configuración\n"
        "/detener - Detener proceso\n\n"
        "Envía un post (texto, foto, video o álbum) para procesarlo."
    )
    await update.message.reply_text(menu)

async def setdetect(update: Update, context: CallbackContext) -> None:
    """Configura la palabra a detectar."""
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("Uso: /setdetect <palabra>")
        return
    detect = " ".join(context.args)
    user_config.setdefault(user_id, {})["detect"] = detect
    await update.message.reply_text(f"Palabra a detectar configurada: {detect}")

async def setreplace(update: Update, context: CallbackContext) -> None:
    """Configura la palabra de reemplazo."""
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("Uso: /setreplace <palabra>")
        return
    replace = " ".join(context.args)
    user_config.setdefault(user_id, {})["replace"] = replace
    await update.message.reply_text(f"Palabra de reemplazo configurada: {replace}")

async def reset(update: Update, context: CallbackContext) -> None:
    """Reinicia la configuración del usuario."""
    user_id = update.message.from_user.id
    if user_id in user_config:
        del user_config[user_id]
    await update.message.reply_text("Configuración reiniciada.")

async def detener(update: Update, context: CallbackContext) -> None:
    """Informa que se ha detenido el proceso."""
    await update.message.reply_text("Proceso detenido.")

# ----- PROCESAMIENTO DE POSTS -----

async def process_posts(update: Update, context: CallbackContext) -> None:
    """
    Procesa mensajes (individuales o álbumes) y realiza el reemplazo en el texto o caption.
    Se intenta conservar las entidades de formato (por ejemplo, negrita) en la medida de lo posible.
    """
    user_id = update.message.from_user.id
    if user_id not in user_config:
        return

    detect = user_config[user_id].get("detect")
    replace = user_config[user_id].get("replace")
    if not detect or not replace:
        return

    # ----- PROCESAMIENTO DE ÁLBUMES -----
    if update.message.media_group_id:
        group_id = update.message.media_group_id
        group = context.bot_data.setdefault(group_id, [])
        group.append(update.message)
        # Esperamos a recibir todos los mensajes del álbum
        if len(group) < update.message.media_group_size:
            return

        transformed_media = []
        for msg in group:
            if msg.caption:
                new_caption = msg.caption.replace(detect, replace) if detect in msg.caption else msg.caption
                entities = msg.caption_entities
            else:
                new_caption, entities = None, None

            if msg.photo:
                transformed_media.append(
                    InputMediaPhoto(msg.photo[-1].file_id, caption=new_caption, caption_entities=entities)
                )
            elif msg.video:
                transformed_media.append(
                    InputMediaVideo(msg.video.file_id, caption=new_caption, caption_entities=entities)
                )
        await context.bot.send_media_group(chat_id=update.message.chat_id, media=transformed_media)
        # Eliminar los mensajes originales del álbum
        for msg in group:
            try:
                await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
            except Exception:
                pass
        del context.bot_data[group_id]
        return

    # ----- PROCESAMIENTO DE MENSAJES INDIVIDUALES -----
    if update.message.text:
        original = update.message.text
        new_text = original.replace(detect, replace) if detect in original else original
        await update.message.reply_text(new_text, entities=update.message.entities)
    elif update.message.photo:
        caption = update.message.caption if update.message.caption else None
        if caption:
            new_caption = caption.replace(detect, replace) if detect in caption else caption
            entities = update.message.caption_entities
        else:
            new_caption, entities = None, None
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=update.message.photo[-1].file_id,
            caption=new_caption,
            caption_entities=entities,
        )
    elif update.message.video:
        caption = update.message.caption if update.message.caption else None
        if caption:
            new_caption = caption.replace(detect, replace) if detect in caption else caption
            entities = update.message.caption_entities
        else:
            new_caption, entities = None, None
        await context.bot.send_video(
            chat_id=update.message.chat_id,
            video=update.message.video.file_id,
            caption=new_caption,
            caption_entities=entities,
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

# ----- CONFIGURACIÓN Y EJECUCIÓN DEL BOT -----

def main():
    TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # Reemplaza con el token real de tu bot
    app = Application.builder().token(TOKEN).build()

    # Agregar handlers de comandos y mensajes
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setdetect", setdetect))
    app.add_handler(CommandHandler("setreplace", setreplace))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("detener", detener))
    app.add_handler(MessageHandler(filters.ALL, process_posts))

    # Función asíncrona para establecer el menú de comandos
    async def set_commands():
        commands = [
            BotCommand("start", "Iniciar"),
            BotCommand("setdetect", "Config. detect"),
            BotCommand("setreplace", "Config. reemplazo"),
            BotCommand("reset", "Reiniciar"),
            BotCommand("detener", "Detener"),
        ]
        await app.bot.set_my_commands(commands)

    # Ejecuta la configuración de comandos en un event loop separado
    asyncio.run(set_commands())

    # Crea y establece un nuevo event loop para run_polling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling()

if __name__ == "__main__":
    main()
