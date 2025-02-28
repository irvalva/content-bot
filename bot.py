import telebot
import threading
import html

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
                         "Ahora dime la <b>palabra de reemplazo</b> (incluye @):")
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

        formatted_message = reconstruct_formatted_text(
            message.text,
            message.entities if message.entities else [],
            keyword, replacement
        )

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
# Función para Reconstruir el Texto Formateado
# =========================

def reconstruct_formatted_text(original_text, entities, keyword, replacement):
    """
    Reconstruye el mensaje final aplicando el reemplazo en los segmentos de texto plano
    y reinsertando el formato definido en las entidades.
    """
    # Ordenar las entidades por su offset
    entities = sorted(entities, key=lambda e: e.offset)
    result = ""
    current_index = 0
    for entity in entities:
        # Segmento de texto plano antes de la entidad
        plain_segment = original_text[current_index:entity.offset]
        plain_segment = plain_segment.replace(keyword, replacement)
        result += html.escape(plain_segment)

        # Texto de la entidad
        entity_text = original_text[entity.offset: entity.offset + entity.length]
        entity_text = entity_text.replace(keyword, replacement)
        escaped_entity_text = html.escape(entity_text)

        # Aplicar el tag según el tipo de entidad
        if entity.type == 'bold':
            result += f"<b>{escaped_entity_text}</b>"
        elif entity.type == 'italic':
            result += f"<i>{escaped_entity_text}</i>"
        elif entity.type == 'underline':
            result += f"<u>{escaped_entity_text}</u>"
        elif entity.type == 'strikethrough':
            result += f"<s>{escaped_entity_text}</s>"
        elif entity.type == 'code':
            result += f"<code>{escaped_entity_text}</code>"
        elif entity.type == 'pre':
            result += f"<pre>{escaped_entity_text}</pre>"
        else:
            result += escaped_entity_text

        current_index = entity.offset + entity.length

    # Procesar el resto del texto después de la última entidad
    plain_segment = original_text[current_index:]
    plain_segment = plain_segment.replace(keyword, replacement)
    result += html.escape(plain_segment)
    return result

# =========================
# Iniciar Bot Master
# =========================

print("🤖 Bot Master en funcionamiento...")
bot_master.polling(timeout=30, long_polling_timeout=30)

