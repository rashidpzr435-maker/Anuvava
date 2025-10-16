from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name

    message = f"""
👋 Welcome, {user_first_name}, to **Stars Earn!**

📈 **Stars Earn — Invite & Earn**
Earn stars by inviting friends and promoting our community!

✨ **Features**
• 👥 Invite members to our group & channel  
• 💫 Earn stars for every invite  
• 🤖 Promote your bot or profile  

💡 4 invited members = 1 ⭐ Star

*By using this bot, you agree to our Privacy Policy.*
"""

    keyboard = [
        [InlineKeyboardButton("💰 Earnings", callback_data="earnings")],
        [InlineKeyboardButton("🌟 Get Stars", callback_data="get_stars")],
        [InlineKeyboardButton("ℹ️ Using Info", callback_data="using_info")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)

# --- Button Handlers ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "earnings":
        await query.edit_message_text("💰 *Your Earnings:* \nStars: 0 ⭐\nInvites: 0\nRatio: 4 members = 1 star", parse_mode="Markdown")

    elif query.data == "get_stars":
        await query.edit_message_text("🌟 *Get Stars:* \nShare your invite link to earn stars!\n\n🔗 Invite Link: coming soon...", parse_mode="Markdown")

    elif query.data == "using_info":
        await query.edit_message_text("ℹ️ *Using Info:* \nInvite members using your personal link.\nEach 4 members = 1 star.\nEarn stars to unlock rewards!", parse_mode="Markdown")

    elif query.data == "contact":
        await query.edit_message_text("📞 *Contact Admin:* \n@YourTelegramID", parse_mode="Markdown")

# --- Run Bot ---
app = ApplicationBuilder().token("8201716701:AAEjfIHh4cJh1p8zWwBhYjl4B4q3HOrqvdY").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

print("🤖 Bot is running...")
app.run_polling()
