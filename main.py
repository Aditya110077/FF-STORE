# -*- coding: utf-8 -*-
import logging
import urllib.parse
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand,
    BotCommandScopeDefault, BotCommandScopeChat
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# Emoji escapes
E_FIRE   = "\U0001F525"
E_BOX    = "\U0001F4E6"
E_USER   = "\U0001F464"
E_MONEY  = "\U0001F4B0"
E_GIFT   = "\U0001F381"
E_TROPHY = "\U0001F3C6"
E_CHART  = "\U0001F4CA"
E_PHONE  = "\U0001F4DE"
E_INFO   = "\u2139\uFE0F"
E_HELP   = "\u2753"
E_GREEN  = "\U0001F7E2"
E_BLUE   = "\U0001F535"
E_PURPLE = "\U0001F7E3"
E_YELLOW = "\U0001F7E1"
E_BOLT   = "\u26A1"
E_GEM    = "\U0001F48E"
E_CROWN  = "\U0001F451"
E_CHECK  = "\u2705"
E_CROSS  = "\u274C"
E_HOUR   = "\u23F3"
E_HEART  = "\u2764\uFE0F"
E_SHIELD = "\U0001F6E1\uFE0F"
E_WAVE   = "\U0001F44B"
E_GAME   = "\U0001F3AE"
E_JOIN   = "\U0001F4E2"
E_BACK   = "\U0001F519"
E_ROCKET = "\U0001F680"
E_STAR   = "\u2B50"
E_LINE   = "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"

# ================= CONFIG =================
BOT_TOKEN = "8801453801:AAGLPbGF2-BvWMJ3E7K2sHeTMQPXZDRFHXU"
OWNER_ID = 6863389453
OWNER_USERNAME = "@CURRENTTTTTTTT"
UPI_ID = "adityagupta0018@axl"
UPI_NAME = "Store Owner"
SUPPORT_LINK = "https://t.me/CURRENTTTTTTTT"
FORCE_CHANNELS = ["@CURRENTTTTTTTT", "@newchannel1109"]
FORCE_LINKS = {
    "@CURRENTTTTTTTT": "https://t.me/CURRENTTTTTTTT",
    "@newchannel1109": "https://t.me/newchannel1109",
}
REFER_BONUS = 0.5
DB_FILE = "store.db"
# ==========================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLANS = {
    "p15":  {"name": "15 Days",  "price": 70,  "days": 15,  "emoji": E_FIRE, "color": E_GREEN},
    "p30":  {"name": "30 Days",  "price": 120, "days": 30,  "emoji": E_BOLT, "color": E_BLUE},
    "p60":  {"name": "60 Days",  "price": 250, "days": 60,  "emoji": E_GEM,  "color": E_PURPLE},
    "p120": {"name": "120 Days", "price": 450, "days": 120, "emoji": E_CROWN,"color": E_YELLOW},
}

# ================= DATABASE =================
def db_init():
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        balance REAL DEFAULT 0, banned INTEGER DEFAULT 0,
        referred_by INTEGER DEFAULT 0, joined_at TEXT,
        last_seen TEXT, active_until TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_key TEXT,
        plan_name TEXT, amount INTEGER, days INTEGER, utr TEXT, status TEXT,
        created_at TEXT, verified_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS utrs (
        utr TEXT PRIMARY KEY, user_id INTEGER, order_id INTEGER, created_at TEXT)""")
    con.commit(); con.close()
    print("[OK] Database ready")

def db_add_user(uid, uname, fname, ref_by=0):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, referred_by, joined_at, last_seen) VALUES (?,?,?,?,?,?)",
              (uid, uname, fname, ref_by, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute("UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
              (uname, fname, datetime.now().isoformat(), uid))
    con.commit(); con.close()

def db_is_new(uid):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone(); con.close()
    return row is None

def db_is_banned(uid):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT banned FROM users WHERE user_id=?", (uid,))
    row = c.fetchone(); con.close()
    return row and row[0] == 1

def db_ban(uid, val):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("UPDATE users SET banned=? WHERE user_id=?", (val, uid))
    con.commit(); con.close()

def db_add_balance(uid, amt):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, uid))
    con.commit(); con.close()

def db_get_user(uid):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone(); con.close()
    return row

def db_create_order(uid, key, plan, utr):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("""INSERT INTO orders (user_id, plan_key, plan_name, amount, days, utr, status, created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (uid, key, plan["name"], plan["price"], plan["days"], utr, "pending", datetime.now().isoformat()))
    oid = c.lastrowid; con.commit(); con.close()
    return oid

def db_update_order(oid, status):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("UPDATE orders SET status=?, verified_at=? WHERE id=?",
              (status, datetime.now().isoformat(), oid))
    con.commit(); con.close()

def db_get_order(oid):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (oid,))
    row = c.fetchone(); con.close()
    return row

def db_user_orders(uid, limit=10):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit))
    rows = c.fetchall(); con.close()
    return rows

def db_pending_orders():
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id DESC")
    rows = c.fetchall(); con.close()
    return rows

def db_stats():
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT COUNT(*) FROM users"); users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=0"); active_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='verified'"); verified = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'"); pending = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM orders WHERE status='verified'"); revenue = c.fetchone()[0] or 0
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (today + "%",))
    today_users = c.fetchone()[0]
    now = datetime.now().isoformat()
    c.execute("SELECT COUNT(*) FROM users WHERE active_until > ?", (now,))
    active_subs = c.fetchone()[0]
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    c.execute("SELECT COUNT(*) FROM users WHERE last_seen > ?", (yesterday,))
    online_24h = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (today + "%",))
    today_orders = c.fetchone()[0]
    con.close()
    return {"users": users, "active_users": active_users, "total": total,
            "verified": verified, "pending": pending, "revenue": revenue,
            "today_users": today_users, "active_subs": active_subs,
            "online_24h": online_24h, "today_orders": today_orders}

def db_all_users():
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT user_id FROM users WHERE banned=0")
    rows = [r[0] for r in c.fetchall()]; con.close()
    return rows

def db_utr_used(utr):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM utrs WHERE utr=?", (utr,))
    row = c.fetchone(); con.close()
    return row is not None

def db_save_utr(utr, uid, oid):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("INSERT OR IGNORE INTO utrs (utr, user_id, order_id, created_at) VALUES (?,?,?,?)",
              (utr, uid, oid, datetime.now().isoformat()))
    con.commit(); con.close()

def db_refer_count(uid):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    count = c.fetchone()[0]; con.close()
    return count

def db_today_orders():
    today = datetime.now().strftime("%Y-%m-%d")
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM orders WHERE created_at LIKE ? ORDER BY id DESC", (today + "%",))
    rows = c.fetchall(); con.close()
    return rows

def fmt_bal(v):
    if v is None: return "0"
    if v == int(v): return str(int(v))
    return f"{v:.2f}".rstrip('0').rstrip('.')

# ================= FORCE JOIN (MULTI CHANNEL) =================
async def is_joined(user_id, ctx):
    for ch in FORCE_CHANNELS:
        try:
            member = await ctx.bot.get_chat_member(ch, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception as e:
            logger.warning(f"Force join check failed for {ch}: {e}")
    return True

async def force_join_msg(u, ctx):
    kb = []
    for ch in FORCE_CHANNELS:
        kb.append([InlineKeyboardButton(f"{E_JOIN}  Join {ch}", url=FORCE_LINKS[ch])])
    kb.append([InlineKeyboardButton(f"{E_CHECK}  Joined, Try Again", callback_data="check_join")])
    channels_list = "\n".join([f"{E_ROCKET} {ch}" for ch in FORCE_CHANNELS])
    text = (
        f"{E_JOIN}  Join Required\n\n"
        f"Pehle ye channels join karo:\n"
        f"{channels_list}\n\n"
        f"{E_CHECK}  Join ke baad JOINED dabao"
    )
    markup = InlineKeyboardMarkup(kb)
    if hasattr(u, "message") and u.message:
        await u.message.reply_text(text, reply_markup=markup)
    else:
        await u.edit_message_text(text, reply_markup=markup)

# ================= EDIT HELPER =================
async def smart_edit(q, text, kb):
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except Exception:
        try:
            await q.message.reply_text(text, reply_markup=kb)
            try:
                await q.message.delete()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"smart_edit failed: {e}")

# ================= KEYBOARDS =================
def home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E_FIRE}  Buy AutoLike  {E_FIRE}", callback_data="buylike")],
        [InlineKeyboardButton(f"{E_BOX}  My Orders", callback_data="myorders"),
         InlineKeyboardButton(f"{E_USER}  Profile", callback_data="profile")],
        [InlineKeyboardButton(f"{E_MONEY}  Wallet", callback_data="wallet"),
         InlineKeyboardButton(f"{E_GIFT}  Refer & Earn", callback_data="refer")],
        [InlineKeyboardButton(f"{E_TROPHY}  Leaderboard", callback_data="leaderboard"),
         InlineKeyboardButton(f"{E_CHART}  Stats", callback_data="bot_stats")],
        [InlineKeyboardButton(f"{E_PHONE}  Support", url=SUPPORT_LINK),
         InlineKeyboardButton(f"{E_INFO}  About", callback_data="about")],
        [InlineKeyboardButton(f"{E_HELP}  Help", callback_data="help")]
    ])

def plans_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E_GREEN}  {E_FIRE}  15 Days   -   Rs.70", callback_data="select_p15")],
        [InlineKeyboardButton(f"{E_BLUE}  {E_BOLT}  30 Days   -   Rs.120", callback_data="select_p30")],
        [InlineKeyboardButton(f"{E_PURPLE}  {E_GEM}  60 Days   -   Rs.250", callback_data="select_p60")],
        [InlineKeyboardButton(f"{E_YELLOW}  {E_CROWN}  120 Days  -   Rs.450", callback_data="select_p120")],
        [InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E_CHART}  Stats", callback_data="admin_stats"),
         InlineKeyboardButton(f"{E_HOUR}  Pending", callback_data="admin_pending")],
        [InlineKeyboardButton(f"{E_JOIN}  Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(f"{E_BACK}  Close", callback_data="back_home")]
    ])

# ================= COMMANDS SETUP =================
async def setup_commands(app):
    member_cmds = [
        BotCommand("start",       "Start the bot"),
        BotCommand("buy",         "Buy AutoLike"),
        BotCommand("myorders",    "My Orders"),
        BotCommand("profile",     "My Profile"),
        BotCommand("wallet",      "My Wallet"),
        BotCommand("refer",       "Refer and Earn"),
        BotCommand("leaderboard", "Leaderboard"),
        BotCommand("support",     "Support"),
        BotCommand("help",        "Help"),
    ]
    owner_cmds = member_cmds + [
        BotCommand("admin",      "Admin Panel"),
        BotCommand("stats",      "Statistics"),
        BotCommand("pending",    "Pending Orders"),
        BotCommand("todayorders","Today Orders"),
        BotCommand("search",     "Search by UTR"),
        BotCommand("adduser",    "Add AutoLike Direct"),
        BotCommand("broadcast",  "Broadcast"),
        BotCommand("verify",     "Verify Order"),
        BotCommand("reject",     "Reject Order"),
        BotCommand("user",       "User Info"),
        BotCommand("ban",        "Ban User"),
        BotCommand("unban",      "Unban User"),
        BotCommand("addbalance", "Add Balance"),
        BotCommand("myid",       "Check My ID"),
    ]
    await app.bot.set_my_commands(member_cmds, scope=BotCommandScopeDefault())
    try:
        await app.bot.set_my_commands(owner_cmds, scope=BotCommandScopeChat(chat_id=OWNER_ID))
    except Exception as e:
        logger.warning(f"Owner commands set failed: {e}")
    print("[OK] Commands set")

# ================= MEMBER COMMANDS =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    ref_by = 0
    if ctx.args and ctx.args[0].startswith("ref_"):
        try:
            ref_by = int(ctx.args[0].split("_")[1])
            if ref_by == u.id: ref_by = 0
        except (ValueError, IndexError):
            pass
    if db_is_new(u.id):
        db_add_user(u.id, u.username or "", u.first_name or "", ref_by)
        if ref_by:
            db_add_balance(ref_by, REFER_BONUS)
            try:
                await ctx.bot.send_message(ref_by,
                    f"{E_GIFT}  New Referral!\n\n"
                    f"{E_USER}  {u.first_name} ne tera link use kiya.\n"
                    f"{E_MONEY}  Rs.{fmt_bal(REFER_BONUS)} added!")
            except Exception:
                pass
    else:
        db_add_user(u.id, u.username or "", u.first_name or "")
    if db_is_banned(u.id):
        await update.message.reply_text(f"{E_CROSS}  Aapko ban kiya gaya hai.")
        return
    if not await is_joined(u.id, ctx):
        await force_join_msg(update, ctx); return
    s = db_stats()
    await update.message.reply_text(
        f"{E_WAVE}  Welcome {u.first_name}!\n\n"
        f"{E_GAME}  FF AUTOLIKE STORE\n\n"
        f"{E_HEART}  200 Likes Daily Given\n"
        f"{E_BOLT}  Instant Auto-Verify\n"
        f"{E_SHIELD}  100% Safe & Trusted\n"
        f"{E_GEM}  Premium Quality Service\n\n"
        f"{E_LINE}\n"
        f"{E_USER}  Total Users: {s['users']}\n"
        f"{E_CHECK}  Total Orders: {s['verified']}\n"
        f"{E_LINE}\n\n"
        f"Niche se option choose karo",
        reply_markup=home_kb()
    )

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_joined(update.effective_user.id, ctx):
        await force_join_msg(update, ctx); return
    await update.message.reply_text(
        f"{E_GEM}  PRICE LIST\n\n"
        f"{E_GREEN}  {E_FIRE}  15 Days   -   Rs.70\n"
        f"{E_BLUE}  {E_BOLT}  30 Days   -   Rs.120\n"
        f"{E_PURPLE}  {E_GEM}  60 Days   -   Rs.250\n"
        f"{E_YELLOW}  {E_CROWN}  120 Days  -   Rs.450\n\n"
        f"{E_HEART}  200 Likes Daily Given\n\n"
        f"Apna plan choose karo",
        reply_markup=plans_kb()
    )

async def cmd_myorders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rows = db_user_orders(uid, 10)
    if not rows:
        await update.message.reply_text(f"{E_BOX}  Abhi tak koi order nahi hai.\n\n/buy se order karo.")
        return
    text = f"{E_BOX}  MY ORDERS\n\n"
    for r in rows:
        oid, _, pkey, pname, amt, days, utr, status, cat, vat = r
        emoji = E_CHECK if status == "verified" else (E_HOUR if status == "pending" else E_CROSS)
        text += f"{emoji}  #{oid} - {pname} (Rs.{amt})\n"
    await update.message.reply_text(text)

async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = db_get_user(uid)
    if not row:
        await update.message.reply_text(f"{E_CROSS}  User not found."); return
    uname, fname, bal, banned, ref_by, joined = row[1], row[2], row[3], row[4], row[5], row[6]
    refs = db_refer_count(uid)
    active = row[8] if len(row) > 8 else None
    status_text = f"{E_CHECK} ACTIVE" if active and active > datetime.now().isoformat() else f"{E_CROSS} INACTIVE"
    await update.message.reply_text(
        f"{E_USER}  MY PROFILE\n\n"
        f"Name: {fname}\n"
        f"ID: {uid}\n"
        f"Username: @{uname or 'N/A'}\n"
        f"{E_MONEY}  Balance: Rs.{fmt_bal(bal)}\n"
        f"{E_GIFT}  Referrals: {refs}\n"
        f"Status: {status_text}\n"
        f"Joined: {joined[:10]}"
    )

async def cmd_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = db_get_user(uid)
    bal = row[3] if row else 0
    await update.message.reply_text(
        f"{E_MONEY}  MY WALLET\n\n"
        f"Balance: Rs.{fmt_bal(bal)}\n\n"
        f"Add money: {OWNER_USERNAME}"
    )

async def cmd_refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_info = await ctx.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    refs = db_refer_count(uid)
    await update.message.reply_text(
        f"{E_GIFT}  REFER & EARN\n\n"
        f"Tera Link:\n{ref_link}\n\n"
        f"{E_CHART}  Referrals: {refs}\n"
        f"{E_MONEY}  Earned: Rs.{fmt_bal(refs * REFER_BONUS)}\n\n"
        f"Rs.{fmt_bal(REFER_BONUS)} per successful refer"
    )

async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("""SELECT first_name, referred_by, COUNT(*) as cnt FROM users 
                 WHERE referred_by != 0 GROUP BY referred_by ORDER BY cnt DESC LIMIT 10""")
    rows = c.fetchall()
    con.close()
    if not rows:
        await update.message.reply_text(f"{E_TROPHY}  Leaderboard\n\nAbhi koi refer nahi hua.")
        return
    text = f"{E_TROPHY}  REFERRAL LEADERBOARD\n\n"
    for i, (name, uid, cnt) in enumerate(rows):
        text += f"{i+1}. {name or 'User'} - {cnt} refs\n"
    await update.message.reply_text(text)

async def cmd_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{E_PHONE}  SUPPORT\n\nContact: {OWNER_USERNAME}")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{E_HELP}  HELP\n\n"
        "/start - Home\n"
        "/buy - Buy\n"
        "/myorders - Orders\n"
        "/profile - Profile\n"
        "/wallet - Wallet\n"
        "/refer - Refer\n"
        "/leaderboard - Top\n"
        "/support - Support"
    )

# ================= OWNER COMMANDS =================
async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    await update.message.reply_text(f"ID: {OWNER_ID}\n{E_CHECK} Owner active")

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    await update.message.reply_text(f"{E_CROWN}  ADMIN PANEL\n\nChoose:", reply_markup=admin_kb())

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    s = db_stats()
    await update.message.reply_text(
        f"{E_CHART}  BOT STATISTICS\n\n"
        f"{E_USER}  Total Users: {s['users']}\n"
        f"{E_CHECK}  Active Users: {s['active_users']}\n"
        f"Today Joined: {s['today_users']}\n"
        f"Online 24h: {s['online_24h']}\n"
        f"{E_BOLT}  Active Subs: {s['active_subs']}\n\n"
        f"{E_BOX}  Total Orders: {s['total']}\n"
        f"{E_CHECK}  Verified: {s['verified']}\n"
        f"{E_HOUR}  Pending: {s['pending']}\n"
        f"Today Orders: {s['today_orders']}\n\n"
        f"{E_MONEY}  Revenue: Rs.{s['revenue']}"
    )

async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast message"); return
    msg = " ".join(ctx.args)
    users = db_all_users()
    sent, fail = 0, 0
    status = await update.message.reply_text(f"{E_JOIN}  Broadcasting to {len(users)} users...")
    for uid in users:
        try:
            await ctx.bot.send_message(uid, f"{E_JOIN}  Announcement\n\n{msg}")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await status.edit_text(f"{E_CHECK}  Sent: {sent}\n{E_CROSS}  Failed: {fail}")

async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    rows = db_pending_orders()
    if not rows:
        await update.message.reply_text(f"{E_CHECK}  Koi pending order nahi."); return
    text = f"{E_HOUR}  PENDING ORDERS\n\n"
    for r in rows[:10]:
        oid, uid, pkey, pname, amt, days, utr, status, cat, vat = r
        text += f"#{oid} | {uid}\n"
        text += f"{pname} | Rs.{amt}\n"
        text += f"UTR: {utr}\n"
        text += f"/verify {uid} {pkey}\n\n"
    await update.message.reply_text(text)

async def cmd_todayorders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    rows = db_today_orders()
    today = datetime.now().strftime("%Y-%m-%d")
    if not rows:
        await update.message.reply_text(f"Aaj ({today}) koi order nahi."); return
    text = f"{E_CHART}  TODAY'S ORDERS ({today})\n\n"
    total = 0
    for r in rows[:15]:
        oid, uid, pkey, pname, amt, days, utr, status, cat, vat = r
        emoji = E_CHECK if status == "verified" else (E_HOUR if status == "pending" else E_CROSS)
        text += f"{emoji}  #{oid} - {uid} (Rs.{amt})\n"
        if status == "verified":
            total += amt
    text += f"\n{E_MONEY}  Today Revenue: Rs.{total}"
    await update.message.reply_text(text)

async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not ctx.args:
        await update.message.reply_text("Usage: /search UTR"); return
    utr = ctx.args[0]
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT * FROM orders WHERE utr=?", (utr,))
    order = c.fetchone()
    if not order:
        con.close()
        await update.message.reply_text(f"{E_CROSS}  UTR {utr} nahi mila."); return
    oid, uid, pkey, pname, amt, days, utr, status, cat, vat = order
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = c.fetchone(); con.close()
    text = (
        f"SEARCH RESULT\n\n"
        f"Order: #{oid}\n"
        f"User ID: {uid}\n"
        f"Name: {user[2] if user else 'N/A'}\n"
        f"Plan: {pname}\n"
        f"Amount: Rs.{amt}\n"
        f"UTR: {utr}\n"
        f"Status: {status.upper()}\n\n"
        f"/verify {uid} {pkey}"
    )
    await update.message.reply_text(text)

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        uid = int(ctx.args[0]); days = int(ctx.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /adduser user_id days"); return
    until = (datetime.now() + timedelta(days=days)).isoformat()
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("UPDATE users SET active_until=? WHERE user_id=?", (until, uid))
    con.commit(); con.close()
    await update.message.reply_text(f"{E_CHECK}  User {uid} - {days} days AutoLike added.")
    try:
        await ctx.bot.send_message(uid,
            f"{E_FIRE}  AutoLike Added!\n\n"
            f"{E_HOUR}  Validity: {days} days\n"
            f"{E_HEART}  200 Likes Daily Given\n"
            f"{E_ROCKET}  Status: ACTIVE")
    except Exception:
        pass

async def cmd_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not ctx.args:
        await update.message.reply_text("Usage: /user user_id"); return
    try:
        uid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID"); return
    row = db_get_user(uid)
    if not row:
        await update.message.reply_text("User not found"); return
    uname, fname, bal, banned, ref_by, joined = row[1], row[2], row[3], row[4], row[5], row[6]
    refs = db_refer_count(uid)
    await update.message.reply_text(
        f"{E_USER}  USER INFO\n\n"
        f"{fname}\n"
        f"{uid}\n"
        f"@{uname or 'N/A'}\n"
        f"Rs.{fmt_bal(bal)}\n"
        f"Refs: {refs}\n"
        f"Banned: {'Yes' if banned else 'No'}\n"
        f"{joined[:10]}"
    )

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /ban user_id"); return
    db_ban(uid, 1)
    await update.message.reply_text(f"{E_CROSS}  User {uid} banned.")

async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unban user_id"); return
    db_ban(uid, 0)
    await update.message.reply_text(f"{E_CHECK}  User {uid} unbanned.")

async def cmd_addbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        uid = int(ctx.args[0]); amt = float(ctx.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addbalance user_id amount"); return
    db_add_balance(uid, amt)
    await update.message.reply_text(f"{E_CHECK}  Rs.{fmt_bal(amt)} added to {uid}")
    try:
        await ctx.bot.send_message(uid, f"{E_GIFT}  Rs.{fmt_bal(amt)} added to your balance!")
    except Exception:
        pass

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        oid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /reject order_id"); return
    order = db_get_order(oid)
    if not order:
        await update.message.reply_text("Order not found"); return
    db_update_order(oid, "rejected")
    uid = order[1]
    await update.message.reply_text(f"{E_CROSS}  Order #{oid} rejected.")
    try:
        await ctx.bot.send_message(uid, f"{E_CROSS}  Order #{oid} Rejected")
    except Exception:
        pass

async def cmd_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(ctx.args[0])
        key = ctx.args[1]
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /verify user_id plan_key")
        return
    plan = PLANS.get(key)
    if not plan:
        await update.message.reply_text(f"{E_CROSS}  Invalid plan key")
        return
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("SELECT id FROM orders WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (uid,))
    row = c.fetchone(); con.close()
    if row:
        db_update_order(row[0], "verified")
    until = (datetime.now() + timedelta(days=plan["days"])).isoformat()
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("UPDATE users SET active_until=? WHERE user_id=?", (until, uid))
    con.commit(); con.close()
    try:
        await ctx.bot.send_message(
            uid,
            f"{E_GIFT}  CONGRATULATIONS!\n\n"
            f"{E_CHECK}  AutoLike Successfully Added!\n\n"
            f"{E_BOX}  Plan: {plan['name']}\n"
            f"{E_HOUR}  Validity: {plan['days']} days\n"
            f"Until: {until[:10]}\n"
            f"{E_HEART}  200 Likes Daily Given\n"
            f"{E_ROCKET}  AutoLike: ACTIVE\n\n"
            f"Thank you!\n{OWNER_USERNAME}"
        )
        await update.message.reply_text(f"{E_CHECK}  Verified & delivered to {uid}")
    except Exception as e:
        await update.message.reply_text(f"{E_CROSS}  Failed: {e}")

# ================= UTR HANDLER =================
async def handle_utr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if db_is_banned(u.id): return
    text = update.message.text.strip()
    if not text.isdigit() or len(text) < 8 or len(text) > 20:
        await update.message.reply_text(f"{E_CROSS}  Invalid UTR\n\n8-20 digit number bhejo.")
        return
    if db_utr_used(text):
        await update.message.reply_text(f"{E_CROSS}  Ye UTR pehle use ho chuka hai!")
        return
    pending_key = ctx.user_data.get("pending_plan")
    if not pending_key:
        await update.message.reply_text(f"{E_CROSS}  Pehle plan select karo.\n/buy use karo.")
        return
    plan = PLANS[pending_key]
    oid = db_create_order(u.id, pending_key, plan, text)
    db_save_utr(text, u.id, oid)
    owner_msg = (
        f"{E_JOIN}  NEW ORDER\n\n"
        f"Order: #{oid}\n"
        f"User: {u.first_name}\n"
        f"ID: {u.id}\n"
        f"Plan: {plan['name']}\n"
        f"Amount: Rs.{plan['price']}\n"
        f"UTR: {text}\n\n"
        f"/verify {u.id} {pending_key}\n"
        f"/reject {oid}"
    )
    try:
        await ctx.bot.send_message(OWNER_ID, owner_msg)
    except Exception as e:
        logger.error(f"Owner notify failed: {e}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E_BOX}  My Orders", callback_data="myorders")],
        [InlineKeyboardButton(f"{E_BACK}  Home", callback_data="back_home")]
    ])
    await update.message.reply_text(
        f"{E_CHECK}  ORDER PLACED\n\n"
        f"Order ID: #{oid}\n"
        f"Plan: {plan['name']}\n"
        f"Amount: Rs.{plan['price']}\n"
        f"UTR: {text}\n\n"
        f"{E_HOUR}  Verification in progress\n"
        f"Time: 5-10 minutes",
        reply_markup=kb
    )
    ctx.user_data["pending_plan"] = None

# ================= CALLBACKS =================
async def cb_buylike(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not await is_joined(q.from_user.id, ctx):
        await force_join_msg(q, ctx); return
    text = (
        f"{E_GEM}  PRICE LIST\n\n"
        f"{E_GREEN}  {E_FIRE}  15 Days   -   Rs.70\n"
        f"{E_BLUE}  {E_BOLT}  30 Days   -   Rs.120\n"
        f"{E_PURPLE}  {E_GEM}  60 Days   -   Rs.250\n"
        f"{E_YELLOW}  {E_CROWN}  120 Days  -   Rs.450\n\n"
        f"{E_HEART}  200 Likes Daily Given\n\n"
        f"Apna plan choose karo"
    )
    await smart_edit(q, text, plans_kb())

async def cb_select_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not await is_joined(q.from_user.id, ctx):
        await force_join_msg(q, ctx); return
    key = q.data.split("_", 1)[1]
    plan = PLANS[key]
    ctx.user_data["pending_plan"] = key
    upi_link = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={plan['price']}&cu=INR"
    qr_url = ("https://api.qrserver.com/v1/create-qr-code/"
              f"?size=500x500&data={urllib.parse.quote(upi_link, safe='')}")
    caption = (
        f"{E_BOX}  ORDER SUMMARY\n\n"
        f"Plan: {plan['name']}\n"
        f"Price: Rs.{plan['price']}\n"
        f"Validity: {plan['days']} days\n"
        f"Likes: 200 Daily Given\n\n"
        f"{E_MONEY}  UPI: {UPI_ID}\n\n"
        f"QR scan karke pay karo.\n\n"
        f"Payment ke baad UTR / Transaction ID yaha type karke bhejo.\n"
        f"(12 digit number)"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="buylike")]])
    try:
        await q.message.reply_photo(photo=qr_url, caption=caption, reply_markup=kb)
        try:
            await q.message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"QR fail: {e}")
        await smart_edit(q, caption, kb)

async def cb_myorders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    rows = db_user_orders(uid, 10)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    if not rows:
        await smart_edit(q, f"{E_BOX}  Abhi tak koi order nahi.\n/buy se order karo.", kb)
        return
    text = f"{E_BOX}  MY ORDERS\n\n"
    for r in rows:
        oid, _, pkey, pname, amt, days, utr, status, cat, vat = r
        emoji = E_CHECK if status == "verified" else (E_HOUR if status == "pending" else E_CROSS)
        text += f"{emoji}  #{oid} - {pname} (Rs.{amt})\n"
    await smart_edit(q, text, kb)

async def cb_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    row = db_get_user(uid)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    if not row:
        await smart_edit(q, f"{E_CROSS}  User not found.", kb); return
    uname, fname, bal, banned, ref_by, joined = row[1], row[2], row[3], row[4], row[5], row[6]
    refs = db_refer_count(uid)
    active = row[8] if len(row) > 8 else None
    status_text = f"{E_CHECK} ACTIVE" if active and active > datetime.now().isoformat() else f"{E_CROSS} INACTIVE"
    text = (
        f"{E_USER}  MY PROFILE\n\n"
        f"Name: {fname}\n"
        f"ID: {uid}\n"
        f"Username: @{uname or 'N/A'}\n"
        f"{E_MONEY}  Balance: Rs.{fmt_bal(bal)}\n"
        f"{E_GIFT}  Refs: {refs}\n"
        f"Status: {status_text}\n"
        f"Joined: {joined[:10]}"
    )
    await smart_edit(q, text, kb)

async def cb_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    row = db_get_user(uid)
    bal = row[3] if row else 0
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    await smart_edit(q, f"{E_MONEY}  MY WALLET\n\nBalance: Rs.{fmt_bal(bal)}\n\nAdd money: {OWNER_USERNAME}", kb)

async def cb_refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    bot_info = await ctx.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    refs = db_refer_count(uid)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"{E_GIFT}  REFER & EARN\n\n"
        f"Tera Link:\n{ref_link}\n\n"
        f"{E_CHART}  Referrals: {refs}\n"
        f"{E_MONEY}  Earned: Rs.{fmt_bal(refs * REFER_BONUS)}\n\n"
        f"Rs.{fmt_bal(REFER_BONUS)} per refer"
    )
    await smart_edit(q, text, kb)

async def cb_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    con = sqlite3.connect(DB_FILE); c = con.cursor()
    c.execute("""SELECT first_name, referred_by, COUNT(*) as cnt FROM users 
                 WHERE referred_by != 0 GROUP BY referred_by ORDER BY cnt DESC LIMIT 10""")
    rows = c.fetchall()
    con.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    if not rows:
        await smart_edit(q, f"{E_TROPHY}  Leaderboard\n\nAbhi koi refer nahi hua.", kb)
        return
    text = f"{E_TROPHY}  REFERRAL LEADERBOARD\n\n"
    for i, (name, uid, cnt) in enumerate(rows):
        text += f"{i+1}. {name or 'User'} - {cnt} refs\n"
    await smart_edit(q, text, kb)

async def cb_bot_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    s = db_stats()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"{E_CHART}  BOT STATISTICS\n\n"
        f"{E_USER}  Total Users: {s['users']}\n"
        f"{E_CHECK}  Active Users: {s['active_users']}\n"
        f"Today Joined: {s['today_users']}\n"
        f"Online 24h: {s['online_24h']}\n"
        f"{E_BOLT}  Active Subs: {s['active_subs']}\n\n"
        f"{E_BOX}  Total Orders: {s['total']}\n"
        f"{E_CHECK}  Verified: {s['verified']}\n"
        f"{E_HOUR}  Pending: {s['pending']}\n"
        f"Today Orders: {s['today_orders']}\n\n"
        f"{E_MONEY}  Total Revenue: Rs.{s['revenue']}\n\n"
        f"{E_LINE}\n"
        f"{E_ROCKET}  Live Updates"
    )
    await smart_edit(q, text, kb)

async def cb_about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not await is_joined(q.from_user.id, ctx):
        await force_join_msg(q, ctx); return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"{E_INFO}  ABOUT US\n\n"
        f"{E_FIRE}  Cheapest FF AutoLike Store\n"
        f"{E_HEART}  200 Likes Daily Given\n"
        f"{E_BOLT}  Instant Auto-Verify\n"
        f"{E_SHIELD}  100% Trusted\n\n"
        f"{E_USER}  Owner: {OWNER_USERNAME}"
    )
    await smart_edit(q, text, kb)

async def cb_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"{E_HELP}  HELP\n\n"
        "/start - Home\n"
        "/buy - Buy\n"
        "/myorders - Orders\n"
        "/profile - Profile\n"
        "/wallet - Wallet\n"
        "/refer - Refer\n"
        "/leaderboard - Top\n"
        "/support - Support"
    )
    await smart_edit(q, text, kb)

async def cb_back_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = (
        f"{E_GAME}  FF AUTOLIKE STORE\n\n"
        f"{E_HEART}  200 Likes Daily Given\n"
        f"{E_BOLT}  Instant Auto-Verify\n\n"
        f"Niche se option choose karo"
    )
    await smart_edit(q, text, home_kb())

async def cb_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if await is_joined(q.from_user.id, ctx):
        text = f"{E_CHECK}  VERIFIED!\n\n{E_GAME}  Welcome!\n\n{E_HEART}  200 Likes Daily Given\n\nChoose:"
        await smart_edit(q, text, home_kb())
    else:
        await q.answer(f"{E_CROSS}  Abhi join nahi kiya!", show_alert=True)

async def cb_admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer(f"{E_CROSS}  Not owner", show_alert=True); return
    await q.answer()
    s = db_stats()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="admin_home")]])
    text = (
        f"{E_CHART}  BOT STATISTICS\n\n"
        f"{E_USER}  Total Users: {s['users']}\n"
        f"{E_CHECK}  Active: {s['active_users']}\n"
        f"Today: {s['today_users']}\n"
        f"Online 24h: {s['online_24h']}\n"
        f"{E_BOLT}  Active Subs: {s['active_subs']}\n\n"
        f"{E_BOX}  Orders: {s['total']}\n"
        f"{E_CHECK}  Verified: {s['verified']}\n"
        f"{E_HOUR}  Pending: {s['pending']}\n"
        f"{E_MONEY}  Revenue: Rs.{s['revenue']}"
    )
    await smart_edit(q, text, kb)

async def cb_admin_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer(f"{E_CROSS}  Not owner", show_alert=True); return
    await q.answer()
    rows = db_pending_orders()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="admin_home")]])
    if not rows:
        await smart_edit(q, f"{E_CHECK}  Koi pending order nahi.", kb); return
    text = f"{E_HOUR}  PENDING ORDERS\n\n"
    for r in rows[:8]:
        oid, uid, pkey, pname, amt, days, utr, status, cat, vat = r
        text += f"#{oid} | {uid}\n"
        text += f"{pname} | Rs.{amt}\n"
        text += f"UTR: {utr}\n"
        text += f"/verify {uid} {pkey}\n\n"
    await smart_edit(q, text, kb)

async def cb_admin_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer(f"{E_CROSS}  Not owner", show_alert=True); return
    await q.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="admin_home")]])
    await smart_edit(q, f"{E_JOIN}  BROADCAST\n\nType:\n/broadcast your message", kb)

async def cb_admin_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer(f"{E_CROSS}  Not owner", show_alert=True); return
    await q.answer()
    await smart_edit(q, f"{E_CROWN}  ADMIN PANEL\n\nChoose:", admin_kb())

# ================= MAIN =================
def main():
    db_init()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("myorders", cmd_myorders))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("wallet", cmd_wallet))
    app.add_handler(CommandHandler("refer", cmd_refer))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("help", cmd_help))

    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("todayorders", cmd_todayorders))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("user", cmd_user))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("addbalance", cmd_addbalance))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("verify", cmd_verify))

    app.add_handler(CallbackQueryHandler(cb_buylike, pattern="^buylike$"))
    app.add_handler(CallbackQueryHandler(cb_select_plan, pattern="^select_"))
    app.add_handler(CallbackQueryHandler(cb_myorders, pattern="^myorders$"))
    app.add_handler(CallbackQueryHandler(cb_profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(cb_wallet, pattern="^wallet$"))
    app.add_handler(CallbackQueryHandler(cb_refer, pattern="^refer$"))
    app.add_handler(CallbackQueryHandler(cb_leaderboard, pattern="^leaderboard$"))
    app.add_handler(CallbackQueryHandler(cb_bot_stats, pattern="^bot_stats$"))
    app.add_handler(CallbackQueryHandler(cb_about, pattern="^about$"))
    app.add_handler(CallbackQueryHandler(cb_help, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(cb_back_home, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(cb_check_join, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(cb_admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(cb_admin_pending, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(cb_admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(cb_admin_home, pattern="^admin_home$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_utr))

    app.post_init = setup_commands

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()