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

# Constantes para estados de conversación
DETECT_WORD, REPLACE_WORD = range(2)
ADD_BOT_TOKEN, = range(1)

#############################################
# BOT MAESTRO: CONFIGURACIÓN
#############################################

MASTER_TELEGRAM_TOKEN = "7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g"  # Reemplaza con el token real del Bot Maestro

#############################################
# BOT SECUNDARIO: PROCESAMIENTO DE POSTS
#############################################

# Funciones auxiliares para obtener texto y entidades
def convert_to_html(text: str, entities: list) -> str:
    if not entities:
        return text
    result = ""
    last_index = 0
    for ent in sorted(entities, key=lambda e: e.offset):
        result += text[last_index:ent.offset]
        seg = text[ent.offset: ent.offset+ent.length]
        if ent.type == "bold":
            result += "<b>" + seg + "</b>"
        else:
            result += seg
        last_index = ent.offset+ent.length
    result += text[last_index:]
    return result

def get_message_text_and_entities(message: Update.message.__class__) -> (str, list):
    return message.text or "", message.entities or []

def get_caption_text_and_entities(message: Update.message.__class__) -> (str, list):
    return message.caption or "", message.caption_entities or []

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

# Función de reemplazo simple
def replace_text_simple(text: str, detect_word: str, replace_word: str) -> str:
    return re.sub(re.escape(detect_word), replace_word, text, flags=re.IGNORECASE)

# Función para procesar entidades bold y reemplazar la etiqueta sin bold
def process_text_entities(text: str, entities: list, detect_word: str, replace_word: str):
    new_text = ""
    new_entities = []
    current = 0
    pattern = re.compile('(' + re.escape(detect_word) + ')', re.IGNORECASE)
    for ent in sorted(entities, key=lambda e: e.offset):
        new_text += text[current: ent.offset]
        seg = text[ent.offset: ent.offset+ent.length]
        if ent.type == "bold" and detect_word.lower() in seg.lower():
            parts = pattern.split(seg)
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

# Función principal para procesar posts
async def process_posts(update: Update, context: CallbackContext) -> None:
    config = context.bot_data.get("configurations", {}).get(update.message.from_user.id)
    if not config:
        return
    detect = config.get("detect")
    replace = config.get("replace")
    if not detect or not replace:
        return

    # Procesamiento de álbum (media_group)
    if update.message.media_group_id:
        group_id = update.message.media_group_id
        group = context.bot_data.setdefault(group_id, [])
        group.append(update.message)
        if "scheduled_album_tasks" not in context.bot_data:
            context.bot_data["scheduled_album_tasks"] = {}
        if group_id in context.bot_data["scheduled_album_tasks"]:
            return
        async def process_album():
            await asyncio.sleep(1)
            album = context.bot_data.pop(group_id, [])
            context.bot_data["scheduled_album_tasks"].pop(group_id, None)
            album.sort(key=lambda m: (m.date, m.message_id))
            if album[0].caption:
                caption = album[0].caption
                new_caption = replace_text_simple(caption, detect, replace)
            else:
                new_caption = None
            media_list = []
            for msg in album:
                if msg.photo:
                    if new_caption and msg == album[0]:
                        media_list.append(InputMediaPhoto(msg.photo[-1].file_id, caption=new_caption, parse_mode="HTML"))
                    else:
                        media_list.append(InputMediaPhoto(msg.photo[-1].file_id))
                elif msg.video:
                    if new_caption and msg == album[0]:
                        media_list.append(InputMediaVideo(msg.video.file_id, caption=new_caption, parse_mode="HTML"))
                    else:
                        media_list.append(InputMediaVideo(msg.video.file_id))
                elif msg.audio:
                    if new_caption and msg == album[0]:
                        media_list.append(InputMediaAudio(msg.audio.file_id, caption=new_caption, parse_mode="HTML"))
                    else:
                        media_list.append(InputMediaAudio(msg.audio.file_id))
                elif msg.document:
                    if new_caption and msg == album[0]:
                        media_list.append(InputMediaDocument(msg.document.file_id, caption=new_caption, parse_mode="HTML"))
                    else:
                        media_list.append(InputMediaDocument(msg.document.file_id))
            if media_list:
                await context.bot.send_media_group(chat_id=update.message.chat_id, media=media_list)
            for msg in album:
                try:
                    await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
                except Exception:
                    pass
        task = asyncio.create_task(process_album())
        context.bot_data["scheduled_album_tasks"][group_id] = task
        return

    # Procesamiento de mensajes individuales
    if update.message.text:
        text, ents = get_message_text_and_entities(update.message)
        if ents:
            new_text, new_entities = process_text_entities(text, ents, detect, replace)
            await update.message.reply_text(new_text, entities=new_entities)
        else:
            new_text = replace_text_simple(text, detect, replace)
            await update.message.reply_text(new_text, parse_mode="HTML")
    elif update.message.caption:
        text, ents = get_caption_text_and_entities(update.message)
        if ents:
            new_text, new_entities = process_text_entities(text, ents, detect, replace)
            await update.message.reply_text(new_text, entities=new_entities)
        else:
            new_text = replace_text_simple(text, detect, replace)
            await update.message.reply_text(new_text, parse_mode="HTML")
    else:
        try:
            await update.message.copy_message(chat_id=update.message.chat_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception:
            pass
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
    except Exception:
        pass

# Handlers de configuración para el Bot Secundario
async def rep_cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bienvenido al Bot Secundario.\n"
        "Para configurar, usa /iniciar.\n"
        "Para detener, usa /detener."
    )

async def rep_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.bot_data["configurations"] = {}
    chat_id = update.message.from_user.id
    context.bot_data["configurations"][chat_id] = {"active": False, "detect": None, "replace": None}
    await update.message.reply_text("¿Cuál es la etiqueta que deseas detectar? (Ejemplo: @Sofiaatrade)")
    return DETECT_WORD

async def rep_detect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.message.from_user.id
    detect = update.message.text.strip()
    context.bot_data["configurations"][chat_id]["detect"] = detect
    await update.message.reply_text("¿Con qué etiqueta deseas reemplazarla? (Ejemplo: @CrecimientoConSofia)")
    return REPLACE_WORD

async def rep_replace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.message.from_user.id
    replace = update.message.text.strip()
    config = context.bot_data["configurations"][chat_id]
    config["replace"] = replace
    config["active"] = True
    await update.message.reply_text(
        f"Configuración completada:\n"
        f"Etiqueta a detectar: {config['detect']}\n"
        f"Etiqueta de reemplazo: {config['replace']}\n"
        f"Ahora, envía posts para procesarlos."
    )
    return ConversationHandler.END

async def rep_detener_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.from_user.id
    if chat_id in context.bot_data.get("configurations", {}):
        context.bot_data["configurations"][chat_id]["active"] = False
        await update.message.reply_text("El bot de reemplazo se ha detenido. Para reconfigurar, usa /iniciar.")
    else:
        await update.message.reply_text("No hay configuración activa.")

async def rep_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_posts(update, context)

def setup_secondary_bot(app: Application) -> None:
    app.add_handler(CommandHandler("start", rep_cmd_start))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("iniciar", rep_iniciar)],
        states={
            DETECT_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, rep_detect)],
            REPLACE_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, rep_replace)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("detener", rep_detener_cmd))
    app.add_handler(MessageHandler(filters.ALL, rep_message_handler))

#############################################
# BOT MAESTRO: HANDLERS PARA AGREGAR BOT SECUNDARIO
#############################################

async def master_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bienvenido al Bot Maestro.\n"
        "Este bot es exclusivo para agregar bots de reemplazo.\n"
        "Usa /addbot para vincular un nuevo bot (envía el token de BotFather)."
    )

async def master_addbot_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Envía el token del bot que deseas agregar:")
    return ADD_BOT_TOKEN

def run_secondary_bot(app: Application, loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    # Parchar el registro de señales en este loop
    loop.add_signal_handler = lambda sig, callback, *args, **kwargs: None
    if hasattr(loop, "_add_signal_handler"):
        loop._add_signal_handler = lambda sig, callback, *args, **kwargs: None
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
        sec_app = Application.builder().token(token).build()
        setup_secondary_bot(sec_app)
        context.bot_data.setdefault("additional_bots", {})[token] = sec_app
        new_loop = asyncio.new_event_loop()
        threading.Thread(target=run_secondary_bot, args=(sec_app, new_loop), daemon=True).start()
        await update.message.reply_text("Bot de reemplazo agregado exitosamente.")
    except Exception as e:
        await update.message.reply_text(f"Error al agregar el bot: {e}")
    return ConversationHandler.END

#############################################
# BOT MAESTRO: CONFIGURAR Y EJECUTAR
#############################################

def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
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

