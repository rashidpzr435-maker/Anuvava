from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot activated and running!")

app = ApplicationBuilder().token("7656174870:AAH69ny2kQ0DE2XmKG3hwnBlnlhSi_ho9EQ").build()
app.add_handler(CommandHandler("start", start))

print("🤖 Bot is running...")
app.run_polling()
