import telebot
import threading
from telebot import types

# Token del Bot Master
MASTER_TOKEN = '7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g'
bot_master = telebot.TeleBot(MASTER_TOKEN, parse_mode='MarkdownV2')

# Diccionario para almacenar los bots secundarios en memoria
connected_bots = {}

# 🚦 Solicitar el token del nuevo bot
@bot_master.message_handler(commands=['addbot'])
def request_token(message):
    msg = bot_master.reply_to(message, "🤖 Por favor, envía el *token* del bot secundario:")
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
        bot_master.reply_to(message, f"✅ *Token aceptado*. El bot *{bot_name}* está conectado.")

        # Ejecutar el bot secundario en un hilo separado
        threading.Thread(target=start_secondary_bot, args=(new_bot, bot_name)).start()

    except Exception as e:
        bot_master.reply_to(message, f"❌ *Token inválido*: {str(e)}")

# 📋 Comando para listar los bots conectados
@bot_master.message_handler(commands=['bots'])
def list_bots(message):
    if connected_bots:
        bot_list = '\n'.join([f"- @{name}" for name in connected_bots.keys()])
        bot_master.reply_to(message, f"🤖 Bots conectados:\n{bot_list}")
    else:
        bot_master.reply_to(message, "🚫 No hay bots conectados.")

# 🚦 Función para iniciar el bot secundario
def start_secondary_bot(bot, bot_name):
    # Almacenamiento dinámico de la palabra clave y la palabra de reemplazo
    bot_settings = {
        'keyword': None,
        'replacement': None
    }

    # 🚦 Comando /start para iniciar la configuración
    @bot.message_handler(commands=['start'])
    def greet(message):
        bot.reply_to(message, "👋 ¡Hola! Soy tu bot configurable 😊\nPor favor, dime la *palabra clave* que debo detectar (incluye @):")
        bot.register_next_step_handler(message, set_keyword)

    # 🛠️ Configurar la palabra clave
    def set_keyword(message):
        keyword = message.text.strip()
        if '@' not in keyword:
            bot.reply_to(message, "❌ La palabra clave debe incluir el símbolo *@*. Inténtalo de nuevo con /start")
            return
        
        bot_settings['keyword'] = keyword
        bot.reply_to(message, f"✅ *Palabra clave* configurada: {keyword}\nAhora dime la *palabra de reemplazo* (incluye @):")
        bot.register_next_step_handler(message, set_replacement)

    # 🛠️ Configurar la palabra de reemplazo
    def set_replacement(message):
        replacement = message.text.strip()
        if '@' not in replacement:
            bot.reply_to(message, "❌ La palabra de reemplazo debe incluir el símbolo *@*. Inténtalo de nuevo con /start")
            return
        
        bot_settings['replacement'] = replacement
        bot.reply_to(message, f"✅ *Palabra de reemplazo* configurada: {replacement}\nEl bot está listo para reemplazar automáticamente 🚦")

    # 🔍 Detectar mensajes con la palabra clave y reemplazar conservando el formato
    @bot.message_handler(func=lambda message: bot_settings['keyword'] and bot_settings['keyword'] in message.text)
    def auto_replace(message):
        keyword = bot_settings['keyword']
        replacement = bot_settings['replacement']
        new_text = message.text.replace(keyword, replacement)
        
        formatted_text = escape_markdown(new_text, message.entities or [])
        
        # 🚮 Eliminar el mensaje original
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el mensaje: {e}")

        # Enviar el mensaje reemplazado con el formato conservado
        bot.send_message(message.chat.id, formatted_text, parse_mode='MarkdownV2')

# 🛠️ Función para escapar caracteres especiales en MarkdownV2
def escape_markdown(text, entities):
    md_text = text
    for entity in entities:
        start, end = entity.offset, entity.offset + entity.length
        original_text = text[start:end]
        if entity.type == 'bold':
            md_text = md_text.replace(original_text, f"*{original_text}*")
        elif entity.type == 'italic':
            md_text = md_text.replace(original_text, f"_{original_text}_")
        elif entity.type == 'underline':
            md_text = md_text.replace(original_text, f"__{original_text}__")
        elif entity.type == 'strikethrough':
            md_text = md_text.replace(original_text, f"~{original_text}~")
        elif entity.type == 'code':
            md_text = md_text.replace(original_text, f"`{original_text}`")
        elif entity.type == 'pre':
            md_text = md_text.replace(original_text, f"```{original_text}```")
        elif entity.type == 'text_link':
            md_text = md_text.replace(original_text, f"[{original_text}]({entity.url})")
    return telebot.util.escape_markdown(md_text, version=2)

# 🚦 Iniciar el bot secundario
print("🤖 Bot Master en funcionamiento...")
bot_master.polling()

