import logging
import re
import threading
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString
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
    JobQueue,
)

#############################################
# Configuración del Bot Maestro
#############################################

MASTER_TELEGRAM_TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # Reemplaza con tu token real

#############################################
# Funciones auxiliares para convertir a HTML
#############################################

def convert_to_html(text: str, entities) -> str:
    """
    Reconstruye el texto a HTML aplicando las entidades de formato (solo se procesan
    las de tipo "bold"). Si no hay entidades, retorna el texto sin cambios.
    """
    result = ""
    last_index = 0
    for entity in sorted(entities, key=lambda e: e.offset):
        result += text[last_index:entity.offset]
        segment = text[entity.offset: entity.offset + entity.length]
        if entity.type == "bold":
            result += "<b>" + segment + "</b>"
        else:
            result += segment
        last_index = entity.offset + entity.length
    result += text[last_index:]
    return result

def get_message_html(message: Update.message.__class__) -> str:
    if message.entities:
        return convert_to_html(message.text, message.entities)
    try:
        return message.to_html()
    except Exception:
        return message.text or ""

def get_caption_html(message: Update.message.__class__) -> str:
    if message.caption and message.caption_entities:
        return convert_to_html(message.caption, message.caption_entities)
    try:
        return message.caption_html
    except Exception:
        return message.caption or ""

#############################################
# Función de reemplazo de texto con formato
#############################################

def replace_text(html_text: str, detect_word: str, replace_word: str) -> str:
    """
    Procesa el contenido HTML para reemplazar todas las ocurrencias de detect_word
    por replace_word.

    Si detect_word aparece dentro de una etiqueta <b>, se quita la negrita en la parte
    reemplazada y se conserva el resto del contenido en negrita; fuera de <b> se hace
    una sustitución simple.

    Se usa un patrón basado en límites definidos por [A-Za-z0-9] para que coincida
    correctamente incluso si detect_word empieza con caracteres especiales (por ejemplo, "@").
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    # Usa límites basados en caracteres alfanuméricos
    regex = re.compile(r'(?<![A-Za-z0-9])' + re.escape(detect_word) + r'(?![A-Za-z0-9])', re.IGNORECASE)

    # Procesar nodos dentro de etiquetas <b>
    for bold_tag in soup.find_all("b"):
        if detect_word.lower() in bold_tag.get_text().lower():
            content = bold_tag.decode_contents(formatter="html")
            parts = regex.split(content)
            matches = regex.findall(content)
            if len(parts) == 1:
                continue
            new_fragments = []
            for i, part in enumerate(parts):
                # Si hay contenido, se envuelve en <b>
                if part:
                    new_b = soup.new_tag("b")
                    new_b.append(NavigableString(part))
                    new_fragments.append(new_b)
                if i < len(matches):
                    # Inserta la palabra reemplazada como texto plano
                    new_fragments.append(NavigableString(replace_word))
            for frag in new_fragments:
                bold_tag.insert_before(frag)
            bold_tag.decompose()

    # Procesar nodos fuera de <b>
    for node in soup.find_all(string=True):
        if node.parent and node.parent.name == "b":
            continue
        new_text = regex.sub(replace_word, node)
        node.replace_with(new_text)

    return str(soup)

#############################################
# Handlers del Bot de Reemplazo
#############################################

# Definir estados para la conversación
DETECT_WORD, REPLACE_WORD = range(2)

async def rep_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    menu = (
        "Comandos disponibles:\n"
        "/iniciar - Configurar el bot de reemplazo\n"
        "/detener - Detener el bot de reemplazo"
    )
    await update.message.reply_text("¡Hola! Soy el Bot de Reemplazo.\n" + menu)

async def rep_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.bot_data["configurations"] = {}
    chat_id = update.effective_chat.id
    context.bot_data["configurations"][chat_id] = {
        "active": False,
        "detect_word": None,
        "replace_word": None
    }
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
    if chat_id in context.bot_data.get("configurations", {}):
        context.bot_data["configurations"][chat_id]["active"] = False
        await update.message.reply_text("El bot se ha detenido. Usa /iniciar para reconfigurar.")
    else:
        await update.message.reply_text("No hay configuración activa.")

async def rep_process_individual_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    configs = context.bot_data.get("configurations", {})
    # Si no hay configuración activa, se reenvía el post original (con formato)
    if chat_id not in configs or not configs[chat_id].get("active", False):
        if update.message.text:
            original_html = get_message_html(update.message)
            await context.bot.send_message(chat_id=chat_id, text=original_html, parse_mode="HTML")
        elif update.message.caption:
            original_html = get_caption_html(update.message)
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=update.message.photo[-1].file_id,
                    caption=original_html,
                    parse_mode="HTML"
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=update.message.video.file_id,
                    caption=original_html,
                    parse_mode="HTML"
                )
            elif update.message.audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=update.message.audio.file_id,
                    caption=original_html,
                    parse_mode="HTML"
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=update.message.document.file_id,
                    caption=original_html,
                    parse_mode="HTML"
                )
        else:
            await context.bot.copy_message(chat_id=chat_id, from_chat_id=chat_id, message_id=update.message.message_id)
        try:
            await update.message.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)
        return

    detect_word = configs[chat_id]["detect_word"]
    replace_word_val = configs[chat_id]["replace_word"]

    if update.message.text:
        original_html = get_message_html(update.message)
        new_html = replace_text(original_html, detect_word, replace_word_val)
        send_text = new_html if new_html != original_html else original_html
        await context.bot.send_message(chat_id=chat_id, text=send_text, parse_mode="HTML")
        try:
            await update.message.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)
    elif update.message.caption:
        original_html = get_caption_html(update.message)
        new_html = replace_text(original_html, detect_word, replace_word_val)
        send_text = new_html if new_html != original_html else original_html
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=update.message.photo[-1].file_id,
                caption=send_text,
                parse_mode="HTML"
            )
        elif update.message.video:
            await context.bot.send_video(
                chat_id=chat_id,
                video=update.message.video.file_id,
                caption=send_text,
                parse_mode="HTML"
            )
        elif update.message.audio:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=update.message.audio.file_id,
                caption=send_text,
                parse_mode="HTML"
            )
        elif update.message.document:
            await context.bot.send_document(
                chat_id=chat_id,
                document=update.message.document.file_id,
                caption=send_text,
                parse_mode="HTML"
            )
        try:
            await update.message.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)
    else:
        await context.bot.copy_message(chat_id=chat_id, from_chat_id=chat_id, message_id=update.message.message_id)
        try:
            await update.message.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)

async def rep_process_media_group(context: CallbackContext) -> None:
    job = context.job
    mg_id = job.data
    media_groups = context.bot_data.get("media_groups", {})
    messages = media_groups.pop(mg_id, [])
    if not messages:
        return
    # Ordena por fecha y message_id para preservar el orden original
    messages.sort(key=lambda m: (m.date, m.message_id))
    chat_id = messages[0].chat.id
    configs = context.bot_data.get("configurations", {})
    if chat_id not in configs or not configs[chat_id].get("active", False):
        if messages[0].caption:
            original_html = get_caption_html(messages[0])
            media_list = []
            for i, m in enumerate(messages):
                if m.photo:
                    if i == 0:
                        media_list.append(InputMediaPhoto(media=m.photo[-1].file_id, caption=original_html, parse_mode="HTML"))
                    else:
                        media_list.append(InputMediaPhoto(media=m.photo[-1].file_id))
            if media_list:
                await context.bot.send_media_group(chat_id=chat_id, media=media_list)
        else:
            for m in messages:
                await context.bot.copy_message(chat_id=chat_id, from_chat_id=chat_id, message_id=m.message_id)
        for m in messages:
            try:
                await m.delete()
            except Exception as e:
                logging.error("Error al borrar mensaje: %s", e)
        return

    detect_word = configs[chat_id]["detect_word"]
    replace_word_val = configs[chat_id]["replace_word"]

    processed_caption = ""
    if messages[0].caption:
        original_html = get_caption_html(messages[0])
        new_html = replace_text(original_html, detect_word, replace_word_val)
        processed_caption = new_html if new_html != original_html else original_html

    media_list = []
    for i, m in enumerate(messages):
        if m.photo:
            if i == 0:
                media = InputMediaPhoto(media=m.photo[-1].file_id, caption=processed_caption, parse_mode="HTML")
            else:
                media = InputMediaPhoto(media=m.photo[-1].file_id)
            media_list.append(media)
        elif m.video:
            if i == 0:
                media = InputMediaVideo(media=m.video.file_id, caption=processed_caption, parse_mode="HTML")
            else:
                media = InputMediaVideo(media=m.video.file_id)
            media_list.append(media)
        elif m.audio:
            if i == 0:
                media = InputMediaAudio(media=m.audio.file_id, caption=processed_caption, parse_mode="HTML")
            else:
                media = InputMediaAudio(media=m.audio.file_id)
            media_list.append(media)
        elif m.document:
            if i == 0:
                media = InputMediaDocument(media=m.document.file_id, caption=processed_caption, parse_mode="HTML")
            else:
                media = InputMediaDocument(media=m.document.file_id)
            media_list.append(media)
        else:
            original_html = get_message_html(m)
            new_html = replace_text(original_html, detect_word, replace_word_val)
            send_text = new_html if new_html != original_html else original_html
            await context.bot.send_message(chat_id=chat_id, text=send_text, parse_mode="HTML")
    if media_list:
        await context.bot.send_media_group(chat_id=chat_id, media=media_list)
    for m in messages:
        try:
            await m.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)

async def rep_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.media_group_id:
        mg_id = update.message.media_group_id
        media_groups = context.bot_data.get("media_groups", {})
        media_groups.setdefault(mg_id, []).append(update.message)
        context.bot_data["media_groups"] = media_groups
        if context.job_queue:
            context.job_queue.run_once(rep_process_media_group, 1, name=mg_id, data=mg_id)
        else:
            await rep_process_media_group(context)
    else:
        await rep_process_individual_message(update, context)

def setup_replacement_bot(app: Application) -> None:
    app.add_handler(CommandHandler("start", rep_start))
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
# Handlers del Bot Maestro
#############################################

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

def run_polling_in_thread(app: Application, loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    # Parcheamos add_signal_handler para evitar errores en threads secundarios
    loop.add_signal_handler = lambda sig, callback, *args, **kwargs: None
    if app.job_queue is None:
        jq = JobQueue()
        jq.start()
        app.job_queue = jq
    loop.run_until_complete(app.bot.set_my_commands([
        ("start", "Mostrar menú de comandos"),
        ("iniciar", "Configurar el bot de reemplazo"),
        ("detener", "Detener el bot de reemplazo")
    ]))
    app.run_polling(close_loop=False)

async def master_addbot_receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    token = update.message.text.strip()
    try:
        rep_app = Application.builder().token(token).build()
        setup_replacement_bot(rep_app)
        context.bot_data.setdefault("additional_bots", {})[token] = rep_app
        new_loop = asyncio.new_event_loop()
        threading.Thread(target=run_polling_in_thread, args=(rep_app, new_loop), daemon=True).start()
        await update.message.reply_text("Bot de reemplazo agregado exitosamente.")
    except Exception as e:
        await update.message.reply_text(f"Error al agregar el bot: {e}")
    return ConversationHandler.END

def main() -> None:
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    master_app = Application.builder().token(MASTER_TELEGRAM_TOKEN).build()
    if master_app.job_queue is None:
        jq = JobQueue()
        jq.start()
        master_app.job_queue = jq
    master_app.add_handler(CommandHandler("start", master_start))
    conv_master = ConversationHandler(
        entry_points=[CommandHandler("addbot", master_addbot_start)],
        states={ADD_BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, master_addbot_receive_token)]},
        fallbacks=[],
    )
    master_app.add_handler(conv_master)
    master_app.run_polling()

if __name__ == "__main__":
    main()
