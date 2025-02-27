import telebot
import threading
import html

# Token del Bot Master
MASTER_TOKEN = '7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g'
bot_master = telebot.TeleBot(MASTER_TOKEN)

# Diccionario para almacenar los bots secundarios en memoria
connected_bots = {}

# 🚦 Solicitar el token del nuevo bot
@bot_master.message_handler(commands=['addbot'])
def request_token(message):
    msg = bot_master.reply_to(message, "🤖 Por favor, envía el token del bot secundario:")
    bot_master.register_next_step_handler(msg, add_bot)

# 🚦 Conectar el bot secundario sin guardar archivos
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
        bot_master.reply_to(message, f"✅ Token aceptado. El bot {bot_name} está conectado.")

        # Ejecutar el bot secundario en un hilo separado
        threading.Thread(target=start_secondary_bot, args=(new_bot, bot_name)).start()

    except Exception as e:
        error_message = f"❌ Token inválido: {str(e)}"
        bot_master.reply_to(message, error_message)

# 🚦 Función para iniciar el bot secundario
def start_secondary_bot(bot, bot_name):
    bot_settings = {
        'keyword': None,
        'replacement': None
    }

    @bot.message_handler(commands=['start'])
    def greet(message):
        print("🟢 Comando /start recibido en el bot secundario")
        text = "👋 ¡Hola! Soy tu bot configurable 😊\nDime la <b>palabra clave</b> que debo detectar (incluye @):"
        bot.reply_to(message, text, parse_mode='HTML')
        bot.register_next_step_handler(message, set_keyword)

    def set_keyword(message):
        keyword = message.text.strip()
        if '@' not in keyword:
            bot.reply_to(message, "❌ La palabra clave debe incluir el símbolo @. Inténtalo de nuevo con /start")
            return
        
        bot_settings['keyword'] = keyword
        print(f"✅ Palabra clave guardada: {keyword}")
        
        response_text = f"✅ <b>Palabra clave</b> configurada: {keyword}\nAhora dime la <b>palabra de reemplazo</b> (incluye @):"
        bot.reply_to(message, response_text, parse_mode='HTML')
        bot.register_next_step_handler(message, set_replacement)

    def set_replacement(message):
        replacement = message.text.strip()
        if '@' not in replacement:
            bot.reply_to(message, "❌ La palabra de reemplazo debe incluir el símbolo @. Inténtalo de nuevo con /start")
            return
        
        bot_settings['replacement'] = replacement
        print(f"✅ Palabra de reemplazo guardada: {replacement}")
        
        response_text = f"✅ <b>Palabra de reemplazo</b> configurada: {replacement}\nEl bot está listo para reemplazar automáticamente 🚦"
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

        # Reemplazar solo el texto, manteniendo las entidades de formato
        new_text = message.text.replace(keyword, replacement)
        entities = message.entities if message.entities else []
        formatted_message = reconstruct_formatted_text(new_text, entities, keyword, replacement)

        try:
            bot.delete_message(message.chat.id, message.message_id)
            print("🗑️ Mensaje original eliminado correctamente")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el mensaje: {e}")

        bot.send_message(message.chat.id, formatted_message, parse_mode='HTML')
        print(f"📤 Mensaje enviado: {formatted_message}")

    print(f"🤖 Bot @{bot_name} en funcionamiento...")
    bot.polling(timeout=30, long_polling_timeout=30)

# 🚦 Función para reconstruir el texto manteniendo el formato original sin cortar palabras
def reconstruct_formatted_text(text, entities, keyword, replacement):
    offset_diff = len(replacement) - len(keyword)
    
    for entity in reversed(entities):
        start, end = entity.offset, entity.offset + entity.length
        
        # Ajustar los índices si la entidad está después de la palabra reemplazada
        if start >= text.find(replacement):
            start += offset_diff
            end += offset_diff

        original_text = html.escape(text[start:end])

        if entity.type == 'bold':
            formatted_text = f"<b>{original_text}</b>"
        elif entity.type == 'italic':
            formatted_text = f"<i>{original_text}</i>"
        elif entity.type == 'underline':
            formatted_text = f"<u>{original_text}</u>"
        elif entity.type == 'code':
            formatted_text = f"<code>{original_text}</code>"
        elif entity.type == 'pre':
            formatted_text = f"<pre>{original_text}</pre>"
        elif entity.type == 'text_link' and entity.url:
            formatted_text = f'<a href="{html.escape(entity.url)}">{original_text}</a>'
        else:
            formatted_text = original_text
        
        text = text[:start] + formatted_text + text[end:]
    
    return text

print("🤖 Bot Master en funcionamiento...")
bot_master.polling(timeout=30, long_polling_timeout=30)
