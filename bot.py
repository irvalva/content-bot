import logging
import re
import threading
import asyncio
from datetime import datetime
from telegram import (
    Update,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    InputMediaDocument,
    MessageEntity,
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

MASTER_TELEGRAM_TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # Reemplaza con el token real

#############################################
# Funciones auxiliares para trabajar con entidades
#############################################

def convert_to_html(text: str, entities: list) -> str:
    """
    Reconstruye el texto a HTML aplicando las entidades (solo bold, en este ejemplo).
    Si no hay entidades, retorna el texto sin cambios.
    """
    if not entities:
        return text
    result = ""
    last_index = 0
    for ent in sorted(entities, key=lambda e: e.offset):
        result += text[last_index:ent.offset]
        seg = text[ent.offset: ent.offset + ent.length]
        if ent.type == "bold":
            result += "<b>" + seg + "</b>"
        else:
            result += seg
        last_index = ent.offset + ent.length
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
    Procesa el contenido HTML para reemplazar todas las ocurrencias de detect_word por replace_word.
    Si detect_word aparece dentro de una etiqueta <b>, se elimina el formato bold únicamente en la
    porción correspondiente a detect_word; el resto se conserva.
    Fuera de <b>, se hace un reemplazo simple.
    Se utiliza un patrón basado en [A-Za-z0-9] para detectar detect_word.
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    pattern = re.compile(r'(?<![A-Za-z0-9])' + re.escape(detect_word) + r'(?![A-Za-z0-9])', re.IGNORECASE)

    # Procesar nodos dentro de <b>
    for bold_tag in soup.find_all("b"):
        if detect_word.lower() in bold_tag.get_text().lower():
            content = bold_tag.decode_contents(formatter="html")
            parts = pattern.split(content)
            matches = pattern.findall(content)
            if len(parts) == 1:
                continue
            new_fragments = []
            for i, part in enumerate(parts):
                if part:
                    new_b = soup.new_tag("b")
                    new_b.append(NavigableString(part))
                    new_fragments.append(new_b)
                if i < len(matches):
                    new_fragments.append(NavigableString(replace_word))
            for frag in new_fragments:
                bold_tag.insert_before(frag)
            bold_tag.decompose()

    # Procesar nodos fuera de <b>
    for node in soup.find_all(string=True):
        if node.parent and node.parent.name == "b":
            continue
        new_text = pattern.sub(replace_word, node)
        node.replace_with(new_text)
    return str(soup)

def replace_text_simple(text: str, detect_word: str, replace_word: str) -> str:
    pattern = re.compile(r'(?<![A-Za-z0-9])' + re.escape(detect_word) + r'(?![A-Za-z0-9])', re.IGNORECASE)
    return pattern.sub(replace_word, text)

def process_text_entities(text: str, entities: list, detect_word: str, replace_word: str):
    """
    Procesa el texto y las entidades, reemplazando detect_word por replace_word en las entidades bold.
    """
    new_text = ""
    new_entities = []
    current = 0
    for ent in sorted(entities, key=lambda e: e.offset):
        new_text += text[current: ent.offset]
        seg = text[ent.offset: ent.offset+ent.length]
        if ent.type == "bold" and detect_word.lower() in seg.lower():
            # Dividir seg en partes
            parts = re.split('(' + re.escape(detect_word) + ')', seg, flags=re.IGNORECASE)
            for part in parts:
                if part.lower() == detect_word.lower():
                    new_text += replace_word
                else:
                    if part:
                        start = len(new_text)
                        new_text += part
                        new_entities.append(MessageEntity(type="bold", offset=start, length=len(part)))
        else:
            start = len(new_text)
            new_text += seg
            new_entities.append(MessageEntity(type=ent.type, offset=start, length=len(seg)))
        current = ent.offset + ent.length
    new_text += text[current:]
    return new_text, new_entities

#############################################
# Handlers del Bot de Reemplazo
#############################################

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
    await update.message.reply_text("¿Cuál es la etiqueta (ej. @Sofiaatrade) que deseas detectar?")
    return DETECT_WORD

async def rep_detect_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    context.bot_data["configurations"][chat_id]["detect_word"] = text
    await update.message.reply_text("¿Con qué etiqueta (ej. @CrecimientoConSofia) deseas reemplazarla?")
    return REPLACE_WORD

async def rep_replace_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    conf = context.bot_data["configurations"][chat_id]
    conf["replace_word"] = text
    conf["active"] = True
    await update.message.reply_text(
        f"Configuración completada:\n"
        f"Etiqueta a detectar: {conf['detect_word']}\n"
        f"Etiqueta de reemplazo: {conf['replace_word']}\n"
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
    if chat_id not in configs or not configs[chat_id].get("active", False):
        # Reenviamos el mensaje original sin cambios
        if update.message.text:
            await context.bot.send_message(chat_id=chat_id, text=update.message.text, parse_mode="HTML")
        elif update.message.caption:
            await context.bot.send_message(chat_id=chat_id, text=update.message.caption, parse_mode="HTML")
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
        text, ents = get_message_text_and_entities(update.message)
        if ents:
            new_text, new_entities = process_text_entities(text, ents, detect_word, replace_word_val)
            await context.bot.send_message(chat_id=chat_id, text=new_text, entities=new_entities)
        else:
            new_text = replace_text_simple(text, detect_word, replace_word_val)
            await context.bot.send_message(chat_id=chat_id, text=new_text, parse_mode="HTML")
        try:
            await update.message.delete()
        except Exception as e:
            logging.error("Error al borrar mensaje: %s", e)
    elif update.message.caption:
        text, ents = get_caption_text_and_entities(update.message)
        if ents:
            new_text, new_entities = process_text_entities(text, ents, detect_word, replace_word_val)
            await context.bot.send_message(chat_id=chat_id, text=new_text, entities=new_entities)
        else:
            new_text = replace_text_simple(text, detect_word, replace_word_val)
            await context.bot.send_message(chat_id=chat_id, text=new_text, parse_mode="HTML")
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
    # Ordenamos por fecha y message_id para preservar el orden original
    messages.sort(key=lambda m: (m.date, m.message_id))
    chat_id = messages[0].chat.id
    configs = context.bot_data.get("configurations", {})
    if chat_id not in configs or not configs[chat_id].get("active", False):
        if messages[0].caption:
            caption = messages[0].caption
            media_list = []
            for m in messages:
                if m.photo:
                    media_list.append(InputMediaPhoto(media=m.photo[-1].file_id, caption=caption, parse_mode="HTML"))
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
        text, ents = get_caption_text_and_entities(messages[0])
        if ents:
            processed_caption, _ = process_text_entities(text, ents, detect_word, replace_word_val)
        else:
            processed_caption = replace_text_simple(text, detect_word, replace_word_val)

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
            text, ents = get_message_text_and_entities(m)
            if ents:
                new_text, new_entities = process_text_entities(text, ents, detect_word, replace_word_val)
                await context.bot.send_message(chat_id=chat_id, text=new_text, entities=new_entities)
            else:
                new_text = replace_text_simple(text, detect_word, replace_word_val)
                await context.bot.send_message(chat_id=chat_id, text=new_text, parse_mode="HTML")
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
