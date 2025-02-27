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

        new_text = message.text.replace(keyword, replacement)
        entities = message.entities if message.entities else []
        formatted_message = apply_formatting_to_words(new_text, entities)

        try:
            bot.delete_message(message.chat.id, message.message_id)
            print("🗑️ Mensaje original eliminado correctamente")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el mensaje: {e}")

        bot.send_message(message.chat.id, formatted_message, parse_mode='HTML')
        print(f"📤 Mensaje enviado: {formatted_message}")

    print(f"🤖 Bot @{bot_name} en funcionamiento...")
    bot.polling(timeout=30, long_polling_timeout=30)

# 🚦 Función para aplicar formato a palabras completas
def apply_formatting_to_words(text, entities):
    # Dividir el texto en palabras para aplicar el formato correctamente
    words = text.split(' ')
    formatted_text = ""

    for word in words:
        formatted_word = html.escape(word)

        # Revisar si la palabra tiene una entidad de formato
        for entity in entities:
            if entity.type == 'bold' and word in text[entity.offset:entity.offset + entity.length]:
                formatted_word = f"<b>{formatted_word}</b>"
            elif entity.type == 'italic' and word in text[entity.offset:entity.offset + entity.length]:
                formatted_word = f"<i>{formatted_word}</i>"
            elif entity.type == 'underline' and word in text[entity.offset:entity.offset + entity.length]:
                formatted_word = f"<u>{formatted_word}</u>"
        
        formatted_text += formatted_word + ' '

    return formatted_text.strip()

print("🤖 Bot Master en funcionamiento...")
bot_master.polling(timeout=30, long_polling_timeout=30)
