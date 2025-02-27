import telebot
import threading

# Token del Bot Master
MASTER_TOKEN = '7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g'
bot_master = telebot.TeleBot(MASTER_TOKEN)

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
        new_bot = telebot.TeleBot(token)
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

# 🚦 Función para iniciar el bot secundario
def start_secondary_bot(bot, bot_name):
    @bot.message_handler(commands=['start'])
    def greet(message):
        bot.reply_to(message, f"Hola 😊 Soy el bot @{bot_name} y estoy aquí para ayudarte!")
    
    print(f"🤖 Bot @{bot_name} en funcionamiento...")
    bot.polling()

# 📋 Comando para listar los bots conectados
@bot_master.message_handler(commands=['bots'])
def list_bots(message):
    if connected_bots:
        bot_list = '\n'.join([f"- @{name}" for name in connected_bots.keys()])
        bot_master.reply_to(message, f"🤖 Bots conectados:\n{bot_list}")
    else:
        bot_master.reply_to(message, "🚫 No hay bots conectados.")

# 🚦 Iniciar el Bot Master
print("🤖 Bot Master en funcionamiento...")
bot_master.polling()
