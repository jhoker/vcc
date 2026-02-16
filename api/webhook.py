import os
import requests
from fastapi import FastAPI, Request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# ====== CONFIG ======
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

GEN_API_URL = "https://gen.xxnx-9ba.workers.dev/api/generate"  # API generator BIN

app = FastAPI()
bot = Bot(token=TOKEN)

# ====== STORAGE SEDERHANA (DISARANKAN GANTI DB UNTUK PRODUKSI) ======
users_balance = {}   # {user_id: saldo}
pending_topup = {}   # {user_id: amount}
gemini_stock = []    # list stok VCC Gemini: {"card","exp","cvv"}


# ====== HELPER SALDO ======
def get_balance(user_id):
    return users_balance.get(user_id, 0)

def add_balance(user_id, amount):
    users_balance[user_id] = get_balance(user_id) + amount

def deduct_balance(user_id, amount):
    current = get_balance(user_id)
    if current >= amount:
        users_balance[user_id] = current - amount
        return True
    return False


# ====== HELPER KEYBOARD ======
def main_menu_keyboard(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("💳 Produk VCC", callback_data='menu_products')],
        [InlineKeyboardButton("💰 Top Up Saldo", callback_data='menu_topup')],
        [InlineKeyboardButton("📊 Cek Saldo", callback_data='menu_balance')],
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data='menu_admin')])
    return InlineKeyboardMarkup(keyboard)

def products_keyboard():
    keyboard = [
        [InlineKeyboardButton("🤖 VCC ChatGPT - Rp2.000", callback_data='buy_chatgpt')],
        [InlineKeyboardButton("💎 VCC Gemini - Rp5.000", callback_data='buy_gemini')],
        [InlineKeyboardButton("« Kembali", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Lihat Request Top Up", callback_data='admin_view_topup')],
        [InlineKeyboardButton("📦 Stok Gemini", callback_data='admin_gemini_stock')],
        [InlineKeyboardButton("« Kembali", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(admin_keyboard_buttons())


def admin_keyboard_buttons():
    return [
        [InlineKeyboardButton("✅ Lihat Request Top Up", callback_data='admin_view_topup')],
        [InlineKeyboardButton("📦 Stok Gemini", callback_data='admin_gemini_stock')],
        [InlineKeyboardButton("« Kembali", callback_data='menu_main')]
    ]

# ====== GENERATE VCC CHATGPT VIA API (BIN 625814) ======
def generate_chatgpt_vcc():
    """
    Panggil API generator dengan BIN 625814, amount: 1.
    Response:
    {
      "success": true,
      "bin": "625814",
      "count": 1,
      "cards": ["6258142602081024|11|2027|853"]
    }
    """
    try:
        payload = {"bin": "625814", "amount": 1}
        headers = {"Content-Type": "application/json"}
        r = requests.post(GEN_API_URL, json=payload, headers=headers, timeout=15)
        data = r.json()

        if not data.get("success") or not data.get("cards"):
            return None

        card_raw = data["cards"][0]
        parts = card_raw.split("|")
        card, mm, yyyy, cvv = parts[0], parts[1], parts[2], parts[3]

        return {
            "card": card,
            "exp": f"{mm}/{yyyy}",
            "cvv": cvv
        }
    except Exception:
        return None


# ====== HANDLER COMMAND & CALLBACK ======
def start(update, context):
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    text = (
        "🏪 *VCC Store Bot*\n\n"
        f"💰 Saldo Anda: Rp{balance:,}\n\n"
        "Silakan pilih menu di bawah:"
    )
    reply_markup = main_menu_keyboard(is_admin=(user_id == ADMIN_ID))
    update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


def button_callback(update, context):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    data = query.data

    # === MAIN MENU ===
    if data == "menu_main":
        balance = get_balance(user_id)
        text = (
            "🏪 *VCC Store Bot*\n\n"
            f"💰 Saldo Anda: Rp{balance:,}\n\n"
            "Silakan pilih menu di bawah:"
        )
        query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_admin=(user_id == ADMIN_ID))
        )

    elif data == "menu_products":
        text = (
            "💳 *Pilih Produk VCC:*\n\n"
            "🤖 VCC ChatGPT: Rp2.000 (auto-generate)\n"
            "💎 VCC Gemini: Rp5.000 (stok manual admin)"
        )
        query.edit_message_text(text, parse_mode="Markdown", reply_markup=products_keyboard())

    elif data == "menu_topup":
        text = (
            "💰 *Cara Top Up Saldo:*\n\n"
            "1. Transfer ke rekening:\n"
            "   📱 Dana: 08811626713\n"
            "   📱 Gopay: 08811626713\n\n"
            "2. Screenshot bukti transfer\n"
            "3. Kirim ke bot ini dengan caption:\n"
            "   `topup [nominal]`\n\n"
            "Contoh: `topup 10000`\n\n"
            "Admin akan verifikasi dalam 1-10 menit."
        )
        query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Kembali", callback_data='menu_main')]])
        )

    elif data == "menu_balance":
        balance = get_balance(user_id)
        text = (
            "📊 *Saldo Anda:*\n\n"
            f"💰 Rp{balance:,}\n\n"
            "Gunakan saldo untuk membeli produk VCC."
        )
        query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Kembali", callback_data='menu_main')]])
        )

    # === ADMIN PANEL ===
    elif data == "menu_admin" and user_id == ADMIN_ID:
        text = "👨‍💼 *Admin Panel*\n\nPilih menu:"
        query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard_buttons())
        )

    elif data == "admin_view_topup" and user_id == ADMIN_ID:
        if pending_topup:
            text = "📋 *Request Top Up Pending:*\n\n"
            for uid, amount in pending_topup.items():
                text += f"User ID: `{uid}`\nJumlah: Rp{amount:,}\n\n"
            text += "Gunakan: `/approve [user_id]` untuk approve."
        else:
            text = "✅ Tidak ada request top up pending."
        query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard_buttons())
        )

    elif data == "admin_gemini_stock" and user_id == ADMIN_ID:
        text = (
            "📦 *Stok VCC Gemini:*\n\n"
            f"Total stok: {len(gemini_stock)}\n\n"
            "Tambah stok dengan format:\n"
            "`/addgemini 6258142602081024|11|2027|853`"
        )
        query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard_buttons())
        )

    # === BELI VCC CHATGPT (AUTO GENERATE) ===
    elif data == "buy_chatgpt":
        balance = get_balance(user_id)
        if balance < 2000:
            text = (
                "❌ Saldo tidak cukup untuk membeli VCC ChatGPT.\n\n"
                f"💰 Saldo Anda: Rp{balance:,}\n"
                "Harga: Rp2.000"
            )
            query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=products_keyboard()
            )
            return

        # potong saldo
        deduct_balance(user_id, 2000)

        # generate VCC via API
        vcc = generate_chatgpt_vcc()
        if not vcc:
            add_balance(user_id, 2000)
            query.edit_message_text(
                "❌ Gagal generate VCC ChatGPT dari API.\nSilakan coba lagi nanti.",
                parse_mode="Markdown",
                reply_markup=products_keyboard()
            )
            return

        # edit pesan menu
        query.edit_message_text(
            "✅ *Pembelian Berhasil!*\n\n"
            "Produk: VCC ChatGPT\n"
            "Harga: Rp2.000\n\n"
            "📩 Detail VCC sudah dikirim ke chat ini.",
            parse_mode="Markdown",
            reply_markup=products_keyboard()
        )

        # kirim produk ke user
        context.bot.send_message(
            chat_id=user_id,
            text=(
                "💳 *VCC ChatGPT Anda:*\n\n"
                f"Card: `{vcc['card']}`\n"
                f"Exp: `{vcc['exp']}`\n"
                f"CVV: `{vcc['cvv']}`\n\n"
                f"💰 Sisa saldo: Rp{get_balance(user_id):,}"
            ),
            parse_mode="Markdown"
        )

        # notif admin
        context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🔔 Transaksi baru!\n\n"
                f"User: `{user_id}`\n"
                "Produk: VCC ChatGPT\n"
                "Harga: Rp2.000"
            ),
            parse_mode="Markdown"
        )

    # === BELI VCC GEMINI (STOK MANUAL ADMIN) ===
    elif data == "buy_gemini":
        balance = get_balance(user_id)
        if balance < 5000:
            text = (
                "❌ Saldo tidak cukup untuk membeli VCC Gemini.\n\n"
                f"💰 Saldo Anda: Rp{balance:,}\n"
                "Harga: Rp5.000"
            )
            query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=products_keyboard()
            )
            return

        if not gemini_stock:
            query.edit_message_text(
                "❌ Stok VCC Gemini sedang kosong.\nSilakan hubungi admin.",
                parse_mode="Markdown",
                reply_markup=products_keyboard()
            )
            return

        # potong saldo
        deduct_balance(user_id, 5000)

        # ambil stok pertama
        vcc = gemini_stock.pop(0)

        query.edit_message_text(
            "✅ *Pembelian Berhasil!*\n\n"
            "Produk: VCC Gemini\n"
            "Harga: Rp5.000\n\n"
            "📩 Detail VCC sudah dikirim ke chat ini.",
            parse_mode="Markdown",
            reply_markup=products_keyboard()
        )

        context.bot.send_message(
            chat_id=user_id,
            text=(
                "💳 *VCC Gemini Anda:*\n\n"
                f"Card: `{vcc['card']}`\n"
                f"Exp: `{vcc['exp']}`\n"
                f"CVV: `{vcc['cvv']}`\n\n"
                f"💰 Sisa saldo: Rp{get_balance(user_id):,}"
            ),
            parse_mode="Markdown"
        )

        context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🔔 Transaksi baru!\n\n"
                f"User: `{user_id}`\n"
                "Produk: VCC Gemini\n"
                "Harga: Rp5.000\n"
                f"Stok Gemini tersisa: {len(gemini_stock)}"
            ),
            parse_mode="Markdown"
        )



# ====== TOPUP HANDLER ======
def handle_topup_request(update, context):
    user_id = update.effective_user.id
    text = update.message.caption or update.message.text

    if text and text.lower().startswith("topup"):
        try:
            amount = int(text.split()[1])
            pending_topup[user_id] = amount

            update.message.reply_text(
                f"✅ Request top up Rp{amount:,} diterima!\n\n"
                f"Menunggu verifikasi admin...\n"
                f"User ID Anda: `{user_id}`",
                parse_mode="Markdown"
            )

            context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 *Request Top Up Baru!*\n\n"
                    f"User ID: `{user_id}`\n"
                    f"Jumlah: Rp{amount:,}\n\n"
                    f"Gunakan: `/approve {user_id}`"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            update.message.reply_text("❌ Format salah! Gunakan: topup [nominal]")


# ====== ADMIN: APPROVE TOPUP & TAMBAH GEMINI ======
def approve_topup(update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        user_id = int(context.args[0])
        if user_id in pending_topup:
            amount = pending_topup[user_id]
            add_balance(user_id, amount)
            del pending_topup[user_id]

            update.message.reply_text(
                f"✅ Top up berhasil!\nUser: {user_id}\nJumlah: Rp{amount:,}"
            )

            bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ *Top Up Berhasil!*\n\n"
                    f"Saldo Rp{amount:,} telah ditambahkan.\n"
                    f"💰 Total saldo: Rp{get_balance(user_id):,}"
                ),
                parse_mode="Markdown"
            )
        else:
            update.message.reply_text("❌ Request tidak ditemukan.")
    except Exception:
        update.message.reply_text("❌ Format: /approve [user_id]")


def add_gemini_stock(update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 1:
        update.message.reply_text("Format: /addgemini 6258142602081024|11|2027|853")
        return

    raw = context.args[0]
    try:
        card, mm, yyyy, cvv = raw.split("|")
        gemini_stock.append({
            "card": card,
            "exp": f"{mm}/{yyyy}",
            "cvv": cvv
        })
        update.message.reply_text(
            f"✅ VCC Gemini ditambahkan ke stok.\nTotal stok sekarang: {len(gemini_stock)}"
        )
    except Exception:
        update.message.reply_text("❌ Format VCC salah. Contoh: 6258142602081024|11|2027|853")


# ====== REGISTER HANDLERS ======
def register_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("approve", approve_topup))
    dispatcher.add_handler(CommandHandler("addgemini", add_gemini_stock))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    dispatcher.add_handler(MessageHandler(Filters.photo | Filters.text, handle_topup_request))


# ====== FASTAPI WEBHOOK ENDPOINT ======
@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    update_data = await request.json()
    update = Update.de_json(update_data, bot)
    dispatcher = Dispatcher(bot, None, workers=4)
    register_handlers(dispatcher)
    dispatcher.process_update(update)
    return {"ok": True}


@app.get("/")
def index():
    return {"status": "Snutz Store Bot Active"}
