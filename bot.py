"""
ARES Lead Bot — приём лидов от партнёров через реферальные ссылки.

Ссылка для Алексея: t.me/ares_automation_bot?start=alexey
Человек нажимает Start → бот приветствует → тебе и Алексею приходит уведомление.
"""
import os
import json
import asyncio
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from pathlib import Path

# ——— Конфиг ———
BOT_TOKEN = "8798495636:AAFHIs934Kg2LwocusYRD4XwcaQtNpzbiwM"
OWNER_CHAT_ID = 8516176669  # Твой Telegram ID

# Партнёры: ref_код → данные
PARTNERS = {
    "alexey": {
        "name": "Алексей",
        "chat_id": None,  # Заполнится когда Алексей даст свой chat_id
        "notify": True,
    },
}

# ——— База данных (JSON) ———
DB_PATH = Path(__file__).parent / "leads.json"


def load_db():
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"leads": [], "stats": {}}


def save_db(db):
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def add_lead(user_id, username, first_name, last_name, source):
    db = load_db()

    # Проверка дубликата
    if any(l["user_id"] == user_id for l in db["leads"]):
        return False

    db["leads"].append({
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "source": source,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "status": "new",
    })

    # Статистика по партнёру
    db["stats"][source] = db["stats"].get(source, 0) + 1
    save_db(db)
    return True


def get_partner_count(source):
    db = load_db()
    return db["stats"].get(source, 0)


def get_total_leads():
    db = load_db()
    return len(db["leads"])


# ——— Обработчик /start ———
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    # Определить источник
    source = "direct"
    if args and args[0] in PARTNERS:
        source = args[0]

    # Сохранить лид
    is_new = add_lead(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        source=source,
    )

    # Приветствие пользователю
    welcome = (
        f"Здравствуйте, {user.first_name}! 👋\n\n"
        f"Вы попали в <b>ARES — автоматизация бизнеса</b>.\n\n"
        f"Мы помогаем клиникам, салонам, автосервисам и другим бизнесам "
        f"автоматизировать приём звонков и запись клиентов.\n\n"
        f"✅ Голосовой ассистент принимает звонки 24/7\n"
        f"✅ Записывает клиентов в расписание\n"
        f"✅ Напоминает о визитах\n"
        f"✅ Отправляет отчёт владельцу каждый вечер\n\n"
        f"📩 Наш специалист свяжется с вами в ближайшее время!"
    )
    await update.message.reply_html(welcome)

    if not is_new:
        return  # Дубликат — не уведомляем

    # ——— Уведомление тебе ———
    username_text = f"@{user.username}" if user.username else "нет username"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    partner_name = PARTNERS[source]["name"] if source in PARTNERS else "Прямой"
    total = get_total_leads()

    owner_msg = (
        f"🔥 <b>Новый лид!</b>\n\n"
        f"👤 Имя: {full_name}\n"
        f"📱 Username: {username_text}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📎 Источник: {partner_name}\n"
        f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📊 Всего лидов: {total}"
    )

    bot = context.bot
    await bot.send_message(chat_id=OWNER_CHAT_ID, text=owner_msg, parse_mode="HTML")

    # ——— Уведомление партнёру ———
    if source in PARTNERS and PARTNERS[source]["chat_id"] and PARTNERS[source]["notify"]:
        partner_count = get_partner_count(source)
        partner_msg = (
            f"📊 <b>Новый клиент через вашу ссылку!</b>\n\n"
            f"👤 {full_name}\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Итого через вас: <b>{partner_count}</b> лидов"
        )
        try:
            await bot.send_message(
                chat_id=PARTNERS[source]["chat_id"],
                text=partner_msg,
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Не удалось уведомить партнёра {source}: {e}")

    print(f"[lead] {full_name} ({username_text}) ot {partner_name}")


# ——— Команда /stats — статистика для тебя ———
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_CHAT_ID:
        return

    db = load_db()
    total = len(db["leads"])

    msg = f"📊 <b>Статистика лидов</b>\n\nВсего: <b>{total}</b>\n\n"

    for source, count in db["stats"].items():
        name = PARTNERS[source]["name"] if source in PARTNERS else source
        msg += f"• {name}: {count}\n"

    # Последние 5 лидов
    if db["leads"]:
        msg += "\n<b>Последние лиды:</b>\n"
        for lead in db["leads"][-5:][::-1]:
            name = f"{lead['first_name']} {lead['last_name']}".strip()
            src = PARTNERS.get(lead["source"], {}).get("name", lead["source"])
            msg += f"• {name} — {src} — {lead['date']}\n"

    await update.message.reply_html(msg)


# ——— Команда /setpartner — привязать chat_id партнёра ———
async def setpartner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_CHAT_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /setpartner alexey 123456789")
        return

    ref = context.args[0]
    chat_id = int(context.args[1])

    if ref in PARTNERS:
        PARTNERS[ref]["chat_id"] = chat_id
        await update.message.reply_text(f"✅ Партнёр {ref} привязан к chat_id {chat_id}")
    else:
        await update.message.reply_text(f"❌ Партнёр {ref} не найден")


# ——— Мини HTTP сервер для Render (бесплатный Web Service) ———
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        stats = getStats()
        self.wfile.write(f"ARES Lead Bot OK | Leads: {stats['total_sent']}".encode())
    def log_message(self, format, *args):
        pass  # тихий лог

def getStats():
    db = load_db()
    return {"total_sent": len(db.get("leads", []))}

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# ——— Запуск ———
async def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("setpartner", setpartner))

    print("[BOT] ARES Lead Bot running")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    # Держим бота живым
    while True:
        await asyncio.sleep(3600)


def main():
    # HTTP сервер для Render health check
    threading.Thread(target=start_health_server, daemon=True).start()

    # Запуск бота
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
