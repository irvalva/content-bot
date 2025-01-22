import logging
from telegram import Update, ReplyKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, ContextTypes

# Configuración de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Diccionario para almacenar configuraciones de reemplazo por usuario
user_data = {}

# Estados de la conversación
TEXT_TO_REPLACE, NEW_TEXT = range(2)

# Función para iniciar el bot con un menú de botones
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        ["🔄 Configurar Reemplazo"],
        ["❌ Cancelar"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_text(
        "👋 ¡Bienvenido! Usa el menú de opciones para comenzar.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

# Capturar texto a reemplazar
async def recibir_texto(update: Update, context: CallbackContext) -> int:
    text = update.message.text

    if text == "🔄 Configurar":
        await update.message.reply_text("✏️ Escribe la palabra o frase que deseas reemplazar:")
        return TEXT_TO_REPLACE

    elif text == "❌ Reiniciar":
        user_data.pop(update.message.from_user.id, None)
        await update.message.reply_text("❌ Reemplazo cancelado. Escribe /start para volver al menú.")
        return ConversationHandler.END

# Guardar el texto a reemplazar y pedir el nuevo texto
async def set_text_to_replace(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_data[user_id] = {'text_to_replace': update.message.text}
    await update.message.reply_text(f"Perfecto. ¿Por qué texto deseas reemplazar '{update.message.text}'?")
    return NEW_TEXT

# Guardar el nuevo texto y finalizar configuración
async def set_new_text(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_data[user_id]['new_text'] = update.message.text
    await update.message.reply_text("✅ ¡Listo! Ahora reenvíame mensajes y los modificaré según tu configuración.")
    return ConversationHandler.END

# Procesar mensajes reenviados y aplicar el reemplazo
async def process_posts(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        return  # Ignorar si no hay configuración de reemplazo

    text_to_replace = user_data[user_id]['text_to_replace']
    new_text = user_data[user_id]['new_text']

    # Procesar álbumes (media group)
    if update.message.media_group_id:
        media_group = update.message.media_group_id
        media_list = context.bot_data.get(media_group, [])

        media_list.append(update.message)
        context.bot_data[media_group] = media_list

        # Esperar hasta recibir todas las imágenes del álbum
        if len(media_list) < update.message.media_group_size:
            return

        # Procesar el álbum
        transformed_media = []
        for media in media_list:
            if media.caption and text_to_replace in media.caption:
                new_caption = media.caption.replace(text_to_replace, new_text)
                if media.photo:
                    transformed_media.append(InputMediaPhoto(media.photo[-1].file_id, caption=new_caption))
                elif media.video:
                    transformed_media.append(InputMediaVideo(media.video.file_id, caption=new_caption))
            else:
                # Si el caption no cambia, agregar sin modificaciones
                if media.photo:
                    transformed_media.append(InputMediaPhoto(media.photo[-1].file_id, caption=media.caption))
                elif media.video:
                    transformed_media.append(InputMediaVideo(media.video.file_id, caption=media.caption))

        # Enviar el álbum transformado
        await context.bot.send_media_group(chat_id=update.message.chat_id, media=transformed_media)
        del context.bot_data[media_group]  # Limpiar datos del álbum
        return

    # Procesar mensajes individuales (texto, fotos, videos)
    original_text = update.message.text or update.message.caption
    if original_text and text_to_replace in original_text:
        replaced_text = original_text.replace(text_to_replace, new_text)

        if update.message.photo:
            await context.bot.send_photo(chat_id=update.message.chat_id, photo=update.message.photo[-1].file_id, caption=replaced_text)
        elif update.message.video:
            await context.bot.send_video(chat_id=update.message.chat_id, video=update.message.video.file_id, caption=replaced_text)
        elif update.message.text:
            await update.message.reply_text(replaced_text)

        # Eliminar mensaje original
        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception:
            pass

# Configuración del bot
def main():
    TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"
    application = Application.builder().token(TOKEN).build()

    # Manejo de conversaciones
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TEXT_TO_REPLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_text_to_replace)],
            NEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_text)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_texto))
    application.add_handler(MessageHandler(filters.FORWARDED & filters.ALL, process_posts))

    application.run_polling()

if __name__ == "__main__":
    main()
