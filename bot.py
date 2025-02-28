import telebot
import threading
import html
import re

# =========================
# Bot Master
# =========================

MASTER_TOKEN = '7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g'
bot_master = telebot.TeleBot(MASTER_TOKEN)

# Diccionario para almacenar los bots secundarios en memoria
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
# Bot Secundario y Funciones de Reemplazo
# =========================

def start_secondary_bot(bot, bot_name):
    bot_settings = {
        'keyword': None,
        'replacement': None
    }

    @bot.message_handler(commands=['start'])
    def greet(message):
        print("🟢 Comando /start recibido en el bot secundario")
        text = ("👋 ¡Hola! Soy tu bot configurable 😊\n"
                "Dime la <b>palabra clave</b> que debo detectar (incluye @):")
        bot.reply_to(message, text, parse_mode='HTML')
        bot.register_next_step_handler(message, set_keyword)

    def set_keyword(message):
        keyword = message.text.strip()
        if '@' not in keyword:
            bot.reply_to(message, "❌ La palabra clave debe incluir el símbolo @. Inténtalo de nuevo con /start")
            return

        bot_settings['keyword'] = keyword
        print(f"✅ Palabra clave guardada: {keyword}")
        response_text = (f"✅ <b>Palabra clave</b> configurada: {keyword}\n"
                         f"Ahora dime la <b>palabra de reemplazo</b> (incluye @):")
        bot.reply_to(message, response_text, parse_mode='HTML')
        bot.register_next_step_handler(message, set_replacement)

    def set_replacement(message):
        replacement = message.text.strip()
        if '@' not in replacement:
            bot.reply_to(message, "❌ La palabra de reemplazo debe incluir el símbolo @. Inténtalo de nuevo con /start")
            return

        bot_settings['replacement'] = replacement
        print(f"✅ Palabra de reemplazo guardada: {replacement}")
        response_text = (f"✅ <b>Palabra de reemplazo</b> configurada: {replacement}\n"
                         "El bot está listo para reemplazar automáticamente 🚦")
        bot.reply_to(message, response_text, parse_mode='HTML')

    @bot.message_handler(func=lambda message: bot_settings['keyword'] and bot_settings['keyword'] in message.text)
    def auto_replace(message):
        keyword = bot_settings['keyword']
        replacement = bot_settings['replacement']

        if not keyword or not replacement:
            print("⚠️ No se ha configurado la palabra clave o el reemplazo.")
            return

        print(f"🔍 Mensaje recibido: {message.text}")
        print(f"🛠️ Reemplazando '{keyword}' con '{replacement}'")

        # Usamos la función que reconstruye el mensaje formateado,
        # calculando los nuevos offsets a partir del texto original.
        formatted_message = reconstruct_formatted_text(message.text, 
                                                       message.entities if message.entities else [],
                                                       keyword, replacement)

        try:
            bot.delete_message(message.chat.id, message.message_id)
            print("🗑️ Mensaje original eliminado correctamente")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el mensaje: {e}")

        bot.send_message(message.chat.id, formatted_message, parse_mode='HTML')
        print(f"📤 Mensaje enviado: {formatted_message}")

    print(f"🤖 Bot @{bot_name} en funcionamiento...")
    bot.polling(timeout=30, long_polling_timeout=30)

# =========================
# Funciones de Ajuste de Entidades y Reconstrucción del Formato
# =========================

def map_offset(old_offset, original_text, keyword, replacement):
    """
    Calcula el nuevo offset en base a la cantidad de ocurrencias de `keyword`
    que aparecen antes de old_offset en el texto original, considerando el cambio
    en longitud (delta) que produce cada reemplazo.
    """
    diff = len(replacement) - len(keyword)
    delta = 0
    for m in re.finditer(re.escape(keyword), original_text):
        if m.start() < old_offset:
            delta += diff
        else:
            break
    return old_offset + delta

def reconstruct_formatted_text(original_text, entities, keyword, replacement):
    """
    Reconstruye el mensaje final en HTML. Primero se calcula el texto final 
    aplicando el reemplazo y luego se ajustan los offsets y longitudes de las entidades 
    en función de la diferencia en longitud introducida.
    """
    # Texto final con el reemplazo aplicado globalmente
    new_text = original_text.replace(keyword, replacement)
    diff = len(replacement) - len(keyword)
    adjusted_entities = []

    # Asegurarse de que las entidades estén ordenadas por offset
    entities = sorted(entities, key=lambda e: e.offset)

    for entity in entities:
        # Calcular el nuevo offset de la entidad
        new_offset = map_offset(entity.offset, original_text, keyword, replacement)
        # Extraer el texto original de la entidad
        orig_entity_text = original_text[entity.offset: entity.offset + entity.length]
        # Contar cuántas ocurrencias de `keyword` aparecen dentro de la entidad
        count = len(re.findall(re.escape(keyword), orig_entity_text))
        new_length = entity.length + count * diff
        adjusted_entities.append({
            'new_offset': new_offset,
            'new_length': new_length,
            'type': entity.type
        })

    # Reconstruir el mensaje HTML insertando los tags correspondientes
    result = ""
    last_index = 0
    for ent in adjusted_entities:
        # Añadir la parte del texto sin formato (escapado) hasta la entidad
        result += html.escape(new_text[last_index:ent['new_offset']])
        # Extraer el segmento de texto correspondiente a la entidad
        entity_substring = new_text[ent['new_offset']: ent['new_offset'] + ent['new_length']]
        escaped_entity_text = html.escape(entity_substring)
        # Envolver el segmento según el tipo de entidad
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
            # Si el tipo de entidad no se maneja específicamente, se inserta el texto sin formato
            result += escaped_entity_text

        last_index = ent['new_offset'] + ent['new_length']
    # Añadir el resto del texto que quede fuera de las entidades
    result += html.escape(new_text[last_index:])
    return result

# =========================
# Iniciar Bot Master
# =========================

print("🤖 Bot Master en funcionamiento...")
bot_master.polling(timeout=30, long_polling_timeout=30)


