from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Estados del bot
TEXT_TO_REPLACE, NEW_TEXT, WAITING_FOR_POSTS = range(3)

# ID del usuario autorizado (cambia esto por tu ID de Telegram)
AUTHORIZED_USER_ID = 123456789  # Reemplázalo con tu ID de Telegram

# Diccionario para almacenar datos del usuario
user_data = {}

# Comando /start para configurar el reemplazo
def start(update: Update, context: CallbackContext) -> int:
    if update.message.from_user.id != AUTHORIZED_USER_ID:
        update.message.reply_text("🚫 No tienes permiso para usar este bot.")
        return ConversationHandler.END
    
    update.message.reply_text("¡Hola! 🤖 ¿Qué texto deseas reemplazar?")
    return TEXT_TO_REPLACE

# Capturar el texto a reemplazar
def set_text_to_replace(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_data[user_id] = {'text_to_replace': update.message.text}
    update.message.reply_text(f"✅ Entendido. Voy a reemplazar '{update.message.text}'. Ahora dime el nuevo texto que pondré en su lugar.")
    return NEW_TEXT

# Capturar el nuevo texto a usar
def set_new_text(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_data[user_id]['new_text'] = update.message.text
    update.message.reply_text(
        f"✅ Perfecto. Reemplazaré '{user_data[user_id]['text_to_replace']}' por '{update.message.text}'. Ahora reenvíame los posts para procesarlos."
    )
    return WAITING_FOR_POSTS

# Procesar los posts reenviados (texto, imágenes y videos)
def process_posts(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        update.message.reply_text("⚠️ Debes configurar primero el reemplazo con /start.")
        return

    # Recupera el texto a reemplazar y el nuevo texto
    text_to_replace = user_data[user_id]['text_to_replace']
    new_text = user_data[user_id]['new_text']

    # Procesa cada mensaje reenviado
    original_text = update.message.caption if update.message.caption else update.message.text

    if original_text and text_to_replace in original_text:
        replaced_text = original_text.replace(text_to_replace, new_text)

        # Si el mensaje contiene un video
        if update.message.video:
            context.bot.send_video(
                chat_id=update.message.chat_id,
                video=update.message.video.file_id,
                caption=replaced_text
            )
        # Si el mensaje contiene una imagen
        elif update.message.photo:
            context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=update.message.photo[-1].file_id,
                caption=replaced_text
            )
        # Si el mensaje contiene solo texto
        else:
            update.message.reply_text(replaced_text)

        # Elimina el mensaje original
        try:
            context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception as e:
            print(f"⚠️ Error al eliminar el mensaje: {e}")
    else:
        update.message.reply_text(f"⚠️ No encontré el texto '{text_to_replace}' en el mensaje.")

# Cancelar la configuración
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("❌ Configuración cancelada. Usa /start para intentarlo de nuevo.")
    return ConversationHandler.END

# Configuración principal del bot
def main():
    TOKEN = 'TU_TOKEN_DE_API'  # Reemplázalo con tu token del Bot de Telegram

    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Configurar el flujo de conversación
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TEXT_TO_REPLACE: [MessageHandler(Filters.text & ~Filters.command, set_text_to_replace)],
            NEW_TEXT: [MessageHandler(Filters.text & ~Filters.command, set_new_text)],
            WAITING_FOR_POSTS: [MessageHandler(Filters.all, process_posts)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)

    # Iniciar el bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
