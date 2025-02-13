import logging
from telegram import Update, InputMediaPhoto, InputMediaVideo, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
)

# Habilitamos logging para ver mensajes de depuración (opcional)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados de la conversación
DETECT, REPLACE = range(2)

# Diccionario para almacenar la configuración de cada usuario
user_config = {}

# ---------- CONVERSACIÓN / START ----------
async def start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Det: ¿Palabra a detectar?")
    return DETECT

async def set_detect(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_config[user_id] = {"detect": update.message.text}
    await update.message.reply_text("Rep: ¿Palabra de reemplazo?")
    return REPLACE

async def set_replace(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_config[user_id]["replace"] = update.message.text
    await update.message.reply_text("Listo. Configuración guardada.")
    return ConversationHandler.END

# Comando para detener/cancelar el proceso en curso
async def detener(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Proceso detenido.")
    return ConversationHandler.END

# ---------- COMANDO / RESET ----------
async def reset(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in user_config:
        del user_config[user_id]
    await update.message.reply_text("Reset realizado. Usa /start para configurar.")

# ---------- PROCESAMIENTO DE MENSAJES ----------
async def process_posts(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    # Si el usuario no tiene configuración, ignorar
    if user_id not in user_config:
        return

    detect = user_config[user_id]["detect"]
    replace = user_config[user_id]["replace"]

    # Procesar álbum (media group)
    if update.message.media_group_id:
        media_group = update.message.media_group_id
        media_list = context.bot_data.get(media_group, [])
        media_list.append(update.message)
        context.bot_data[media_group] = media_list

        # Esperar hasta recibir todos los mensajes del álbum
        if len(media_list) < update.message.media_group_size:
            return

        transformed_media = []
        for media in media_list:
            if media.caption is not None:
                new_caption = media.caption.replace(detect, replace) if detect in media.caption else media.caption
            else:
                new_caption = None

            if media.photo:
                transformed_media.append(
                    InputMediaPhoto(media.photo[-1].file_id, caption=new_caption)
                )
            elif media.video:
                transformed_media.append(
                    InputMediaVideo(media.video.file_id, caption=new_caption)
                )
        # Enviar el álbum transformado (manteniendo el orden)
        await context.bot.send_media_group(chat_id=update.message.chat_id, media=transformed_media)
        # Eliminar cada uno de los mensajes originales
        for media in media_list:
            try:
                await context.bot.delete_message(chat_id=media.chat_id, message_id=media.message_id)
            except Exception:
                pass
        del context.bot_data[media_group]
        return

    # Procesar mensajes individuales
    original_text = update.message.text if update.message.text is not None else update.message.caption
    if original_text is not None:
        replaced_text = original_text.replace(detect, replace) if detect in original_text else original_text
    else:
        replaced_text = None

    if update.message.photo:
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=update.message.photo[-1].file_id,
            caption=replaced_text,
        )
    elif update.message.video:
        await context.bot.send_video(
            chat_id=update.message.chat_id,
            video=update.message.video.file_id,
            caption=replaced_text,
        )
    elif update.message.text:
        await update.message.reply_text(replaced_text)
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

# ---------- CONFIGURACIÓN Y EJECUCIÓN ----------
def main():
    TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g" # Reemplaza con el token de tu bot
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DETECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_detect)],
            REPLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_replace)],
        },
        fallbacks=[CommandHandler("detener", detener)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("detener", detener))
    application.add_handler(MessageHandler(filters.ALL, process_posts))

    # Establece el menú de comandos (texto corto y directo)
    commands = [
        BotCommand("start", "Iniciar"),
        BotCommand("reset", "Reset"),
        BotCommand("detener", "Detener"),
    ]
    async def set_commands(app):
        await app.bot.set_my_commands(commands)

    # Programa la asignación de comandos para que se ejecute al iniciar
    application.job_queue.run_once(lambda context: set_commands(application), when=0)

    application.run_polling()

if __name__ == "__main__":
    main()
