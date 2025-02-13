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

# Configuración de logging para depuración (opcional)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados de la conversación para configurar las palabras
DETECT, REPLACE = range(2)

# Diccionario para almacenar la configuración de cada usuario
user_config = {}

# --------- Comandos de Configuración ---------

# /start: Inicia la configuración preguntando la palabra a detectar y luego la de reemplazo
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

# /detener: Cancela el proceso de configuración en curso
async def detener(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Proceso detenido.")
    return ConversationHandler.END

# /reset: Reinicia la configuración (borra las palabras definidas)
async def reset(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in user_config:
        del user_config[user_id]
    await update.message.reply_text("Reset realizado. Usa /start para configurar.")

# --------- Procesamiento de Mensajes ---------

# Este handler procesa los mensajes enviados y realiza el reemplazo
async def process_posts(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    # Si el usuario no ha configurado palabras, ignoramos el mensaje
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

        # Esperar a recibir todos los mensajes del álbum
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
        # Enviar el álbum transformado
        await context.bot.send_media_group(chat_id=update.message.chat_id, media=transformed_media)
        # Eliminar los mensajes originales
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

    # Eliminar el mensaje original
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
    except Exception:
        pass

# --------- Configuración y Ejecución del Bot ---------

def main():
    TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # Reemplaza con el token real de tu bot
    application = Application.builder().token(TOKEN).build()

    # Configurar el flujo de conversación para /start
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

    # Nota:
    # Si deseas que las opciones aparezcan en el menú de Telegram (al presionar "/"),
    # puedes configurarlas manualmente en BotFather o, alternativamente,
    # instalar el JobQueue (pip install "python-telegram-bot[job-queue]")
    # y agregar el código para set_my_commands. En esta versión se ha omitido para evitar errores.

    application.run_polling()

if __name__ == "__main__":
    main()
