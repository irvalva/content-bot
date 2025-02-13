import logging
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Configuración de logging (opcional)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Diccionario para almacenar la configuración de cada usuario.
# Cada usuario puede definir:
#   "detect": la palabra a detectar.
#   "replace": la palabra de reemplazo.
user_config = {}

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
        # Si el usuario no tiene configuración, no se procesa nada.
        return
    detect = config.get("detect")
    replace = config.get("replace")
    if not detect or not replace:
        return

    # Procesamiento de álbumes (media_group)
    if update.message.media_group_id:
        group_id = update.message.media_group_id
        group = context.bot_data.setdefault(group_id, [])
        group.append(update.message)
        # Espera a que se reciban todos los mensajes del álbum
        if len(group) < update.message.media_group_size:
            return

        media_list = []
        for msg in group:
            if msg.caption:
                new_caption = msg.caption.replace(detect, replace) if detect in msg.caption else msg.caption
            else:
                new_caption = None
            if msg.photo:
                media_list.append(InputMediaPhoto(msg.photo[-1].file_id, caption=new_caption))
            elif msg.video:
                media_list.append(InputMediaVideo(msg.video.file_id, caption=new_caption))
        await context.bot.send_media_group(chat_id=update.message.chat_id, media=media_list)
        for msg in group:
            try:
                await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
            except Exception:
                pass
        context.bot_data.pop(group_id, None)
        return

    # Procesamiento de mensajes individuales
    if update.message.text:
        new_text = update.message.text.replace(detect, replace) if detect in update.message.text else update.message.text
        await update.message.reply_text(new_text, entities=update.message.entities)
    elif update.message.photo:
        caption = update.message.caption or ""
        new_caption = caption.replace(detect, replace) if detect in caption else caption
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=update.message.photo[-1].file_id,
            caption=new_caption,
            caption_entities=update.message.caption_entities,
        )
    elif update.message.video:
        caption = update.message.caption or ""
        new_caption = caption.replace(detect, replace) if detect in caption else caption
        await context.bot.send_video(
            chat_id=update.message.chat_id,
            video=update.message.video.file_id,
            caption=new_caption,
            caption_entities=update.message.caption_entities,
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

    # Agregar los handlers de comandos y mensajes
    app.add_handler(CommandHandler("setdetect", setdetect))
    app.add_handler(CommandHandler("setreplace", setreplace))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.ALL, process_posts))

    # Inicia el bot (modo polling)
    app.run_polling()

if __name__ == "__main__":
    main()
