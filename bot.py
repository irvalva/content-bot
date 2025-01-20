from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler

# Estados del bot para el flujo de conversación
TEXT_TO_REPLACE, NEW_TEXT, WAITING_FOR_POSTS = range(3)

# ID del usuario autorizado (solo tú puedes usar el bot)
AUTHORIZED_USER_ID = 1376071083  # Tu ID de Telegram

# Token del bot (⚠ NO compartas este dato en público ⚠)
TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"

# Diccionario para almacenar datos del usuario
user_data = {}

# Comando /start para configurar el reemplazo
async def start(update: Update, context: CallbackContext) -> int:
    if update.message.from_user.id != AUTHORIZED_USER_ID:
        await update.message.reply_text("🚫 No tienes permiso para usar este bot.")
        return ConversationHandler.END
    
    await update.message.reply_text("¡Hola! 🤖 ¿Qué texto deseas reemplazar?")
    return TEXT_TO_REPLACE

# Capturar el texto a reemplazar
async def set_text_to_replace(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_data[user_id] = {'text_to_replace': update.message.text}
    await update.message.reply_text(f"✅ Entendido. Voy a reemplazar '{update.message.text}'. Ahora dime el nuevo texto que pondré en su lugar.")
    return NEW_TEXT

# Capturar el nuevo texto a usar
async def set_new_text(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_data[user_id]['new_text'] = update.message.text
    await update.message.reply_text(
        f"✅ Perfecto. Reemplazaré '{user_data[user_id]['text_to_replace']}' por '{update.message.text}'. Ahora reenvíame los posts para procesarlos."
    )
    return WAITING_FOR_POSTS

# Procesar los posts reenviados (texto, imágenes y videos)
async def process_posts(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        await update.message.reply_text("⚠️ Debes configurar primero el reemplazo con /start.")
        return

    text_to_replace = user_data[user_id]['text_to_replace']
    new_text = user_data[user_id]['new_text']

    # Extraer el texto original con formato
    original_text = update.message.text or update.message.caption
    entities = update.message.entities or update.message.caption_entities  # Mantiene formato

    if original_text and text_to_replace in original_text:
        replaced_text = original_text.replace(text_to_replace, new_text)

        # Si el mensaje tiene un video
        if update.message.video:
            await context.bot.send_video(
                chat_id=update.message.chat_id,
                video=update.message.video.file_id,
                caption=replaced_text,
                parse_mode=None,  # No forzamos Markdown, usamos el formato de Telegram
                caption_entities=entities  # Mantiene el formato original
            )
        # Si el mensaje tiene una imagen
        elif update.message.photo:
            await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=update.message.photo[-1].file_id,
                caption=replaced_text,
                parse_mode=None,
                caption_entities=entities
            )
        # Si el mensaje contiene solo texto
        else:
            await update.message.reply_text(
                replaced_text,
                parse_mode=None,
                entities=entities  # Mantiene el formato original
            )

        # Elimina el mensaje original
        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception as e:
            print(f"⚠️ Error al eliminar el mensaje: {e}")
    else:
        await update.message.reply_text(f"⚠️ No encontré el texto '{text_to_replace}' en el mensaje.")

# Cancelar la configuración
async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("❌ Configuración cancelada. Usa /start para intentarlo de nuevo.")
    return ConversationHandler.END

# Configuración principal del bot
def main():
    application = Application.builder().token(TOKEN).build()

    # Configurar el flujo de conversación
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TEXT_TO_REPLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_text_to_replace)],
            NEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_text)],
            WAITING_FOR_POSTS: [MessageHandler(filters.ALL, process_posts)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    # Iniciar el bot
    application.run_polling()

if __name__ == '__main__':
    main()
