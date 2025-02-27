import telebot
import threading
from telebot import types

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
        new_bot = telebot.TeleBot(token, parse_mode='MarkdownV2')
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
    # Almacenamiento dinámico de la palabra clave y la palabra de reemplazo
    bot_settings = {
        'keyword': None,
        'replacement': None
    }

    @bot.message_handler(commands=['start'])
    def greet(message):
        print("🟢 Comando /start recibido en el bot secundario")
        text = "👋 ¡Hola! Soy tu bot configurable 😊\nDime la *palabra clave* que debo detectar (incluye @):"
        escaped_text = escape_markdown(text)
        bot.reply_to(message, escaped_text, parse_mode='MarkdownV2')
        bot.register_next_step_handler(message, set_keyword)

    def set_keyword(message):
        keyword = message.text.strip()
        if '@' not in keyword:
            bot.reply_to(message, "❌ La palabra clave debe incluir el símbolo *@*. Inténtalo de nuevo con /start")
            return
        
        bot_settings['keyword'] = keyword
        print(f"✅ Palabra clave guardada: {keyword}")
        bot.reply_to(message, f"✅ *Palabra clave* configurada: {escape_markdown(keyword)}\nAhora dime la *palabra de reemplazo* (incluye @):")
        bot.register_next_step_handler(message, set_replacement)

    def set_replacement(message):
        replacement = message.text.strip()
        if '@' not in replacement:
            bot.reply_to(message, "❌ La palabra de reemplazo debe incluir el símbolo *@*. Inténtalo de nuevo con /start")
            return
        
        bot_settings['replacement'] = replacement
        print(f"✅ Palabra de reemplazo guardada: {replacement}")
        bot.reply_to(message, f"✅ *Palabra de reemplazo* configurada: {escape_markdown(replacement)}\nEl bot está listo para reemplazar automáticamente 🚦")

    # 🔍 Detectar mensajes con la palabra clave y reemplazar conservando el formato
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
        formatted_text = escape_markdown(new_text)
        
        # 🚮 Eliminar el mensaje original
        try:
            bot.delete_message(message.chat.id, message.message_id)
            print("🗑️ Mensaje original eliminado correctamente")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el mensaje: {e}")

        # Enviar el mensaje reemplazado con el formato conservado
        bot.send_message(message.chat.id, formatted_text, parse_mode='MarkdownV2')
        print(f"📤 Mensaje enviado: {formatted_text}")

    # 🚦 Iniciar el bot secundario con timeout prolongado
    print(f"🤖 Bot @{bot_name} en funcionamiento...")
    bot.polling(timeout=30, long_polling_timeout=30)

# 🚦 Función para escapar caracteres especiales en MarkdownV2
def escape_markdown(text: str) -> str:
    """
    Escapa los caracteres especiales para MarkdownV2.
    """
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

# 🚦 Iniciar el Bot Master
print("🤖 Bot Master en funcionamiento...")
bot_master.polling(timeout=30, long_polling_timeout=30)

