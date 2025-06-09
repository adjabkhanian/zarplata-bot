import requests
import sqlite3
import calendar
from datetime import datetime, date, timedelta
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ConversationHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from dateutil.relativedelta import relativedelta

# --- Состояния для ConversationHandler ---
BAR, RASHOD, SHTRAF = range(3)

# === Airtable настройки ===
AIRTABLE_TOKEN = "pat0va1EYWcKoftLt.232d9d55b86b36bef62ab68e16a64bb36d6e7b64ff3a97c2ec9a983982728bbc"
AIRTABLE_BASE_ID = "appxB3WUsTmbNSlqx"
AIRTABLE_TABLE_NAME = "Zarplata"

def send_to_airtable(date_str, typ, amount, comment):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"fields": {"Date": date_str, "Type": typ, "Amount": amount, "Comment": comment}}
    requests.post(url, headers=headers, json=data)

def init_db():
    conn = sqlite3.connect("zarplata.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY, date TEXT, type TEXT, amount REAL, comment TEXT)''')
    conn.commit()
    conn.close()

def add_record(rec_type, amount, comment=""):
    date_str = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("zarplata.db")
    conn.execute(
        "INSERT INTO records (date, type, amount, comment) VALUES (?, ?, ?, ?)",
        (date_str, rec_type, amount, comment)
    )
    conn.commit()
    conn.close()
    send_to_airtable(date_str, rec_type, amount, comment)

# --- Старт / Кнопки ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [KeyboardButton("🕑 Дневная"), KeyboardButton("🌙 Ночная")],
        [KeyboardButton("🍷 Бар"), KeyboardButton("💸 Расход")],
        [KeyboardButton("🚫 Штраф"), KeyboardButton("📊 Отчёт")]
    ]
    await update.message.reply_text("Выбери действие 👇", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def handle_buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if t == "🕑 Дневная":
        add_record("смена", 2500, "дневная")
        await update.message.reply_text("✅ Дневная смена добавлена.")
    elif t == "🌙 Ночная":
        add_record("смена", 2500, "ночная")
        await update.message.reply_text("✅ Ночная смена добавлена.")
    elif t == "🍷 Бар":
        await update.message.reply_text("Введите сумму бара:")
        return BAR
    elif t == "💸 Расход":
        await update.message.reply_text("Введите: сумма и комментарий (напр. ‘300 еда’):")
        return RASHOD
    elif t == "🚫 Штраф":
        await update.message.reply_text("Введите: сумма и комментарий (напр. ‘500 опоздание’):")
        return SHTRAF
    elif t == "📊 Отчёт":
        now = date.today()
        last = now.replace(day=1) - timedelta(days=1)
        kb2 = [
            [InlineKeyboardButton("📆 Текущий", callback_data=f"month_0")],
            [InlineKeyboardButton("⬅️ Предыдущий", callback_data=f"month_-1")],
            [InlineKeyboardButton("📅 Май", callback_data="month_2024_5")],
            [InlineKeyboardButton("📅 Апрель", callback_data="month_2024_4")]
        ]
        await update.message.reply_text("Выбери месяц:", reply_markup=InlineKeyboardMarkup(kb2))
    return ConversationHandler.END

# --- Ввод суммы BAR, RASHOD, SHTRAF ---
async def bar_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        percent = 0
        if amount < 3500:
            percent = 5
        elif 3500 <= amount < 4000:
            percent = 6
        elif 4000 <= amount < 4500:
            percent = 7
        elif 4500 <= amount < 5000:
            percent = 8
        elif 5000 <= amount < 5500:
            percent = 9
        elif 5500 <= amount < 10000:
            percent = 10
        elif amount >= 10000:
            percent = 15

        profit = amount * percent / 100
        add_record("бар", profit, f"{amount}₽ — {percent}%")
        await update.message.reply_text(f"🍷 Бар: {amount}₽ → {percent}% = +{profit:.0f}₽")
    except:
        await update.message.reply_text("Неверный формат. Введите сумму числом.")
    return ConversationHandler.END

async def rashod_input(update: Update, ctx):
    parts = update.message.text.split(maxsplit=1)
    try:
        amt = float(parts[0])
        comm = parts[1] if len(parts) > 1 else "Без комментария"
        add_record("расход", -amt, comm)
        await update.message.reply_text(f"💸 Расход: −{amt}₽ ({comm})")
    except:
        await update.message.reply_text("Ошибка — введите: сумма + комментарий.")

    return ConversationHandler.END

async def shtraf_input(update: Update, ctx):
    parts = update.message.text.split(maxsplit=1)
    try:
        amt = float(parts[0])
        comm = parts[1] if len(parts) > 1 else "Без комментария"
        add_record("штраф", -amt, comm)
        await update.message.reply_text(f"🚫 Штраф: −{amt}₽ ({comm})")
    except:
        await update.message.reply_text("Ошибка — введите: сумма + комментарий.")
    return ConversationHandler.END

# --- Обработка выбора месяца ---
async def month_cb(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    data = q.data  # e.g. month_-1 or month_2024_5
    if data.startswith("month_"):
        _, *rest = data.split("_")
        if rest[0] in ("0", "-1"):
            offset = int(rest[0])
            tgt = date.today() + relativedelta(months=offset)
            y, m = tgt.year, tgt.month
        else:
            y, m = map(int, rest)
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])
        msg = report_from_airtable(start, end, y, m)
        await q.edit_message_text(msg)

def report_from_airtable(start, end, y, m):
    u = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    hdr = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    resp = requests.get(u, headers=hdr, params={"pageSize": 100}).json()
    recs = resp.get("records", [])

    sw, bp, rs, st = 0, 0, 0, 0
    for r in recs:
        f = r.get("fields", {})
        d = f.get("Date", "")
        tp = f.get("Type", "").lower()
        am = f.get("Amount", 0)
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
        except:
            continue
        if not (start <= dt <= end): continue
        if tp == "смена": sw += 1
        if tp == "бар": bp += am
        if tp == "расход": rs += abs(am)
        if tp == "штраф": st += abs(am)
    tot = sw*2500 + bp - rs - st
    return (
        f"📊 Отчёт {calendar.month_name[m]} {y}:\n"
        f"Смены: {sw} ×2500₽ = {sw*2500}₽\n"
        f"Бар: +{bp:.0f}₽\n"
        f"Расходы: -{rs:.0f}₽\n"
        f"Штрафы: -{st:.0f}₽\n"
        f"Итого: {tot:.0f}₽"
    )

# --- Simple echo for testing ---
async def echo(update: Update, ctx):
    await update.message.reply_text(f"Ты написал: {update.message.text}")

async def cancel(update: Update, ctx):
    await update.message.reply_text("ОК, отмена.")
    return ConversationHandler.END

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token("8092177846:AAHO4f8yZTYvfDH76Ort9wmds7XeQ9kCgr0").build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons)],
        states={
            BAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, bar_input)],
            RASHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, rashod_input)],
            SHTRAF: [MessageHandler(filters.TEXT & ~filters.COMMAND, shtraf_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(month_cb, pattern=r"^month_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    print("✅ Бот запущен и слушает команды!")
    app.run_polling()