import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
# Import the necessary handler for group tracking
from telegram.ext import ChatMemberHandler 
from telegram import ChatMember

# 1. Configuration (use the same values)
TOKEN = '8201716701:AAEjfIHh4cJh1p8zWwBhYjl4B4q3HOrqvdY' 
GROUP_ID = -1003172282694 # Replace with your actual group's ID

# 2. Simulated Database (Must be replaced with a real DB)
# Stores: user_id: {'invite_link_name': 'unique_hash', 'stars': 0, 'invited_count': 0}
# Initializing data for example purposes
user_data = {
    # Example user data
    12345678: {'invite_link_name': 'user_12345678', 'stars': 5, 'invited_count': 22} 
} 

# --- CORE LOGIC FUNCTIONS (Reused) ---

# This function creates/retrieves the unique link object from Telegram API
async def create_unique_link(user_id: int, bot: telegram.Bot, chat_id: int) -> str:
    """Creates or retrieves a unique invite link for the user."""
    invite_link_name = f"user_{user_id}" 
    
    if user_id not in user_data:
        # Initialize user data if they are new
        user_data[user_id] = {'invite_link_name': invite_link_name, 'stars': 0, 'invited_count': 0}

    # API call to create the link (or retrieve existing link)
    invite_link_object = await bot.create_chat_invite_link(
        chat_id=chat_id,
        name=invite_link_name,
        member_limit=None 
    )
    return invite_link_object.invite_link


# --- HANDLERS ---

# 1. /start command handler (Sends the main menu with new buttons)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the main menu with Share & Withdraw options."""
    
    # Define the buttons
    keyboard = [
        [
            InlineKeyboardButton("🔗 Share & Earn", callback_data="btn_getlink"),
            InlineKeyboardButton("⭐ Withdraw", callback_data="btn_withdraw")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Welcome to the Star Earning Bot! Choose an option below:",
        reply_markup=reply_markup
    )


# 2. Button Press Handler (Handles 'btn_getlink' and 'btn_withdraw')
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses and directs to the appropriate function."""
    
    query = update.callback_query
    await query.answer() # Acknowledge the press

    if query.data == 'btn_getlink':
        await handle_get_link(query, context)
    
    elif query.data == 'btn_withdraw':
        await handle_withdraw(query, context)


# 3. Logic for 'Share & Earn' button (btn_getlink)
async def handle_get_link(query: telegram.CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Generates the unique invite link and sends it to the user."""
    user_id = query.from_user.id
    
    try:
        # Create or retrieve the unique link
        link = await create_unique_link(user_id, context.bot, GROUP_ID)
        
        # Get current stars to show the incentive
        stars = user_data.get(user_id, {}).get('stars', 0)

        response_text = (
            f"**My Group Link:**\n`{link}`\n\n"
            f"**Distribution:** Share this link to invite members. "
            f"Invite 4 members to earn 1 Star ⭐.\n\n"
            f"You currently have ⭐ **{stars}** stars."
        )
        
    except telegram.error.BadRequest:
        response_text = (
            "❌ **ERROR:** Cannot create the link. "
            "Please ensure the bot is an Admin in the group with 'Manage Invite Links' permission."
        )

    await query.edit_message_text(text=response_text, parse_mode=telegram.constants.ParseMode.MARKDOWN)


# 4. Logic for 'Withdraw' button (btn_withdraw)
async def handle_withdraw(query: telegram.CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's stars and invited member count."""
    user_id = query.from_user.id
    
    # Retrieve user data, defaulting to 0 if the user is new
    data = user_data.get(user_id, {'stars': 0, 'invited_count': 0})
    
    total_stars = data['stars']
    invited_members = data['invited_count']
    
    response_text = (
        f"**Withdrawal & Stats**\n\n"
        f"⭐ **Total Stars:** {total_stars}\n"
        f"👥 **Invited Members:** {invited_members}\n\n"
        f"To withdraw, please contact an administrator." 
        # You would add your actual withdrawal instructions here
    )

    # Re-show the main buttons after displaying stats
    keyboard = [
        [
            InlineKeyboardButton("🔗 Share & Earn", callback_data="btn_getlink"),
            InlineKeyboardButton("⭐ Withdraw", callback_data="btn_withdraw")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=response_text, 
        reply_markup=reply_markup,
        parse_mode=telegram.constants.ParseMode.MARKDOWN
    )


# --- MAIN SETUP ---

def main():
    """Start the bot."""
    application = Application.builder().token(8201716701:AAEjfIHh4cJh1p8zWwBhYjl4B4q3HOrqvdY).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    
    # Handles button presses for both Share & Earn and Withdraw
    application.add_handler(CallbackQueryHandler(button_callback)) 
    
    # You MUST include the ChatMemberHandler from the previous example
    # to actually track the invites and grant stars!
    # application.add_handler(ChatMemberHandler(track_new_member, chat_id=GROUP_ID))
    
    print("Bot is running...")
    application.run_polling(allowed_updates=[Update.COMMAND, Update.CALLBACK_QUERY])

if __name__ == '__main__':
    main()
