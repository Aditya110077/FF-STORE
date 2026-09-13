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
E_ID     = "\U0001F194"
E_GLOBE  = "\U0001F30D"
E_DEVIL  = "\U0001F608"
E_WARN   = "\u26A0\uFE0F"
E_MAIL   = "\U0001F4E9"
E_LINE   = "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"

# ================= CONFIG =================
BOT_TOKEN = "8801453801:AAFeC-jf5eo2ohgXFy147boD3XTNsPW3tSQ"
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
REFER_BONUS = 0.25
DB_FILE = "store.db"
# ==========================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLANS = {
    "p15":  {"name": "15 Days",  "price": 70,  "days": 15},
    "p30":  {"name": "30 Days",  "price": 120, "days": 30},
    "p60":  {"name": "60 Days",  "price": 250, "days": 60},
    "p120": {"name": "120 Days", "price": 450, "days": 120},
}

# ================= FAKE UTR =================
FAKE_PATTERNS = [
    "111111111111", "222222222222", "333333333333", "444444444444",
    "555555555555", "666666666666", "777777777777", "888888888888",
    "999999999999", "000000000000",
    "123456789012", "123456789123", "1234567890123",
    "987654321098", "987654321987",
]

def is_fake_utr(utr):
    if utr in FAKE_PATTERNS:
        return True, "Known fake pattern"
    if len(set(utr)) == 1:
        return True, "Sabhi digits same"
    if len(set(utr)) <= 2 and len(utr) >= 8:
        return True, "Sirf 1-2 digits repeat"
    seq_asc = "0123456789012345678901234"
    if utr in seq_asc or utr in seq_asc[::-1]:
        return True, "Sequence pattern"
    digits = [int(d) for d in utr]
    if all(d % 2 == 0 for d in digits):
        return True, "Sabhi digits even"
    if all(d % 2 == 1 for d in digits):
        return True, "Sabhi digits odd"
    if len(utr) >= 6:
        for size in range(2, len(utr) // 2 + 1):
            if len(utr) % size == 0:
                sub = utr[:size]
                if sub * (len(utr) // size) == utr:
                    return True, "Repeated pattern"
    if len(utr) >= 6:
        is_seq = True
        for i in range(1, len(utr)):
            if int(utr[i]) != (int(utr[i-1]) + 1) % 10:
                is_seq = False
                break
        if is_seq:
            return True, "Increasing sequence"
    return False, ""

# ================= DATABASE =================
def db_init():
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        balance REAL DEFAULT 0, banned INTEGER DEFAULT 0,
        referred_by INTEGER DEFAULT 0, joined_at TEXT,
        last_seen TEXT, active_until TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_key TEXT,
        plan_name TEXT, amount INTEGER, days INTEGER, utr TEXT, status TEXT,
        created_at TEXT, verified_at TEXT, ff_uid TEXT, region TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS utrs (
        utr TEXT PRIMARY KEY, user_id INTEGER, order_id INTEGER, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER, referred_id INTEGER,
        created_at TEXT, UNIQUE(referred_id))""")
    c.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in c.fetchall()]
    if "ff_uid" not in cols:
        c.execute("ALTER TABLE orders ADD COLUMN ff_uid TEXT")
    if "region" not in cols:
        c.execute("ALTER TABLE orders ADD COLUMN region TEXT")
    con.commit()
    con.close()
    print("[OK] Database ready")

def db_add_user(uid, uname, fname, ref_by=0):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, referred_by, joined_at, last_seen) VALUES (?,?,?,?,?,?)",
              (uid, uname, fname, ref_by, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute("UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
              (uname, fname, datetime.now().isoformat(), uid))
    con.commit()
    con.close()

def db_is_new(uid):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    con.close()
    return row is None

def db_is_banned(uid):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT banned FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    con.close()
    return row and row[0] == 1

def db_ban(uid, val):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("UPDATE users SET banned=? WHERE user_id=?", (val, uid))
    con.commit()
    con.close()

def db_add_balance(uid, amt):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, uid))
    con.commit()
    con.close()

def db_get_user(uid):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    con.close()
    return row

def db_create_order(uid, key, plan, utr, ff_uid, region):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("""INSERT INTO orders (user_id, plan_key, plan_name, amount, days, utr, status, created_at, ff_uid, region)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (uid, key, plan["name"], plan["price"], plan["days"], utr, "pending",
         datetime.now().isoformat(), ff_uid, region))
    oid = c.lastrowid
    con.commit()
    con.close()
    return oid

def db_update_order(oid, status):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("UPDATE orders SET status=?, verified_at=? WHERE id=?",
              (status, datetime.now().isoformat(), oid))
    con.commit()
    con.close()

def db_get_order(oid):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (oid,))
    row = c.fetchone()
    con.close()
    return row

def db_user_orders(uid, limit=10):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit))
    rows = c.fetchall()
    con.close()
    return rows

def db_pending_orders():
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id DESC")
    rows = c.fetchall()
    con.close()
    return rows

def db_stats():
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=0")
    active_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='verified'")
    verified = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM orders WHERE status='verified'")
    revenue = c.fetchone()[0] or 0
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
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT user_id FROM users WHERE banned=0")
    rows = [r[0] for r in c.fetchall()]
    con.close()
    return rows

def db_utr_used(utr):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM utrs WHERE utr=?", (utr,))
    row = c.fetchone()
    con.close()
    return row is not None

def db_save_utr(utr, uid, oid):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO utrs (utr, user_id, order_id, created_at) VALUES (?,?,?,?)",
              (utr, uid, oid, datetime.now().isoformat()))
    con.commit()
    con.close()

def db_refer_count(uid):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,))
    count = c.fetchone()[0]
    con.close()
    return count

def db_today_orders():
    today = datetime.now().strftime("%Y-%m-%d")
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM orders WHERE created_at LIKE ? ORDER BY id DESC", (today + "%",))
    rows = c.fetchall()
    con.close()
    return rows

def db_save_referral(referrer_id, referred_id):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    try:
        c.execute("INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?,?,?)",
                  (referrer_id, referred_id, datetime.now().isoformat()))
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()

def fmt_bal(v):
    if v is None:
        return "0"
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}".rstrip('0').rstrip('.')

def fmt_order(r):
    return (tuple(r) + ("",) * 12)[:12]

# ================= FORCE JOIN =================
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
        f"╔══════════════════════╗\n"
        f"   {E_WARN}  *JOIN REQUIRED*  {E_WARN}\n"
        f"╚══════════════════════╝\n\n"
        f"Pehle ye channels join karo:\n"
        f"{channels_list}\n\n"
        f"{E_CHECK}  Join ke baad *JOINED* dabao"
    )
    markup = InlineKeyboardMarkup(kb)
    if hasattr(u, "message") and u.message:
        await u.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await u.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")

# ================= EDIT HELPER =================
async def smart_edit(q, text, kb):
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try:
            await q.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            try:
                await q.message.delete()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"smart_edit failed: {e}")

# ================= DEVIL QR =================
def make_stylish_qr_url(upi_link):
    encoded = urllib.parse.quote(upi_link, safe='')
    return (
        f"https://api.qrserver.com/v1/create-qr-code/"
        f"?size=700x700&data={encoded}&color=000000&bgcolor=8B0000&qzone=3&format=png"
    )

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

def region_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("IN  I N D I A", callback_data="region_India")],
        [InlineKeyboardButton("BD  B A N G L A D E S H", callback_data="region_Bangladesh")],
        [InlineKeyboardButton("PK  P A K I S T A N", callback_data="region_Pakistan")],
        [InlineKeyboardButton("ID  I N D O N E S I A", callback_data="region_Indonesia")],
        [InlineKeyboardButton("ME  M I D D L E   E A S T", callback_data="region_Middle East")],
        [InlineKeyboardButton("OT  O T H E R", callback_data="region_Other")],
        [InlineKeyboardButton(f"{E_BACK}  B A C K", callback_data="buylike")]
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E_CHART}  Stats", callback_data="admin_stats"),
         InlineKeyboardButton(f"{E_HOUR}  Pending", callback_data="admin_pending")],
        [InlineKeyboardButton(f"{E_JOIN}  Broadcast Guide", callback_data="admin_broadcast")],
        [InlineKeyboardButton(f"{E_USER}  Users List", callback_data="admin_users")],
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
        BotCommand("dm",         "DM any user"),
        BotCommand("broadcast",  "Broadcast Message"),
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
            if ref_by == u.id:
                ref_by = 0
        except (ValueError, IndexError):
            pass
    if db_is_new(u.id):
        db_add_user(u.id, u.username or "", u.first_name or "", ref_by)
        if ref_by and not db_is_new(ref_by):
            ref_row = db_get_user(ref_by)
            if ref_row and ref_row[4] == 0:
                if db_save_referral(ref_by, u.id):
                    db_add_balance(ref_by, REFER_BONUS)
                    try:
                        await ctx.bot.send_message(ref_by,
                            f"{E_GIFT}  *New Referral!*\n\n"
                            f"{E_USER}  *{u.first_name}* ne tera link use kiya.\n"
                            f"{E_MONEY}  *Rs.{fmt_bal(REFER_BONUS)} added!*",
                            parse_mode="Markdown")
                    except Exception:
                        pass
    else:
        db_add_user(u.id, u.username or "", u.first_name or "")
    if db_is_banned(u.id):
        await update.message.reply_text(f"{E_CROSS}  Aapko ban kiya gaya hai.", parse_mode="Markdown")
        return
    if not await is_joined(u.id, ctx):
        await force_join_msg(update, ctx)
        return
    s = db_stats()
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_WAVE}  *Welcome {u.first_name}!*\n"
        f"╚══════════════════════╝\n\n"
        f"{E_GAME}  *FF AUTOLIKE STORE*\n\n"
        f"{E_HEART}  200 Likes Daily Given\n"
        f"{E_BOLT}  Instant Auto-Verify\n"
        f"{E_SHIELD}  100% Safe & Trusted\n"
        f"{E_GEM}  Premium Quality Service\n\n"
        f"{E_LINE}\n"
        f"{E_USER}  Total Users: *{s['users']}*\n"
        f"{E_CHECK}  Total Orders: *{s['verified']}*\n"
        f"{E_LINE}\n\n"
        f"👇  *Niche se option choose karo*",
        reply_markup=home_kb(),
        parse_mode="Markdown"
    )

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_joined(update.effective_user.id, ctx):
        await force_join_msg(update, ctx)
        return
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_GEM}  *PRICE LIST*  {E_GEM}\n"
        f"╚══════════════════════╝\n\n"
        f"{E_GREEN}  {E_FIRE}  15 Days   -   Rs.70\n"
        f"{E_BLUE}  {E_BOLT}  30 Days   -   Rs.120\n"
        f"{E_PURPLE}  {E_GEM}  60 Days   -   Rs.250\n"
        f"{E_YELLOW}  {E_CROWN}  120 Days  -   Rs.450\n\n"
        f"{E_HEART}  *200 Likes Daily Given*\n\n"
        f"👇  *Apna plan choose karo*",
        reply_markup=plans_kb(),
        parse_mode="Markdown"
    )

async def cmd_myorders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rows = db_user_orders(uid, 10)
    if not rows:
        await update.message.reply_text(f"{E_BOX}  Abhi tak koi order nahi hai.\n\n/buy se order karo.", parse_mode="Markdown")
        return
    text = f"╔══════════════════════╗\n   {E_BOX}  *MY ORDERS*  {E_BOX}\n╚══════════════════════╝\n\n"
    for r in rows:
        r = fmt_order(r)
        oid, _, pkey, pname, amt, days, utr, status, cat, vat, ff_uid, region = r
        emoji = E_CHECK if status == "verified" else (E_HOUR if status == "pending" else E_CROSS)
        text += f"{emoji}  *#{oid}* - {pname} (Rs.{amt})\n"
        if ff_uid:
            text += f"     {E_ID} UID: `{ff_uid}`\n"
        text += "\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = db_get_user(uid)
    if not row:
        await update.message.reply_text(f"{E_CROSS}  User not found.", parse_mode="Markdown")
        return
    uname, fname, bal, banned, ref_by, joined = row[1], row[2], row[3], row[4], row[5], row[6]
    refs = db_refer_count(uid)
    active = row[8] if len(row) > 8 else None
    status_text = f"{E_CHECK} ACTIVE" if active and active > datetime.now().isoformat() else f"{E_CROSS} INACTIVE"
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_USER}  *MY PROFILE*  {E_USER}\n"
        f"╚══════════════════════╝\n\n"
        f"📛  Name: *{fname}*\n"
        f"🆔  ID: `{uid}`\n"
        f"🔗  Username: @{uname or 'N/A'}\n"
        f"{E_MONEY}  Balance: Rs.{fmt_bal(bal)}\n"
        f"{E_GIFT}  Referrals: {refs}\n"
        f"Status: {status_text}\n"
        f"📅  Joined: {joined[:10]}",
        parse_mode="Markdown"
    )

async def cmd_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = db_get_user(uid)
    bal = row[3] if row else 0
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_MONEY}  *MY WALLET*  {E_MONEY}\n"
        f"╚══════════════════════╝\n\n"
        f"Balance: *Rs.{fmt_bal(bal)}*\n\n"
        f"Add money: {OWNER_USERNAME}",
        parse_mode="Markdown"
    )

async def cmd_refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_info = await ctx.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    refs = db_refer_count(uid)
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_GIFT}  *REFER & EARN*  {E_GIFT}\n"
        f"╚══════════════════════╝\n\n"
        f"Tera Link:\n`{ref_link}`\n\n"
        f"{E_CHART}  Referrals: *{refs}*\n"
        f"{E_MONEY}  Earned: *Rs.{fmt_bal(refs * REFER_BONUS)}*\n\n"
        f"Rs.{fmt_bal(REFER_BONUS)} per successful refer\n"
        f"{E_WARN}  Fake referral ban karne pe account ban hoga!",
        parse_mode="Markdown"
    )

async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("""SELECT u.first_name, r.referrer_id, COUNT(*) as cnt 
                 FROM referrals r LEFT JOIN users u ON u.user_id = r.referrer_id
                 GROUP BY r.referrer_id ORDER BY cnt DESC LIMIT 10""")
    rows = c.fetchall()
    con.close()
    if not rows:
        await update.message.reply_text(f"{E_TROPHY}  Leaderboard\n\nAbhi koi refer nahi hua.", parse_mode="Markdown")
        return
    text = f"╔══════════════════════╗\n   {E_TROPHY}  *LEADERBOARD*  {E_TROPHY}\n╚══════════════════════╝\n\n"
    for i, (name, uid, cnt) in enumerate(rows):
        text += f"{i+1}.  *{name or 'User'}*  -  {cnt} refs\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_PHONE}  *SUPPORT*  {E_PHONE}\n"
        f"╚══════════════════════╝\n\n"
        f"Contact: {OWNER_USERNAME}",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_HELP}  *HELP*  {E_HELP}\n"
        f"╚══════════════════════╝\n\n"
        "/start - Home\n"
        "/buy - Buy\n"
        "/myorders - Orders\n"
        "/profile - Profile\n"
        "/wallet - Wallet\n"
        "/refer - Refer\n"
        "/leaderboard - Top\n"
        "/support - Support",
        parse_mode="Markdown"
    )

# ================= OWNER COMMANDS =================
async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(f"ID: `{OWNER_ID}`\n{E_CHECK} Owner active", parse_mode="Markdown")

async def cmd_dm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            f"{E_MAIL}  *DM Command Usage*\n\n"
            f"`/dm user_id message`\n\n"
            f"Example:\n"
            f"`/dm 6863389453 Hello bhai`",
            parse_mode="Markdown"
        )
        return
    try:
        target_uid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text(f"{E_CROSS}  Invalid user ID", parse_mode="Markdown")
        return
    msg = " ".join(ctx.args[1:])
    try:
        await ctx.bot.send_message(
            target_uid,
            f"╔══════════════════════╗\n"
            f"   {E_MAIL}  *MESSAGE FROM OWNER*  {E_MAIL}\n"
            f"╚══════════════════════╝\n\n"
            f"{msg}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{E_USER}  *Owner:*  {OWNER_USERNAME}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"{E_CHECK}  *Message sent to* `{target_uid}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"{E_CROSS}  Failed: {e}", parse_mode="Markdown")

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_CROWN}  *ADMIN PANEL*  {E_CROWN}\n"
        f"╚══════════════════════╝\n\n"
        "👇  Choose:",
        reply_markup=admin_kb(),
        parse_mode="Markdown"
    )

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    s = db_stats()
    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"   {E_CHART}  *STATISTICS*  {E_CHART}\n"
        f"╚══════════════════════╝\n\n"
        f"{E_USER}  Total Users: *{s['users']}*\n"
        f"{E_CHECK}  Active Users: *{s['active_users']}*\n"
        f"Today Joined: *{s['today_users']}*\n"
        f"Online 24h: *{s['online_24h']}*\n"
        f"{E_BOLT}  Active Subs: *{s['active_subs']}*\n\n"
        f"{E_BOX}  Total Orders: *{s['total']}*\n"
        f"{E_CHECK}  Verified: *{s['verified']}*\n"
        f"{E_HOUR}  Pending: *{s['pending']}*\n"
        f"Today Orders: *{s['today_orders']}*\n\n"
        f"{E_MONEY}  Revenue: *Rs.{s['revenue']}*",
        parse_mode="Markdown"
    )

async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{E_JOIN}  *BROADCAST USAGE*\n\n"
            f"`/broadcast Your message here`",
            parse_mode="Markdown"
        )
        return
    msg = " ".join(ctx.args)
    users = db_all_users()
    sent, fail = 0, 0
    status = await update.message.reply_text(f"{E_JOIN}  Broadcasting to {len(users)} users...", parse_mode="Markdown")
    for uid in users:
        try:
            await ctx.bot.send_message(uid,
                f"╔══════════════════════╗\n"
                f"   {E_JOIN}  *ANNOUNCEMENT*  {E_JOIN}\n"
                f"╚══════════════════════╝\n\n{msg}",
                parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await status.edit_text(
        f"{E_CHECK}  *Broadcast Complete!*\n\n"
        f"Sent: *{sent}*\n"
        f"Failed: *{fail}*",
        parse_mode="Markdown"
    )

async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    rows = db_pending_orders()
    if not rows:
        await update.message.reply_text(f"{E_CHECK}  Koi pending order nahi.", parse_mode="Markdown")
        return
    text = f"╔══════════════════════╗\n   {E_HOUR}  *PENDING*  {E_HOUR}\n╚══════════════════════╝\n\n"
    for r in rows[:10]:
        r = fmt_order(r)
        oid, uid, pkey, pname, amt, days, utr, status, cat, vat, ff_uid, region = r
        text += f"#{oid}  |  {uid}\n"
        text += f"{E_ID}  UID:  {ff_uid}\n"
        text += f"{E_GLOBE}  Region:  {region}\n"
        text += f"{E_BOX}  {pname}  |  Rs.{amt}\n"
        text += f"UTR:  {utr}\n"
        text += f"/verify {uid} {pkey}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_todayorders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    rows = db_today_orders()
    today = datetime.now().strftime("%Y-%m-%d")
    if not rows:
        await update.message.reply_text(f"Aaj ({today}) koi order nahi.", parse_mode="Markdown")
        return
    text = f"{E_CHART}  *TODAY'S ORDERS* ({today})\n\n"
    total = 0
    for r in rows[:15]:
        r = fmt_order(r)
        oid, uid, pkey, pname, amt, days, utr, status, cat, vat, ff_uid, region = r
        emoji = E_CHECK if status == "verified" else (E_HOUR if status == "pending" else E_CROSS)
        text += f"{emoji}  #{oid} - {uid} (Rs.{amt})\n"
        if status == "verified":
            total += amt
    text += f"\n{E_MONEY}  *Today Revenue:* Rs.{total}"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /search UTR", parse_mode="Markdown")
        return
    utr = ctx.args[0]
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT * FROM orders WHERE utr=?", (utr,))
    order = c.fetchone()
    if not order:
        con.close()
        await update.message.reply_text(f"{E_CROSS}  UTR {utr} nahi mila.", parse_mode="Markdown")
        return
    order = fmt_order(order)
    oid, uid, pkey, pname, amt, days, utr, status, cat, vat, ff_uid, region = order
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = c.fetchone()
    con.close()
    text = (
        f"SEARCH RESULT\n\n"
        f"Order: #{oid}\n"
        f"User ID: {uid}\n"
        f"Name: {user[2] if user else 'N/A'}\n"
        f"FF UID: {ff_uid}\n"
        f"Region: {region}\n"
        f"Plan: {pname}\n"
        f"Amount: Rs.{amt}\n"
        f"UTR: {utr}\n"
        f"Status: {status.upper()}\n\n"
        f"/verify {uid} {pkey}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(ctx.args[0])
        days = int(ctx.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /adduser user_id days", parse_mode="Markdown")
        return
    until = (datetime.now() + timedelta(days=days)).isoformat()
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("UPDATE users SET active_until=? WHERE user_id=?", (until, uid))
    con.commit()
    con.close()
    await update.message.reply_text(f"{E_CHECK}  User {uid} - {days} days AutoLike added.", parse_mode="Markdown")
    try:
        await ctx.bot.send_message(uid,
            f"╔══════════════════════╗\n"
            f"   {E_FIRE}  *AUTOLIKE ADDED!*  {E_FIRE}\n"
            f"╚══════════════════════╝\n\n"
            f"{E_CHECK}  Aapka AutoLike activate ho gaya!\n\n"
            f"{E_HOUR}  Validity: *{days} days*\n"
            f"Until: *{until[:10]}*\n"
            f"{E_HEART}  200 Likes Daily Given\n"
            f"{E_ROCKET}  Status: *ACTIVE*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Kisi bhi problem ke liye Owner se contact karo:\n"
            f"👉  {OWNER_USERNAME}",
            parse_mode="Markdown")
    except Exception:
        pass

async def cmd_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /user user_id", parse_mode="Markdown")
        return
    try:
        uid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID", parse_mode="Markdown")
        return
    row = db_get_user(uid)
    if not row:
        await update.message.reply_text("User not found", parse_mode="Markdown")
        return
    uname, fname, bal, banned, ref_by, joined = row[1], row[2], row[3], row[4], row[5], row[6]
    refs = db_refer_count(uid)
    await update.message.reply_text(
        f"USER INFO\n\n"
        f"Name: {fname}\n"
        f"ID: {uid}\n"
        f"Username: @{uname or 'N/A'}\n"
        f"Balance: Rs.{fmt_bal(bal)}\n"
        f"Refs: {refs}\n"
        f"Banned: {'Yes' if banned else 'No'}\n"
        f"Joined: {joined[:10]}",
        parse_mode="Markdown"
    )

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /ban user_id", parse_mode="Markdown")
        return
    db_ban(uid, 1)
    await update.message.reply_text(f"{E_CROSS}  User {uid} banned.", parse_mode="Markdown")

async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unban user_id", parse_mode="Markdown")
        return
    db_ban(uid, 0)
    await update.message.reply_text(f"{E_CHECK}  User {uid} unbanned.", parse_mode="Markdown")

async def cmd_addbalance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(ctx.args[0])
        amt = float(ctx.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addbalance user_id amount", parse_mode="Markdown")
        return
    db_add_balance(uid, amt)
    await update.message.reply_text(f"{E_CHECK}  Rs.{fmt_bal(amt)} added to {uid}", parse_mode="Markdown")
    try:
        await ctx.bot.send_message(uid, f"{E_GIFT}  Rs.{fmt_bal(amt)} added to your balance!", parse_mode="Markdown")
    except Exception:
        pass

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        oid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /reject order_id", parse_mode="Markdown")
        return
    order = db_get_order(oid)
    if not order:
        await update.message.reply_text(f"{E_CROSS}  Order not found", parse_mode="Markdown")
        return
    db_update_order(oid, "rejected")
    uid = order[1]
    order = fmt_order(order)
    oid_, _, pkey, pname, amt, days, utr, status, cat, vat, ff_uid, region = order
    await update.message.reply_text(
        f"{E_CROSS}  Order #{oid} Rejected\n\n"
        f"User: {uid}\n"
        f"UID: {ff_uid}\n"
        f"Region: {region}\n"
        f"Plan: {pname}\n"
        f"Amount: Rs.{amt}",
        parse_mode="Markdown"
    )
    try:
        await ctx.bot.send_message(
            uid,
            f"╔══════════════════════╗\n"
            f"   {E_CROSS}  *ORDER REJECTED*  {E_CROSS}\n"
            f"╚══════════════════════╝\n\n"
            f"Order ID: #{oid}\n"
            f"FF UID: {ff_uid}\n"
            f"Region: {region}\n"
            f"Plan: {pname}\n"
            f"Amount: Rs.{amt}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{E_WARN}  *Reason:*\n"
            f"Payment verify nahi hui ya galat UTR tha.\n\n"
            f"{E_MAIL}  *Agar aapne paisa bheja hai to Owner se contact karo:*\n\n"
            f"👉  {OWNER_USERNAME}\n\n"
            f"Payment screenshot ya UTR bhejo owner ko.\n"
            f"Owner manually verify karega.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Thank you",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Reject notify failed: {e}")

async def cmd_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(ctx.args[0])
        key = ctx.args[1]
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /verify user_id plan_key", parse_mode="Markdown")
        return
    plan = PLANS.get(key)
    if not plan:
        await update.message.reply_text(f"{E_CROSS}  Invalid plan key", parse_mode="Markdown")
        return
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("SELECT id, utr, ff_uid, region FROM orders WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (uid,))
    order_row = c.fetchone()
    con.close()
    oid = order_row[0] if order_row else None
    utr = order_row[1] if order_row else "N/A"
    ff_uid = order_row[2] if order_row and order_row[2] else "N/A"
    region = order_row[3] if order_row and order_row[3] else "N/A"
    if oid:
        db_update_order(oid, "verified")
    until = (datetime.now() + timedelta(days=plan["days"])).isoformat()
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("UPDATE users SET active_until=? WHERE user_id=?", (until, uid))
    con.commit()
    con.close()
    success_msg = (
        f"╔══════════════════════╗\n"
        f"   CONGRATULATIONS\n"
        f"╚══════════════════════╝\n\n"
        f"AUTOLIKE SUCCESSFULLY ADDED!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"FF UID: {ff_uid}\n"
        f"Region: {region}\n"
        f"Plan: {plan['name']}\n"
        f"Days: {plan['days']} days\n"
        f"Valid Until: {until[:10]}\n"
        f"Amount Paid: Rs.{plan['price']}\n"
        f"UTR: {utr}\n"
        f"Order ID: #{oid if oid else 'N/A'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"200 Likes Daily Given\n"
        f"Status: ACTIVE\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Thank you for purchasing!\n\n"
        f"Kisi bhi problem ke liye Owner se contact karo:\n"
        f"👉  {OWNER_USERNAME}"
    )
    try:
        await ctx.bot.send_message(uid, success_msg, parse_mode="Markdown")
        await update.message.reply_text(
            f"{E_CHECK}  Verified & delivered!\n\n"
            f"User: {uid}\n"
            f"UID: {ff_uid}\n"
            f"Region: {region}\n"
            f"Plan: {plan['name']}\n"
            f"Days: {plan['days']}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"{E_CROSS}  Failed: {e}", parse_mode="Markdown")

# ================= MAIN TEXT HANDLER =================
async def handle_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if db_is_banned(u.id):
        return
    text = update.message.text.strip()
    if ctx.user_data.get("awaiting_uid"):
        if not text.isdigit() or len(text) < 6 or len(text) > 15:
            await update.message.reply_text(
                f"{E_CROSS}  INVALID UID\n\n"
                f"Sirf 6-15 digit numbers bhejo.\n"
                f"Example: 123456789",
                parse_mode="Markdown"
            )
            return
        ctx.user_data["ff_uid"] = text
        ctx.user_data["awaiting_uid"] = False
        pending_key = ctx.user_data.get("pending_plan")
        plan = PLANS.get(pending_key, {})
        await update.message.reply_text(
            f"{E_CHECK}  UID SAVED\n\n"
            f"FF UID: {text}\n"
            f"Plan: {plan.get('name', '')}\n\n"
            f"STEP 2 - SELECT REGION\n\n"
            f"Apna region choose karo:",
            reply_markup=region_kb(),
            parse_mode="Markdown"
        )
        return
    if ctx.user_data.get("awaiting_utr"):
        if not text.isdigit() or len(text) < 12 or len(text) > 22:
            await update.message.reply_text(
                f"{E_CROSS}  INVALID UTR\n\n12-22 digit transaction ID bhejo.",
                parse_mode="Markdown"
            )
            return
        if db_utr_used(text):
            await update.message.reply_text(
                f"{E_CROSS}  Ye UTR pehle use ho chuka hai!\n\nNaya UTR bhejo.",
                parse_mode="Markdown"
            )
            return
        is_fake, reason = is_fake_utr(text)
        if is_fake:
            await update.message.reply_text(
                f"{E_CROSS}  INVALID UTR DETECTED!\n\nReason: {reason}\n\nKripya asli transaction ID bhejo.",
                parse_mode="Markdown"
            )
            try:
                await ctx.bot.send_message(
                    OWNER_ID,
                    f"{E_CROSS}  Fake UTR Attempt\n\n"
                    f"User: {u.first_name}\n"
                    f"ID: {u.id}\n"
                    f"UTR: {text}\n"
                    f"Reason: {reason}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return
        con = sqlite3.connect(DB_FILE)
        c = con.cursor()
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND created_at > ?", (u.id, yesterday))
        recent = c.fetchone()[0]
        con.close()
        if recent >= 3:
            await update.message.reply_text(
                f"{E_CROSS}  RATE LIMIT EXCEEDED\n\nAapne 24 ghante me 3 orders kar liye hain.",
                parse_mode="Markdown"
            )
            return
        pending_key = ctx.user_data.get("pending_plan")
        ff_uid = ctx.user_data.get("ff_uid")
        region = ctx.user_data.get("region")
        if not pending_key or not ff_uid or not region:
            await update.message.reply_text(f"{E_CROSS}  Data missing. /buy se dobara start karo.", parse_mode="Markdown")
            return
        plan = PLANS[pending_key]
        oid = db_create_order(u.id, pending_key, plan, text, ff_uid, region)
        db_save_utr(text, u.id, oid)
        owner_msg = (
            f"NEW ORDER\n\n"
            f"Order: #{oid}\n"
            f"User: {u.first_name}\n"
            f"ID: {u.id}\n"
            f"FF UID: {ff_uid}\n"
            f"Region: {region}\n"
            f"Plan: {plan['name']}\n"
            f"Amount: Rs.{plan['price']}\n"
            f"UTR: {text}\n\n"
            f"/verify {u.id} {pending_key}\n"
            f"/reject {oid}"
        )
        try:
            await ctx.bot.send_message(OWNER_ID, owner_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Owner notify failed: {e}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{E_BOX}  My Orders", callback_data="myorders")],
            [InlineKeyboardButton(f"{E_BACK}  Home", callback_data="back_home")]
        ])
        await update.message.reply_text(
            f"ORDER PLACED\n\n"
            f"Order ID: #{oid}\n"
            f"FF UID: {ff_uid}\n"
            f"Region: {region}\n"
            f"Plan: {plan['name']}\n"
            f"Amount: Rs.{plan['price']}\n"
            f"UTR: {text}\n\n"
            f"Verification in progress\n"
            f"Time: 5-10 minutes",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        ctx.user_data["pending_plan"] = None
        ctx.user_data["ff_uid"] = None
        ctx.user_data["region"] = None
        ctx.user_data["awaiting_utr"] = False
        return

# ================= CALLBACKS =================
async def cb_buylike(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await is_joined(q.from_user.id, ctx):
        await force_join_msg(q, ctx)
        return
    ctx.user_data["awaiting_uid"] = False
    ctx.user_data["awaiting_utr"] = False
    text = (
        f"PRICE LIST\n\n"
        f"15 Days   -   Rs.70\n"
        f"30 Days   -   Rs.120\n"
        f"60 Days   -   Rs.250\n"
        f"120 Days  -   Rs.450\n\n"
        f"200 Likes Daily Given\n\n"
        f"Apna plan choose karo"
    )
    await smart_edit(q, text, plans_kb())

async def cb_select_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await is_joined(q.from_user.id, ctx):
        await force_join_msg(q, ctx)
        return
    key = q.data.split("_", 1)[1]
    plan = PLANS[key]
    ctx.user_data["pending_plan"] = key
    ctx.user_data["awaiting_uid"] = True
    ctx.user_data["ff_uid"] = None
    ctx.user_data["region"] = None
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="buylike")]])
    text = (
        f"STEP 1 - ENTER UID\n\n"
        f"Plan: {plan['name']}\n"
        f"Price: Rs.{plan['price']}\n"
        f"Validity: {plan['days']} days\n\n"
        f"Kripya apna Free Fire UID bhejo:\n\n"
        f"Sirf numbers bhejo\n"
        f"Example: 123456789\n\n"
        f"UID kaha milega?\n"
        f"FF game - Profile - UID copy karo"
    )
    await smart_edit(q, text, kb)

async def cb_region(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    region = q.data.split("_", 1)[1]
    ctx.user_data["region"] = region
    ctx.user_data["awaiting_utr"] = False
    pending_key = ctx.user_data.get("pending_plan")
    if not pending_key:
        await q.edit_message_text("Session expired. /buy se dobara start karo.")
        return
    plan = PLANS[pending_key]
    ff_uid = ctx.user_data.get("ff_uid", "")
    uid = q.from_user.id
    row = db_get_user(uid)
    balance = row[3] if row else 0
    caption = (
        f"ORDER SUMMARY\n\n"
        f"FF UID: {ff_uid}\n"
        f"Region: {region}\n"
        f"Plan: {plan['name']}\n"
        f"Price: Rs.{plan['price']}\n"
        f"Validity: {plan['days']} days\n\n"
        f"Wallet Balance: Rs.{fmt_bal(balance)}\n\n"
        f"Payment method choose karo:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"WALLET SE PAY (Rs.{fmt_bal(balance)})", callback_data=f"paywallet_{pending_key}")],
        [InlineKeyboardButton(f"UPI SE PAY (QR)", callback_data=f"payupi_{pending_key}")],
        [InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]
    ])
    await smart_edit(q, caption, kb)

async def cb_pay_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    pending_key = q.data.split("_", 1)[1]
    plan = PLANS.get(pending_key)
    if not plan:
        await q.edit_message_text("Session expired. /buy se dobara start karo.")
        return
    ff_uid = ctx.user_data.get("ff_uid", "")
    region = ctx.user_data.get("region", "")
    row = db_get_user(uid)
    balance = row[3] if row else 0
    if balance < plan["price"]:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"UPI SE PAY (QR)", callback_data=f"payupi_{pending_key}")],
            [InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]
        ])
        await smart_edit(q,
            f"INSUFFICIENT BALANCE\n\n"
            f"Tera Balance: Rs.{fmt_bal(balance)}\n"
            f"Plan Price: Rs.{plan['price']}\n"
            f"Short: Rs.{fmt_bal(plan['price'] - balance)}\n\n"
            f"Wallet me paise add karo ya UPI se pay karo.",
            kb)
        return
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (plan["price"], uid))
    con.commit()
    con.close()
    oid = db_create_order(uid, pending_key, plan, "WALLET_PAYMENT", ff_uid, region)
    db_update_order(oid, "verified")
    until = (datetime.now() + timedelta(days=plan["days"])).isoformat()
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("UPDATE users SET active_until=? WHERE user_id=?", (until, uid))
    con.commit()
    con.close()
    row = db_get_user(uid)
    new_balance = row[3] if row else 0
    try:
        await ctx.bot.send_message(
            OWNER_ID,
            f"WALLET ORDER\n\n"
            f"Order: #{oid}\n"
            f"User: {uid}\n"
            f"FF UID: {ff_uid}\n"
            f"Region: {region}\n"
            f"Plan: {plan['name']}\n"
            f"Amount: Rs.{plan['price']}\n"
            f"Paid via: WALLET\n"
            f"New Balance: Rs.{fmt_bal(new_balance)}\n\n"
            f"Auto-activated",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Owner notify failed: {e}")
    success_msg = (
        f"CONGRATULATIONS\n\n"
        f"AUTOLIKE SUCCESSFULLY ADDED!\n\n"
        f"FF UID: {ff_uid}\n"
        f"Region: {region}\n"
        f"Plan: {plan['name']}\n"
        f"Days: {plan['days']} days\n"
        f"Valid Until: {until[:10]}\n"
        f"Paid: Rs.{plan['price']} (Wallet)\n"
        f"New Balance: Rs.{fmt_bal(new_balance)}\n"
        f"Order ID: #{oid}\n\n"
        f"200 Likes Daily Given\n"
        f"Status: ACTIVE\n\n"
        f"Thank you!\n\n"
        f"Kisi bhi problem ke liye Owner se contact karo:\n"
        f"👉  {OWNER_USERNAME}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E_BOX}  My Orders", callback_data="myorders")],
        [InlineKeyboardButton(f"{E_BACK}  Home", callback_data="back_home")]
    ])
    await smart_edit(q, success_msg, kb)
    ctx.user_data["pending_plan"] = None
    ctx.user_data["ff_uid"] = None
    ctx.user_data["region"] = None

async def cb_pay_upi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pending_key = q.data.split("_", 1)[1]
    plan = PLANS.get(pending_key)
    if not plan:
        await q.edit_message_text("Session expired. /buy se dobara start karo.")
        return
    ctx.user_data["awaiting_utr"] = True
    ff_uid = ctx.user_data.get("ff_uid", "")
    region = ctx.user_data.get("region", "")
    upi_link = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={plan['price']}&cu=INR"
    qr_url = make_stylish_qr_url(upi_link)
    caption = (
        f"UPI PAYMENT\n\n"
        f"FF UID: {ff_uid}\n"
        f"Region: {region}\n"
        f"Plan: {plan['name']}\n"
        f"Price: Rs.{plan['price']}\n\n"
        f"UPI: {UPI_ID}\n\n"
        f"QR scan karke Rs.{plan['price']} pay karo.\n\n"
        f"Payment ke baad 12-digit UTR yaha type karke bhejo."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    try:
        await q.message.reply_photo(photo=qr_url, caption=caption, reply_markup=kb, parse_mode="Markdown")
        try:
            await q.message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"QR fail: {e}")
        await smart_edit(q, caption, kb)

async def cb_myorders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    rows = db_user_orders(uid, 10)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    if not rows:
        await smart_edit(q, f"{E_BOX}  Abhi tak koi order nahi.\n/buy se order karo.", kb)
        return
    text = f"MY ORDERS\n\n"
    for r in rows:
        r = fmt_order(r)
        oid, _, pkey, pname, amt, days, utr, status, cat, vat, ff_uid, region = r
        emoji = E_CHECK if status == "verified" else (E_HOUR if status == "pending" else E_CROSS)
        text += f"{emoji}  #{oid} - {pname} (Rs.{amt})\n"
        if ff_uid:
            text += f"     UID: {ff_uid}\n"
        text += "\n"
    await smart_edit(q, text, kb)

async def cb_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    row = db_get_user(uid)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    if not row:
        await smart_edit(q, f"{E_CROSS}  User not found.", kb)
        return
    uname, fname, bal, banned, ref_by, joined = row[1], row[2], row[3], row[4], row[5], row[6]
    refs = db_refer_count(uid)
    active = row[8] if len(row) > 8 else None
    status_text = "ACTIVE" if active and active > datetime.now().isoformat() else "INACTIVE"
    text = (
        f"MY PROFILE\n\n"
        f"Name: {fname}\n"
        f"ID: {uid}\n"
        f"Username: @{uname or 'N/A'}\n"
        f"Balance: Rs.{fmt_bal(bal)}\n"
        f"Refs: {refs}\n"
        f"Status: {status_text}\n"
        f"Joined: {joined[:10]}"
    )
    await smart_edit(q, text, kb)

async def cb_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    row = db_get_user(uid)
    bal = row[3] if row else 0
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    await smart_edit(q, f"MY WALLET\n\nBalance: Rs.{fmt_bal(bal)}\n\nAdd money: {OWNER_USERNAME}", kb)

async def cb_refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    bot_info = await ctx.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    refs = db_refer_count(uid)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"REFER & EARN\n\n"
        f"Tera Link:\n{ref_link}\n\n"
        f"Referrals: {refs}\n"
        f"Earned: Rs.{fmt_bal(refs * REFER_BONUS)}\n\n"
        f"Rs.{fmt_bal(REFER_BONUS)} per refer"
    )
    await smart_edit(q, text, kb)

async def cb_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    con = sqlite3.connect(DB_FILE)
    c = con.cursor()
    c.execute("""SELECT u.first_name, r.referrer_id, COUNT(*) as cnt 
                 FROM referrals r LEFT JOIN users u ON u.user_id = r.referrer_id
                 GROUP BY r.referrer_id ORDER BY cnt DESC LIMIT 10""")
    rows = c.fetchall()
    con.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    if not rows:
        await smart_edit(q, f"Leaderboard\n\nAbhi koi refer nahi hua.", kb)
        return
    text = f"LEADERBOARD\n\n"
    for i, (name, uid, cnt) in enumerate(rows):
        text += f"{i+1}.  {name or 'User'}  -  {cnt} refs\n"
    await smart_edit(q, text, kb)

async def cb_bot_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    s = db_stats()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"STATISTICS\n\n"
        f"Total Users: {s['users']}\n"
        f"Active Users: {s['active_users']}\n"
        f"Today Joined: {s['today_users']}\n"
        f"Online 24h: {s['online_24h']}\n"
        f"Active Subs: {s['active_subs']}\n\n"
        f"Total Orders: {s['total']}\n"
        f"Verified: {s['verified']}\n"
        f"Pending: {s['pending']}\n\n"
        f"Total Revenue: Rs.{s['revenue']}"
    )
    await smart_edit(q, text, kb)

async def cb_about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await is_joined(q.from_user.id, ctx):
        await force_join_msg(q, ctx)
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"ABOUT US\n\n"
        f"Cheapest FF AutoLike Store\n"
        f"200 Likes Daily Given\n"
        f"Instant Auto-Verify\n"
        f"100% Trusted\n\n"
        f"Owner: {OWNER_USERNAME}"
    )
    await smart_edit(q, text, kb)

async def cb_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="back_home")]])
    text = (
        f"HELP\n\n"
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
    q = update.callback_query
    await q.answer()
    ctx.user_data["awaiting_uid"] = False
    ctx.user_data["awaiting_utr"] = False
    text = (
        f"FF AUTOLIKE STORE\n\n"
        f"200 Likes Daily Given\n"
        f"Instant Auto-Verify\n\n"
        f"Niche se option choose karo"
    )
    await smart_edit(q, text, home_kb())

async def cb_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await is_joined(q.from_user.id, ctx):
        text = "VERIFIED\n\nWelcome!\n\n200 Likes Daily Given\n\nChoose:"
        await smart_edit(q, text, home_kb())
    else:
        await q.answer("Abhi join nahi kiya!", show_alert=True)

async def cb_admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer("Not owner", show_alert=True)
        return
    await q.answer()
    s = db_stats()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="admin_home")]])
    text = (
        f"STATISTICS\n\n"
        f"Users: {s['users']}\n"
        f"Active: {s['active_users']}\n"
        f"Today: {s['today_users']}\n"
        f"Online 24h: {s['online_24h']}\n"
        f"Active Subs: {s['active_subs']}\n\n"
        f"Orders: {s['total']}\n"
        f"Verified: {s['verified']}\n"
        f"Pending: {s['pending']}\n\n"
        f"Revenue: Rs.{s['revenue']}"
    )
    await smart_edit(q, text, kb)

async def cb_admin_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer("Not owner", show_alert=True)
        return
    await q.answer()
    rows = db_pending_orders()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="admin_home")]])
    if not rows:
        await smart_edit(q, f"{E_CHECK}  Koi pending order nahi.", kb)
        return
    text = f"PENDING ORDERS\n\n"
    for r in rows[:8]:
        r = fmt_order(r)
        oid, uid, pkey, pname, amt, days, utr, status, cat, vat, ff_uid, region = r
        text += f"#{oid}  |  {uid}\n"
        text += f"UID:  {ff_uid}\n"
        text += f"Region:  {region}\n"
        text += f"{pname}  |  Rs.{amt}\n"
        text += f"/verify {uid} {pkey}\n\n"
    await smart_edit(q, text, kb)

async def cb_admin_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer("Not owner", show_alert=True)
        return
    await q.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="admin_home")]])
    await smart_edit(q,
        f"BROADCAST\n\n"
        f"Type karo:\n/broadcast Your message here\n\n"
        f"Example:\n/broadcast New offer aa gaya!",
        kb)

async def cb_admin_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer("Not owner", show_alert=True)
        return
    await q.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{E_BACK}  Back", callback_data="admin_home")]])
    await smart_edit(q,
        f"USER MANAGEMENT\n\n"
        f"Commands:\n\n"
        f"/user user_id - User info\n"
        f"/dm user_id msg - Send DM\n"
        f"/ban user_id - Ban user\n"
        f"/unban user_id - Unban user\n"
        f"/addbalance user_id amt - Add balance\n"
        f"/adduser user_id days - AutoLike direct",
        kb)

async def cb_admin_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer("Not owner", show_alert=True)
        return
    await q.answer()
    await smart_edit(q, f"ADMIN PANEL\n\nChoose:", admin_kb())

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
    app.add_handler(CommandHandler("dm", cmd_dm))
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
    app.add_handler(CallbackQueryHandler(cb_region, pattern="^region_"))
    app.add_handler(CallbackQueryHandler(cb_pay_wallet, pattern="^paywallet_"))
    app.add_handler(CallbackQueryHandler(cb_pay_upi, pattern="^payupi_"))
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
    app.add_handler(CallbackQueryHandler(cb_admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(cb_admin_home, pattern="^admin_home$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    app.post_init = setup_commands

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
