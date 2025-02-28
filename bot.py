import telebot
import threading
import html
import re
from telebot.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from bs4 import BeautifulSoup  # Requiere: pip install beautifulsoup4

# =========================
# Funciones de conversión y reconstrucción de formato (para mensajes de texto y captions con entities)
# =========================

def tg_to_py_index(text, tg_offset):
    """
    Convierte un offset (en code units UTF-16 que usa Telegram) al índice real en el string de Python.
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
    Convierte cada entidad (con offset y length en UTF-16) a índices y longitudes en el string de Python.
    Retorna una lista ordenada de diccionarios con 'start', 'end' y 'type'.
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
    Reconstruye el mensaje aplicando el reemplazo en cada segmento y conservando el formato (HTML)
    indicado por las entidades.
    """
    conv_entities = convert_entity_offsets(original_text, entities)
    result = ""
    current_index = 0
    for ent in conv_entities:
        # Procesa el segmento sin formato anterior a la entidad
        plain_segment = original_text[current_index:ent['start']]
        plain_segment = plain_segment.replace(keyword, replacement)
        result += html.escape(plain_segment)
        # Procesa el segmento con formato (entidad)
        entity_text = original_text[ent['start']:ent['end']]
        entity_text = entity_text.replace(keyword, replacement)
        escaped_entity_text = html.escape(entity_text)
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
    # Procesa el resto del texto
    plain_segment = original_text[current_index:]
    plain_segment = plain_segment.replace(keyword, replacement)
    result += html.escape(plain_segment)
    return result

# =========================
# Función para reconstruir captions ya en HTML (sin entities) usando BeautifulSoup
# =========================

def reconstruct_html_caption(caption, keyword, replacement):
    """
    Parsea el caption HTML y reemplaza la palabra clave en los nodos de texto, 
    preservando la estructura y formato HTML.
    """
    soup = BeautifulSoup(caption, "html.parser")
    # Recorremos todos los nodos de texto para realizar el reemplazo
    for element in soup.find_all(text=True):
        new_text = element.replace(keyword, replacement)
        element.replace_with(new_text)
    return str(soup)

# =========================
# Variables para agrupar media groups
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
        threading.Thread(target=start_secondary_bot, args=(new_bot, bot_name)).start()
    except Exception as e:
        bot_master.reply_to(message, f"❌ Token inválido: {str(e)}")

# =========================
# Bot Secundario y Procesamiento de Mensajes
# =========================

def start_secondary_bot(bot, bot_name):
    bot_settings = {'keyword': None, 'replacement': None}

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
        chat_id = message.chat.id
        # Se intenta eliminar el mensaje original
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as e:
            print("No se pudo eliminar el mensaje:", e)
        # Procesa según el tipo de contenido
        if message.content_type == 'text':
            text = message.text
            if keyword in text:
                new_text = (reconstruct_formatted_text(text, message.entities, keyword, replacement)
                            if message.entities else text.replace(keyword, replacement))
            else:
                new_text = text
            bot.send_message(chat_id, new_text, parse_mode='HTML')
        elif message.content_type in ['photo', 'video', 'document', 'audio', 'voice']:
            caption = message.caption if message.caption else ""
            if caption and keyword in caption:
                if message.caption_entities:
                    new_caption = reconstruct_formatted_text(caption, message.caption_entities, keyword, replacement)
                elif '<' in caption and '>' in caption:
                    # Asumimos que el caption ya viene en HTML y lo procesamos con BeautifulSoup
                    new_caption = reconstruct_html_caption(caption, keyword, replacement)
                else:
                    new_caption = caption.replace(keyword, replacement)
            else:
                new_caption = caption
            if message.content_type == 'photo':
                bot.send_photo(chat_id, message.photo[-1].file_id, caption=new_caption, parse_mode='HTML')
            elif message.content_type == 'video':
                bot.send_video(chat_id, message.video.file_id, caption=new_caption, parse_mode='HTML')
            elif message.content_type == 'document':
                bot.send_document(chat_id, message.document.file_id, caption=new_caption, parse_mode='HTML')
            elif message.content_type == 'audio':
                bot.send_audio(chat_id, message.audio.file_id, caption=new_caption, parse_mode='HTML')
            elif message.content_type == 'voice':
                bot.send_voice(chat_id, message.voice.file_id, caption=new_caption, parse_mode='HTML')
        elif message.content_type == 'video_note':
            # Los video_note (videos circulares) no admiten caption
            bot.send_video_note(chat_id, message.video_note.file_id)
        elif message.content_type == 'sticker':
            bot.send_sticker(chat_id, message.sticker.file_id)
        else:
            try:
                bot.copy_message(chat_id, chat_id, message.message_id)
            except Exception as e:
                print("Error copiando mensaje fallback:", e)

    def process_media_group(media_group_id, chat_id, bot, keyword, replacement):
        group_messages = media_groups.get(media_group_id, [])
        if media_group_id in media_groups:
            del media_groups[media_group_id]
        if media_group_id in media_group_timers:
            del media_group_timers[media_group_id]
        group_messages.sort(key=lambda m: m.message_id)
        media_list = []
        for msg in group_messages:
            caption = msg.caption if msg.caption else ""
            if caption and keyword in caption:
                if msg.caption_entities:
                    new_caption = reconstruct_formatted_text(caption, msg.caption_entities, keyword, replacement)
                elif '<' in caption and '>' in caption:
                    new_caption = reconstruct_html_caption(caption, keyword, replacement)
                else:
                    new_caption = caption.replace(keyword, replacement)
            else:
                new_caption = caption
            if msg.content_type == 'photo':
                media_list.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=new_caption, parse_mode='HTML'))
            elif msg.content_type == 'video':
                media_list.append(InputMediaVideo(media=msg.video.file_id, caption=new_caption, parse_mode='HTML'))
            elif msg.content_type == 'document':
                media_list.append(InputMediaDocument(media=msg.document.file_id, caption=new_caption, parse_mode='HTML'))
            elif msg.content_type == 'audio':
                media_list.append(InputMediaAudio(media=msg.audio.file_id, caption=new_caption, parse_mode='HTML'))
            elif msg.content_type == 'video_note':
                # Los video_note no se admiten en media group; se procesan individualmente.
                process_single_message(msg, bot, keyword, replacement)
            else:
                process_single_message(msg, bot, keyword, replacement)
        if media_list:
            bot.send_media_group(chat_id, media=media_list)
        # Se eliminan los mensajes originales del grupo
        for msg in group_messages:
            try:
                bot.delete_message(chat_id, msg.message_id)
            except Exception as e:
                print("Error al eliminar mensaje del media group:", e)

    @bot.message_handler(content_types=['text', 'photo', 'video', 'video_note', 'audio', 'voice', 'document', 'sticker'])
    def handle_all(message):
        keyword = bot_settings['keyword']
        replacement = bot_settings['replacement']
        # Si no se ha configurado palabra clave y reemplazo, se copia el mensaje original
        if keyword is None or replacement is None:
            try:
                bot.copy_message(message.chat.id, message.chat.id, message.message_id)
            except Exception as e:
                print("Error copiando mensaje sin configuración:", e)
            return
        # Si el mensaje forma parte de un media group, agruparlo
        if hasattr(message, 'media_group_id') and message.media_group_id:
            mg_id = message.media_group_id
            if mg_id not in media_groups:
                media_groups[mg_id] = []
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
