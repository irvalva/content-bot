from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler

# Diccionario para almacenar configuraciones de reemplazo por usuario
user_data = {}

# Estados para el flujo de conversación
TEXT_TO_REPLACE, NEW_TEXT = range(2)

# Comando /start para configurar el reemplazador
async def start(update: Update, context: CallbackContext) -> int:
	await update.message.reply_text("¡Hola! ¿Qué texto deseas reemplazar?")
	return TEXT_TO_REPLACE

# Capturar texto a reemplazar
async def set_text_to_replace(update: Update, context: CallbackContext) -> int:
	user_id = update.message.from_user.id
	user_data[user_id] = {'text_to_replace': update.message.text}
	await update.message.reply_text(f"Perfecto. ¿Por qué texto deseas reemplazar '{update.message.text}'?")
	return NEW_TEXT

# Capturar nuevo texto para reemplazar
async def set_new_text(update: Update, context: CallbackContext) -> int:
	user_id = update.message.from_user.id
	user_data[user_id]['new_text'] = update.message.text
	await update.message.reply_text("Listo. Reenvíame mensajes para procesarlos.")
	return ConversationHandler.END

# Procesar mensajes (tanto individuales como álbumes)
async def process_posts(update: Update, context: CallbackContext) -> None:
	user_id = update.message.from_user.id
	if user_id not in user_data:
	return

	text_to_replace = user_data[user_id]['text_to_replace']
	new_text = user_data[user_id]['new_text']

	# Procesamiento para álbum (media group)
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
        	# Si existe caption, aplicar (o no) la sustitución
        	if media.caption is not None:
            	if text_to_replace in media.caption:
                	new_caption = media.caption.replace(text_to_replace, new_text)
            	else:
                	new_caption = media.caption
        	else:
            	new_caption = None

        	if media.photo:
            	transformed_media.append(InputMediaPhoto(media.photo[-1].file_id, caption=new_caption))
        	elif media.video:
            	transformed_media.append(InputMediaVideo(media.video.file_id, caption=new_caption))
        	else:
            	# Aquí podrías agregar soporte para otros tipos de medios si lo deseas.
            	pass

    	# Enviar el álbum transformado (manteniendo el orden)
    	await context.bot.send_media_group(chat_id=update.message.chat_id, media=transformed_media)

    	# Eliminar cada uno de los mensajes originales del álbum
    	for media in media_list:
        	try:
            	await context.bot.delete_message(chat_id=media.chat_id, message_id=media.message_id)
        	except Exception:
            	pass

    	# Limpiar la entrada en bot_data
    	del context.bot_data[media_group]
    	return

	# Procesamiento para mensajes individuales
	# Se extrae el contenido (texto o caption) y se determina el nuevo texto a usar
	original_text = update.message.text if update.message.text is not None else update.message.caption
	if original_text is not None:
    	if text_to_replace in original_text:
        	replaced_text = original_text.replace(text_to_replace, new_text)
    	else:
        	replaced_text = original_text
	else:
    	replaced_text = None

	# Procesar según el tipo de mensaje
	if update.message.photo:
    	await context.bot.send_photo(
        	chat_id=update.message.chat_id,
        	photo=update.message.photo[-1].file_id,
        	caption=replaced_text
    	)
	elif update.message.video:
    	await context.bot.send_video(
        	chat_id=update.message.chat_id,
        	video=update.message.video.file_id,
        	caption=replaced_text
    	)
	elif update.message.text:
    	await update.message.reply_text(replaced_text)
	else:
    	# Para otros tipos de mensaje, se usa copy_message para "repostear" sin cambios.
    	try:
        	await context.bot.copy_message(
            	chat_id=update.message.chat_id,
            	from_chat_id=update.message.chat_id,
            	message_id=update.message.message_id
        	)
    	except Exception:
        	pass

	# Eliminar el mensaje original (ya se procesó y se reenvió)
	try:
    	await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
	except Exception:
    	pass

# Configuración y ejecución del bot
def main():
	TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"
	application = Application.builder().token(TOKEN).build()

	conv_handler = ConversationHandler(
    	entry_points=[CommandHandler("start", start)],
    	states={
        	TEXT_TO_REPLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_text_to_replace)],
        	NEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_text)],
    	},
    	fallbacks=[]
	)

	application.add_handler(conv_handler)
	application.add_handler(MessageHandler(filters.ALL, process_posts))

	application.run_polling()

if __name__ == "__main__":
	main()


