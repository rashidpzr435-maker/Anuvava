from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("asslamu allyikkum")

app = ApplicationBuilder().token("8201716701:AAEjfIHh4cJh1p8zWwBhYjl4B4q3HOrqvdY").build()
app.add_handler(CommandHandler("start", start))

print("🤖 Bot is running...")
app.run_polling()
