import asyncio
import logging
from datetime import datetime, timedelta
import aiosqlite
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatInviteLink,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

# ========== CONFIG ==========
BOT_TOKEN = "8201716701:AAEjfIHh4cJh1p8zWwBhYjl4B4q3HOrqvdY"
# Default invite expiration (hours)
DEFAULT_EXPIRE_HOURS = 24
# Reward rule: how many invited members produce 1 star
INVITE_PER_STAR = 4
# Money value per star in ₹ (INR)
RS_PER_STAR = 1
# Minimum withdrawal (in ₹ / stars)
MIN_WITHDRAWAL_RS = 50
# SQLite DB file
DB_PATH = "invite_bot.db"
# ============================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- Database helpers ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stars REAL DEFAULT 0,
            invites_count INTEGER DEFAULT 0,
            invite_progress INTEGER DEFAULT 0 -- counts invites toward next star
        )
        """
        )
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS invite_links (
            code TEXT PRIMARY KEY,
            creator_id INTEGER,
            chat_id INTEGER,
            invite_link TEXT,
            expire_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invite_link_code TEXT,
            invitee_id INTEGER,
            invitee_username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount_stars REAL,
            amount_rs REAL,
            status TEXT DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        await db.commit()


async def ensure_user(user_id: int, username: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)
            """,
            (user_id, username or ""),
        )
        await db.commit()


# ---------- Invite link creation ----------
import secrets


async def create_invite_link_for_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, creator_id: int, hours: int):
    # create a unique code so we can track which link was used
    code = secrets.token_urlsafe(6)
    expire_date = datetime.utcnow() + timedelta(hours=hours)

    # Use Telegram API to create an invite link (requires bot to be admin)
    bot = context.bot
    try:
        chat_invite = await bot.create_chat_invite_link(
            chat_id=chat_id,
            expire_date=expire_date,
            name=f"ref-{code}",
            member_limit=0,
            creates_join_request=False,
        )
    except Exception as e:
        logger.exception("Failed to create invite link: %s", e)
        raise

    # Save to DB
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO invite_links (code, creator_id, chat_id, invite_link, expire_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (code, creator_id, chat_id, chat_invite.invite_link, expire_date.isoformat()),
        )
        await db.commit()

    return code, chat_invite.invite_link, expire_date


# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await ensure_user(user.id, user.username)
    await update.message.reply_text(
        "Hello! Use /generate to create an expiring invite link for this group.\n"
        "Use /stats to see your invites and stars.\n"
        "Rules: every 4 invited members => 1 star. 1 star = ₹1. Minimum withdraw: ₹50."
    )


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # only allow in groups or supergroups
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Please use /generate inside the target group where the bot is admin.")
        return

    user = update.effective_user
    await ensure_user(user.id, user.username)

    # optional: allow hours arg
    args = context.args
    hours = DEFAULT_EXPIRE_HOURS
    if args:
        try:
            h = int(args[0])
            if 1 <= h <= 168:
                hours = h
        except:
            pass

    try:
        code, link, expire_date = await create_invite_link_for_user(context, update.effective_chat.id, user.id, hours)
    except Exception as e:
        await update.message.reply_text("Failed to create invite link. Make sure I am admin with invite-link permission.")
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Withdraw (request)", callback_data="withdraw:start")]])
    await update.message.reply_text(
        f"Invite link created by {user.mention_html()} (code: {code})\n\n"
        f"Link: {link}\nExpires (UTC): {expire_date.isoformat()}\n\n"
        "Share this link — when people join with it, you'll get credit.",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    When new members join the group, Telegram may include chat_invite_link info in update.message.chat_invite_link
    We record the invite usage when we can find which link (by name/code) was used.
    """
    msg = update.message
    if not msg or not msg.new_chat_members:
        return

    # If Telegram provided the invite link info
    invite_link_obj = getattr(msg, "chat_invite_link", None)
    if invite_link_obj:
        # The invite's name or invite_link might include our code (we created name="ref-<code>")
        name = getattr(invite_link_obj, "name", "") or ""
        # fallback: full invite_link string
        full_link = getattr(invite_link_obj, "invite_link", "") or ""

        # attempt to extract code from name "ref-<code>"
        code = None
        if name.startswith("ref-"):
            code = name.split("ref-")[1].strip()
        else:
            # maybe we stored the full link; attempt to match stored invite_link
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT code FROM invite_links WHERE invite_link = ?", (full_link,))
                row = await cur.fetchone()
                if row:
                    code = row[0]

        if not code:
            # couldn't map; ignore
            logger.info("New member joined but invite link code not recognized.")
            return

        # For each new_chat_member, record invite and credit creator
        for new_member in msg.new_chat_members:
            # ignore if the new member is a bot
            if new_member.is_bot:
                continue

            async with aiosqlite.connect(DB_PATH) as db:
                # register invite record
                await db.execute(
                    """
                    INSERT INTO invites (invite_link_code, invitee_id, invitee_username)
                    VALUES (?, ?, ?)
                    """,
                    (code, new_member.id, new_member.username or ""),
                )

                # find creator
                cur = await db.execute("SELECT creator_id FROM invite_links WHERE code = ?", (code,))
                row = await cur.fetchone()
                if not row:
                    continue
                creator_id = row[0]

                # ensure user exists
                await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (creator_id, ""))

                # update invites_count and progress / stars
                cur2 = await db.execute("SELECT invites_count, invite_progress, stars FROM users WHERE user_id = ?", (creator_id,))
                creator_row = await cur2.fetchone()
                if creator_row:
                    invites_count, invite_progress, stars = creator_row
                else:
                    invites_count = invite_progress = stars = 0

                invites_count = (invites_count or 0) + 1
                invite_progress = (invite_progress or 0) + 1

                # If invite_progress reaches INVITE_PER_STAR, award star(s)
                new_stars_awarded = 0
                while invite_progress >= INVITE_PER_STAR:
                    invite_progress -= INVITE_PER_STAR
                    new_stars_awarded += 1

                stars = (stars or 0) + new_stars_awarded

                await db.execute(
                    """
                    UPDATE users SET invites_count = ?, invite_progress = ?, stars = ? WHERE user_id = ?
                    """,
                    (invites_count, invite_progress, stars, creator_id),
                )
                await db.commit()

                # Notify the creator via DM if bot can message them
                try:
                    await context.bot.send_message(
                        chat_id=creator_id,
                        text=f"🎉 You got credit for inviting @{new_member.username or new_member.full_name}! "
                             f"Total invites: {invites_count}. Stars: {stars:.2f} (progress toward next star: {invite_progress}/{INVITE_PER_STAR})."
                    )
                except Exception:
                    # might be unable to message user
                    logger.debug("Couldn't message creator user %s", creator_id)
    else:
        # no invite link info; can't attribute credit
        logger.info("New chat members but no chat_invite_link information available.")


# ---------- Stats ----------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await ensure_user(user.id, user.username)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT invites_count, invite_progress, stars FROM users WHERE user_id = ?", (user.id,))
        row = await cur.fetchone()
        if not row:
            invites_count = invite_progress = stars = 0
        else:
            invites_count, invite_progress, stars = row

        # compute monetary value
        value_rs = (stars or 0) * RS_PER_STAR

        # show top inviters in group (simple leaderboard)
        top_cur = await db.execute("SELECT user_id, username, invites_count, stars FROM users ORDER BY invites_count DESC LIMIT 5")
        top_rows = await top_cur.fetchall()

    text = (
        f"Your invites: {invites_count or 0}\n"
        f"Invite progress toward next star: {invite_progress or 0}/{INVITE_PER_STAR}\n"
        f"Stars earned: {stars or 0:.2f}\n"
        f"Equivalent ₹: {value_rs:.2f}\n\n"
        f"Reward rule: {INVITE_PER_STAR} invites → 1 star (1 star = ₹{RS_PER_STAR})\n"
    )
    if value_rs >= MIN_WITHDRAWAL_RS:
        withdraw_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Request Withdraw (min ₹{MIN_WITHDRAWAL_RS})", callback_data="withdraw:start")]])
        await update.message.reply_text(text, reply_markup=withdraw_kb)
    else:
        await update.message.reply_text(text)

    # show leaderboard
    if top_rows:
        lb = "\nTop inviters:\n"
        for idx, (uid, uname, icount, s) in enumerate(top_rows, start=1):
            lb += f"{idx}. {uname or uid} — invites: {icount}, stars: {s:.2f}\n"
        await update.message.reply_text(lb)


# ---------- Withdraw flow ----------
async def callback_query_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "withdraw:start":
        user = update.effective_user
        # fetch user's stars
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT stars FROM users WHERE user_id = ?", (user.id,))
            row = await cur.fetchone()
            stars = row[0] if row else 0
            rs_value = (stars or 0) * RS_PER_STAR

        if rs_value < MIN_WITHDRAWAL_RS:
            await query.edit_message_text(f"Your balance is ₹{rs_value:.2f}. Minimum withdraw is ₹{MIN_WITHDRAWAL_RS}. Keep inviting!")
            return

        # ask for withdrawal method info (collect via next message)
        await query.edit_message_text(f"You have ₹{rs_value:.2f}. Reply to me with withdrawal details (UPI ID or bank details) to request withdrawal.")
        # set a simple conversation state: store in user_data that we're awaiting withdraw details
        context.user_data["awaiting_withdraw"] = True


async def text_handler_collect_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If awaiting withdraw details
    if not context.user_data.get("awaiting_withdraw"):
        return

    user = update.effective_user
    details = update.message.text.strip()

    # compute user's current balance
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT stars FROM users WHERE user_id = ?", (user.id,))
        row = await cur.fetchone()
        stars = row[0] if row else 0
        rs_value = (stars or 0) * RS_PER_STAR

        if rs_value < MIN_WITHDRAWAL_RS:
            await update.message.reply_text(f"Your balance is ₹{rs_value:.2f}, below minimum withdraw ₹{MIN_WITHDRAWAL_RS}.")
            context.user_data.pop("awaiting_withdraw", None)
            return

        # We'll withdraw full amount available (or you could ask how much). Here: withdraw all stars as example.
        amount_rs = rs_value
        amount_stars = stars

        # record withdrawal
        await db.execute(
            "INSERT INTO withdrawals (user_id, amount_stars, amount_rs, status) VALUES (?, ?, ?, 'pending')",
            (user.id, amount_stars, amount_rs),
        )

        # reset user's stars to 0 after requesting (or you can deduct)
        await db.execute("UPDATE users SET stars = 0 WHERE user_id = ?", (user.id,))
        await db.commit()

    context.user_data.pop("awaiting_withdraw", None)

    # notify admin (you should replace ADMIN_CHAT_ID with your admin/group chat id)
    ADMIN_CHAT_ID = None  # <--- set to your admin id to receive withdraw requests via bot
    notif = f"Withdrawal requested by {user.mention_html()}:\nAmount: ₹{amount_rs:.2f} ({amount_stars:.2f} stars)\nDetails: {details}\nStatus: pending"
    await update.message.reply_text("Withdrawal request received. Admin will process it soon. Thank you!")
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(ADMIN_CHAT_ID, notif, parse_mode="HTML")
        except Exception:
            logger.debug("Couldn't notify admin.")


# ---------- Admin command to view pending withdrawals ----------
async def pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # this should be protected — only allow for admin or specific user ids
    admin_ids = {update.effective_user.id}  # you can add specific admin user ids here
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Unauthorized.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, user_id, amount_rs, status, requested_at FROM withdrawals WHERE status = 'pending' ORDER BY requested_at DESC")
        rows = await cur.fetchall()

    if not rows:
        await update.message.reply_text("No pending withdrawals.")
        return

    text = "Pending withdrawals:\n"
    for r in rows:
        text += f"#{r[0]} user:{r[1]} amount: ₹{r[2]:.2f} requested: {r[4]}\n"
    await update.message.reply_text(text)


# ---------- main ----------
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("pending_withdrawals", pending_withdrawals))

    # new chat members handler
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))

    # callback queries (withdraw)
    app.add_handler(CallbackQueryHandler(callback_query_router))

    # collect withdrawal details via plain text when awaiting
    app.add_handler(MessageHandler(filters.TEXT & filters.PrivateChat(), text_handler_collect_withdraw))

    logger.info("Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
