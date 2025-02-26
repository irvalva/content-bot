import logging
import re
import asyncio
from telegram import (
    Update,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    InputMediaDocument,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackContext,
)

#############################################
# Configuración del Bot Maestro
#############################################

# Inserta aquí el token de tu Bot Maestro
MASTER_TELEGRAM_TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # <-- Reemplaza este valor con tu token

#############################################
# Funciones compartidas para Bots de Reemplazo
#############################################

# Estados del ConversationHandler para la configuración en bots de reemplazo
DETECT_WORD, REPLACE_WORD = range(2)

def replace_text(text: str, detect_word: str, replace_word: str) -> str:
    """
    Reemplaza todas las ocurrencias de detect_word por replace_word.
    Elimina etiquetas <b> si la palabra aparece en negrita.
    """
    pattern = re.compile(r'(?:<b>)?(' + re.escape(detect_word) + r')(?:</b>)?', re.IGNORECASE)
    return pattern.sub(replace_word, text)

# Comandos y funciones de configuración para bots de reemplazo

async def rep_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de configuración en el bot de reemplazo."""
    context.bot_data["configurations"] = context.bot_data.get("configurations", {})
    chat_id = update.effective_chat.id
    context.bot_data["configurations"][chat_id] = {"active": False, "detect_word": None, "replace_word": None}
    await update.message.reply_text("¿Cuál es la palabra que deseas detectar?")
    return DETECT_WORD

async def rep_detect_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    text = update.message.text
    context.bot_data["configurations"][chat_id]["detect_word"] = text
    await update.message.reply_text("¿Cuál es la palabra que deseas usar para reemplazar?")
    return REPLACE_WORD

async def rep_replace_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    text = update.message.text
    conf = context.bot_data["configurations"][chat_id]
    conf["replace_word"] = text
    conf["active"] = True
    await update.message.reply_text(
        f"Configuración completada:\n"
        f"Palabra a detectar: {conf['detect_word']}\n"
        f"Palabra de reemplazo: {conf['replace_word']}\n"
        f"Envía posts para procesar."
    )
    return ConversationHandler.END

async def rep_detener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if "configurations" in context.bot_data and chat_id in context.bot_data["configurations"]:
        context.bot_data["configurations"][chat_id]["active"] = False
        await update.message.reply_text("El bot se ha detenido. Usa /iniciar para reconfigurar.")
    else:
        await update.message.reply_text("No hay configuración activa.")

# Funciones para procesar mensajes en bots de reemplazo

async def rep_process_individual_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    configurations = context.bot_data.get("configurations", {})
    if chat_id not in configurations or not configurations[chat_id].get("active", False):
        return

    detect_word = configurations[chat_id]["detect_word"]
    replace_word_val = configurations[chat_id]["replace_word"]

    # Procesa mensajes de texto
    if update.message.text:
        new_text = replace_text(update.message.text, detect_word, replace_word_val)
        if new_text != update.message.text:
            await context.bot.send_message(chat_id=chat_id, text=new_text, parse_mode="HTML")
            try:
                await update.message.delete()
            except Exception as e:
                logging.error("Error al borrar mensaje: %s", e)
    # Procesa mensajes con medios y caption
    elif update.message.caption:
        new_caption = replace_text(update.message.caption, detect_word, replace_word_val)
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=update.message.photo[-1].file_id,
                caption=new_caption,
                parse_mode="HTML"
            )
        elif update.message.video:
            await context.bot.send_video(
                chat_id=chat_id,
                video=update.message.video.file_id,
                caption=new_caption,
                parse_mode="HTML"
            )
        elif update.message.audio:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=update.message.audio.file_id,
                caption=new_caption,
                parse_mode="HTML"
            )
        elif update.message.document:
            await context.bot.send_document(
                chat_id=chat_id,
                document=update.message.document.file_id,
                caption=new_caption,
                parse_mode="HTML"
            )
        try:
            await update.message.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)

async def rep_process_media_group(context: CallbackContext) -> None:
    """Procesa un grupo de medios preservando el orden original."""
    job = context.job
    mg_id = job.data
    media_groups = context.bot_data.get("media_groups", {})
    messages = media_groups.pop(mg_id, [])
    if not messages:
        return

    messages.sort(key=lambda m: m.message_id)
    chat_id = messages[0].chat.id

    configurations = context.bot_data.get("configurations", {})
    if chat_id not in configurations or not configurations[chat_id].get("active", False):
        return

    detect_word = configurations[chat_id]["detect_word"]
    replace_word_val = configurations[chat_id]["replace_word"]
    media_group_list = []

    for msg in messages:
        caption = msg.caption if msg.caption else ""
        new_caption = replace_text(caption, detect_word, replace_word_val) if caption else caption
        if msg.photo:
            media = InputMediaPhoto(media=msg.photo[-1].file_id, caption=new_caption, parse_mode="HTML")
        elif msg.video:
            media = InputMediaVideo(media=msg.video.file_id, caption=new_caption, parse_mode="HTML")
        elif msg.audio:
            media = InputMediaAudio(media=msg.audio.file_id, caption=new_caption, parse_mode="HTML")
        elif msg.document:
            media = InputMediaDocument(media=msg.document.file_id, caption=new_caption, parse_mode="HTML")
        else:
            media = None
        if media:
            media_group_list.append(media)
        else:
            new_text = replace_text(msg.text, detect_word, replace_word_val)
            await context.bot.send_message(chat_id=chat_id, text=new_text, parse_mode="HTML")

    if media_group_list:
        await context.bot.send_media_group(chat_id=chat_id, media=media_group_list)

    for msg in messages:
        try:
            await msg.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)

async def rep_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja los mensajes entrantes en el bot de reemplazo.  
    Si el mensaje forma parte de un media group se acumula y se procesa luego.
    """
    if update.message.media_group_id:
        mg_id = update.message.media_group_id
        media_groups = context.bot_data.get("media_groups", {})
        media_groups.setdefault(mg_id, []).append(update.message)
        context.bot_data["media_groups"] = media_groups
        context.job_queue.run_once(rep_process_media_group, 1, name=mg_id, data=mg_id)
    else:
        await rep_process_individual_message(update, context)

def setup_replacement_bot(app: Application) -> None:
    """
    Agrega los handlers correspondientes a un bot de reemplazo.
    """
    # ConversationHandler para configurar las palabras con /iniciar
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("iniciar", rep_iniciar)],
        states={
            DETECT_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, rep_detect_word)],
            REPLACE_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, rep_replace_word)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("detener", rep_detener))
    app.add_handler(MessageHandler(filters.ALL, rep_message_handler))

#############################################
# Funciones para el Bot Maestro
#############################################

# Estado para el ConversationHandler del bot maestro (para agregar tokens)
ADD_BOT_TOKEN = range(1)

async def master_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bienvenido al Bot Maestro.\n"
        "Este bot es exclusivo para agregar bots de reemplazo.\n"
        "Usa /addbot para vincular un nuevo bot (envía el token de BotFather)."
    )

async def master_addbot_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Envía el token del bot que deseas agregar:")
    return ADD_BOT_TOKEN

async def master_addbot_receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    token = update.message.text.strip()
    try:
        # Se crea una nueva Application para el bot de reemplazo usando el token proporcionado
        rep_app = Application.builder().token(token).build()
        setup_replacement_bot(rep_app)
        # Almacena la instancia del bot agregado (opcional: para control o registro)
        context.bot_data.setdefault("additional_bots", {})[token] = rep_app
        # Inicia el bot de reemplazo en segundo plano sin cerrar el event loop
        asyncio.create_task(rep_app.run_polling(close_loop=False))
        await update.message.reply_text("Bot de reemplazo agregado exitosamente.")
    except Exception as e:
        await update.message.reply_text(f"Error al agregar el bot: {e}")
    return ConversationHandler.END

#############################################
# Función main (inicializa el Bot Maestro)
#############################################

def main() -> None:
    # Configuración básica de logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )

    master_app = Application.builder().token(MASTER_TELEGRAM_TOKEN).build()

    # Handler para /start del bot maestro
    master_app.add_handler(CommandHandler("start", master_start))

    # ConversationHandler para agregar bots (comando /addbot)
    conv_master = ConversationHandler(
        entry_points=[CommandHandler("addbot", master_addbot_start)],
        states={
            ADD_BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, master_addbot_receive_token)]
        },
        fallbacks=[],
    )
    master_app.add_handler(conv_master)

    # Inicia el bot maestro en modo polling
    master_app.run_polling()

if __name__ == "__main__":
    main()
