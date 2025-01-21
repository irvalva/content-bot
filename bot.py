import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuración del logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Diccionario para almacenar los datos del usuario
user_data = {}

# Función para iniciar el bot con un menú de texto
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        ["🔄 Configurar Reemplazo"],
        ["❌ Cancelar"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_text(
        "👋 ¡Bienvenido! Usa el menú de opciones para comenzar.",
        reply_markup=reply_markup
    )

# Captura la palabra/frase a reemplazar
async def recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if text == "🔄 Configurar Reemplazo":
        await update.message.reply_text("✏️ Escribe la palabra o frase que deseas reemplazar:")
        context.user_data["estado"] = "esperando_texto_a_reemplazar"

    elif text == "❌ Cancelar":
        context.user_data.clear()  # Elimina la configuración actual
        await update.message.reply_text("❌ Reemplazo cancelado. Escribe /start para volver al menú.")

    elif context.user_data.get("estado") == "esperando_texto_a_reemplazar":
        context.user_data["texto_a_reemplazar"] = text
        context.user_data["estado"] = "esperando_nuevo_texto"
        await update.message.reply_text("✅ Ahora escribe el nuevo texto que reemplazará al anterior:")

    elif context.user_data.get("estado") == "esperando_nuevo_texto":
        context.user_data["nuevo_texto"] = text
        context.user_data["estado"] = "configuracion_completa"
        await update.message.reply_text("✅ ¡Listo! Ahora reenvíame un mensaje y lo modificaré según tu configuración.")

# Función para procesar mensajes reenviados y aplicar el reemplazo
async def process_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto_a_reemplazar = context.user_data.get("texto_a_reemplazar")
    nuevo_texto = context.user_data.get("nuevo_texto")

    if texto_a_reemplazar and nuevo_texto:
        mensaje = update.message.text
        mensaje_modificado = mensaje.replace(texto_a_reemplazar, nuevo_texto)
        
        if mensaje != mensaje_modificado:
            await update.message.reply_text(mensaje_modificado)
    else:
        return  # Si no hay configuración, ignora el mensaje

# Configuración del bot y los handlers
def main():
    application = Application.builder().token("7769164457:AAGn_cwagig2jMpWyKubGIv01-kwZ1VuW0g").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_texto))
    application.add_handler(MessageHandler(filters.FORWARDED & filters.TEXT, process_posts))

    application.run_polling()

if __name__ == "__main__":
    main()