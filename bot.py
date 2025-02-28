mport telebot
import threading
import html
import re
from telebot.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument

# =========================
# Funciones para convertir y reconstruir texto formateado
# =========================

def tg_to_py_index(text, tg_offset):
    """
    Convierte un offset basado en UTF-16 (de Telegram) al índice de Python.
    """
    code_units = 0
    for i, ch in enumerate(text):
        units = len(ch.encode('utf-16-le')) // 2
        if code_units + units > tg_offset:
            return i
        code_units += units
    return len(text)

def convert_entity_offsets(text, entities):
    """
    Convierte cada entidad de Telegram (offset y length en UTF-16) a índices de Python.
    Retorna una lista de diccionarios con 'start', 'end' y 'type'.
    """
    converted = []
    for entity in entities:
        start = tg_to_py_index(text, entity.offset)
        end = tg_to_py_index(text, entity.offset + entity.length)
        converted.append({
            'start': start,
            'end': end,
            'type': entity.type
        })
    return sorted(converted, key=lambda e: e['start'])

def reconstruct_formatted_text(original_text, entities, keyword, replacement):
    """
    Reconstruye el mensaje final en HTML aplicando el reemplazo en cada segmento de texto,
    respetando el formato (entidades) recibido.
    """
    conv_entities = convert_entity_offsets(original_text, entities)
    result = ""
    current_index = 0
    for ent in conv_entities:
        # Procesa el segmento sin formato anterior a la entidad
        plain_segment = original_text[current_index:ent['start']]
        plain_segment = plain_segment.replace(keyword, replacement)
        result += html.escape(plain_segment)
        
        # Procesa el segmento de la entidad
        entity_text = original_text[ent['start']:ent['end']]
        entity_text = entity_text.replace(keyword, replacement)
        escaped_entity_text = html.escape(entity_text)
        
        # Aplica la etiqueta según el tipo de entidad
        if ent['type'] == 'bold':
            result += f"<b>{escaped_entity_text}</b>"
        elif ent['type'] == 'italic':
            result += f"<i>{escaped_entity_text}</i>"
        elif ent['type'] == 'underline':
            result += f"<u>{escaped_entity_text}</u>"
        elif ent['type'] == 'strikethrough':
            result += f"<s>{escaped_entity_text}</s>"
        elif ent['type'] == 'code':
            result += f"<code>{escaped_entity_text}</code>"
        elif ent['type'] == 'pre':
            result += f"<pre>{escaped_entity_text}</pre>"
        else:
            result += escaped_entity_text

        current_index = ent['end']
    # Procesa el resto del texto sin entidad
    plain_segment = original_text[current_index:]
    plain_segment = plain_segment.replace(keyword, replacement)
    result += html.escape(plain_segment)
    return result

# =========================
# Variables globales para agrupar media groups
# =========================

media_groups = {}         # key: media_group_id, value: lista de mensajes
media_group_timers = {}   # key: media_group_id, value: timer

# =========================
# Bot Master
# =========================

MASTER_TOKEN = '7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g'
bot_master = telebot.TeleBot(MASTER_TOKEN)
connected_bots = {}

@bot_master.message_handler(commands=['addbot'])
def request_token(message):
    msg = bot_master.reply_to(message, "🤖 Por favor, envía el token del bot secundario:")
    bot_master.register_next_step_handler(msg, add_bot)

def add_bot(message):
    token = message.text.strip()
    try:
        new_bot = telebot.TeleBot(token, parse_mode='HTML')
        bot_info = new_bot.get_me()
        bot_name = bot_info.username

        if bot_name in connected_bots:
            bot_master.reply_to(message, f"❗️ El bot @{bot_name} ya está conectado.")
            return

        connected_bots[bot_name] = new_bot
        bot_master.reply_to(message, f"✅ Token aceptado. El bot @{bot_name} está conectado.")

        # Ejecutar el bot secundario en un hilo separado
        threading.Thread(target=start_secondary_bot, args=(new_bot, bot_name)).start()

    except Exception as e:
        error_message = f"❌ Token inválido: {str(e)}"
        bot_master.reply_to(message, error_message)

# =========================
# Bot Secundario y Procesamiento de Mensajes
# =========================

def start_secondary_bot(bot, bot_name):
    # Diccionario para almacenar la palabra clave y su reemplazo
    bot_settings = {
        'keyword': None,
        'replacement': None
    }

    @bot.message_handler(commands=['start'])
    def greet(message):
        welcome_text = ("👋 ¡Hola! Soy tu bot configurable 😊\n"
                        "Dime la <b>palabra clave</b> que debo detectar (incluye @):")
        bot.reply_to(message, welcome_text, parse_mode='HTML')
        bot.register_next_step_handler(message, set_keyword)

    def set_keyword(message):
        keyword = message.text.strip()
        if '@' not in keyword:
            bot.reply_to(message, "❌ La palabra clave debe incluir el símbolo @. Inténtalo de nuevo con /start", parse_mode='HTML')
            return
        bot_settings['keyword'] = keyword
        response_text = (f"✅ <b>Palabra clave</b> configurada: {keyword}\n"
                         "Ahora dime la <b>palabra de reemplazo</b> (incluye @):")
        bot.reply_to(message, response_text, parse_mode='HTML')
        bot.register_next_step_handler(message, set_replacement)

    def set_replacement(message):
        replacement = message.text.strip()
        if '@' not in replacement:
            bot.reply_to(message, "❌ La palabra de reemplazo debe incluir el símbolo @. Inténtalo de nuevo con /start", parse_mode='HTML')
            return
        bot_settings['replacement'] = replacement
        bot.reply_to(message, f"✅ <b>Palabra de reemplazo</b> configurada: {replacement}\nEl bot está listo para reemplazar automáticamente 🚦", parse_mode='HTML')

    def process_single_message(message, bot, keyword, replacement):
        """
        Procesa mensajes individuales (no pertenecientes a media group), reemplazando
        el texto o caption si corresponde; de lo contrario, copia el mensaje original.
        """
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            print("No se pudo eliminar el mensaje:", e)

        # Si es un mensaje de texto
        if hasattr(message, 'text') and message.text:
            if keyword in message.text:
                new_text = (reconstruct_formatted_text(message.text, message.entities, keyword, replacement)
                            if message.entities else message.text.replace(keyword, replacement))
            else:
                new_text = message.text
            bot.send_message(message.chat.id, new_text, parse_mode='HTML')
            return

        # Si tiene caption (por ejemplo, foto, video, audio, documento)
        if hasattr(message, 'caption') and message.caption:
            if keyword in message.caption:
                new_caption = (reconstruct_formatted_text(message.caption, message.caption_entities, keyword, replacement)
                               if message.caption_entities else message.caption.replace(keyword, replacement))
            else:
                new_caption = message.caption

            if message.photo:
                bot.send_photo(message.chat.id, message.photo[-1].file_id, caption=new_caption, parse_mode='HTML')
            elif message.video:
                bot.send_video(message.chat.id, message.video.file_id, caption=new_caption, parse_mode='HTML')
            elif message.document:
                bot.send_document(message.chat.id, message.document.file_id, caption=new_caption, parse_mode='HTML')
            elif message.audio:
                bot.send_audio(message.chat.id, message.audio.file_id, caption=new_caption, parse_mode='HTML')
            else:
                bot.copy_message(message.chat.id, message.chat.id, message.message_id)
            return

        # Si el mensaje no tiene texto ni caption, simplemente lo copia
        bot.copy_message(message.chat.id, message.chat.id, message.message_id)

    def process_media_group(media_group_id, chat_id, bot, keyword, replacement):
        """
        Procesa un grupo de medios (media group) en conjunto, asegurando que se
        mantenga el orden y se reemplacen los textos en las captions si existen.
        """
        group_messages = media_groups.get(media_group_id, [])
        if media_group_id in media_groups:
            del media_groups[media_group_id]
        if media_group_id in media_group_timers:
            del media_group_timers[media_group_id]

        group_messages.sort(key=lambda m: m.message_id)
        media_list = []
        for msg in group_messages:
            caption = None
            if msg.caption:
                if keyword in msg.caption:
                    caption = (reconstruct_formatted_text(msg.caption, msg.caption_entities, keyword, replacement)
                               if msg.caption_entities else msg.caption.replace(keyword, replacement))
                else:
                    caption = msg.caption

            # Dependiendo del tipo de medio, se arma el InputMedia correspondiente:
            if msg.photo:
                media_list.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=caption, parse_mode='HTML'))
            elif msg.video:
                media_list.append(InputMediaVideo(media=msg.video.file_id, caption=caption, parse_mode='HTML'))
            elif msg.document:
                media_list.append(InputMediaDocument(media=msg.document.file_id, caption=caption, parse_mode='HTML'))
            else:
                # Si no se reconoce, se procesa individualmente
                process_single_message(msg, bot, keyword, replacement)
        if media_list:
            bot.send_media_group(chat_id, media=media_list)

    @bot.message_handler(content_types=['text', 'photo', 'video', 'video_note', 'audio', 'document', 'sticker'])
    def handle_all(message):
        """
        Handler genérico para procesar cualquier mensaje. Si el mensaje forma parte de
        un media group se agrupa para procesarlo junto con los demás; en caso contrario se
        procesa individualmente.
        """
        keyword = bot_settings['keyword']
        replacement = bot_settings['replacement']

        # Si aún no se han configurado palabra clave y reemplazo, simplemente se copia el mensaje
        if keyword is None or replacement is None:
            try:
                bot.copy_message(message.chat.id, message.chat.id, message.message_id)
            except Exception as e:
                print("Error copiando mensaje:", e)
            return

        if hasattr(message, 'media_group_id') and message.media_group_id:
            mg_id = message.media_group_id
            if mg_id not in media_groups:
                media_groups[mg_id] = []
                # Se programa el procesamiento del media group después de 1 segundo
                timer = threading.Timer(1.0, process_media_group, args=(mg_id, message.chat.id, bot, keyword, replacement))
                media_group_timers[mg_id] = timer
                timer.start()
            media_groups[mg_id].append(message)
        else:
            process_single_message(message, bot, keyword, replacement)

    print(f"🤖 Bot @{bot_name} en funcionamiento...")
    bot.polling(timeout=30, long_polling_timeout=30)

# =========================
# Iniciar Bot Master
# =========================

print("🤖 Bot Master en funcionamiento...")
bot_master.polling(timeout=30, long_polling_timeout=30)

