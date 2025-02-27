import telebot
from telebot import types
import importlib
import os

# Token del Bot Master
MASTER_TOKEN = '7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g'
bot_master = telebot.TeleBot(MASTER_TOKEN)

# Diccionario para almacenar los bots secundarios
connected_bots = {}

# 🚦 Solicitar el token del nuevo bot
@bot_master.message_handler(commands=['addbot'])
def request_token(message):
    msg = bot_master.reply_to(message, "🤖 Por favor, envía el *token* del bot secundario:")
    bot_master.register_next_step_handler(msg, add_bot)

# 🚦 Conectar el bot secundario con el token proporcionado
def add_bot(message):
    token = message.text.strip()
    try:
        new_bot = telebot.TeleBot(token)
        bot_info = new_bot.get_me()
        bot_name = bot_info.username
        
        if bot_name in connected_bots:
            bot_master.reply_to(message, f"❗️ El bot @{bot_name} ya está conectado.")
            return
        
        connected_bots[bot_name] = token
        bot_master.reply_to(message, f"✅ *Token aceptado*. El bot *{bot_name}* está conectado.")

        # Crear el archivo del bot secundario dinámicamente
        create_bot_file(bot_name, token)

    except Exception as e:
        bot_master.reply_to(message, f"❌ *Token inválido*: {str(e)}")

# 🛠️ Crear el archivo del bot secundario
def create_bot_file(bot_name, token):
    bot_code = f'''
import telebot

TOKEN = '{token}'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def greet(message):
    bot.reply_to(message, "Hola 😊 Soy el bot @{bot_name} y estoy aquí para ayudarte!")

print("🤖 Bot @{bot_name} en funcionamiento...")
bot.polling()
'''
    # Guardar el archivo dinámicamente
    file_path = f'bots/{bot_name}.py'
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(bot_code)

    # Ejecutar el bot secundario dinámicamente
    os.system(f'python {file_path} &')

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

