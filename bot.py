"""
ARES Lead Bot — приём лидов от партнёров через реферальные ссылки.
Ссылка для Алексея: t.me/ares_automation_bot?start=alexey
"""
import os
import json
import asyncio
import logging
import traceback
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ares-lead-bot")

# ——— Конфиг ———
BOT_TOKEN = "8798495636:AAFHIs934Kg2LwocusYRD4XwcaQtNpzbiwM"
OWNER_CHAT_ID = 8516176669

# ID которые НЕ считаются лидами (ты сам)
IGNORE_IDS = {8516176669, 683536710}

# Партнёры
PARTNERS = {
    "alexey": {
        "name": "Алексей",
        "chat_id": 683536710,
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
    db["stats"][source] = db["stats"].get(source, 0) + 1
    save_db(db)
    return True


def get_partner_count(source):
    db = load_db()
    return db["stats"].get(source, 0)


def get_total_leads():
    db = load_db()
    return len(db["leads"])


# ——— /start ———
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    source = "direct"
    if args and args[0] in PARTNERS:
        source = args[0]

    # Приветствие — всегда
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

    # Себя не считаем лидом
    if user.id in IGNORE_IDS:
        return

    is_new = add_lead(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        source=source,
    )

    if not is_new:
        return  # Дубликат — не уведомляем повторно

    # ——— Уведомление тебе ———
    username_text = f"@{user.username}" if user.username else "нет username"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    partner_name = PARTNERS[source]["name"] if source in PARTNERS else "Прямой"
    total = get_total_leads()

    owner_msg = (
        f"🔥 <b>Новый лид!</b>\n\n"
        f"👤 {full_name}\n"
        f"📱 {username_text}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"📎 Источник: {partner_name}\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📊 Всего лидов: {total}"
    )
    await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=owner_msg, parse_mode="HTML")

    # ——— Уведомление партнёру ———
    if source in PARTNERS and PARTNERS[source]["chat_id"] and PARTNERS[source]["notify"]:
        partner_count = get_partner_count(source)
        partner_msg = (
            f"📊 <b>Новый клиент через вашу ссылку!</b>\n\n"
            f"👤 {full_name}\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Итого через вас: <b>{partner_count}</b>"
        )
        try:
            await context.bot.send_message(
                chat_id=PARTNERS[source]["chat_id"],
                text=partner_msg,
                parse_mode="HTML",
            )
        except Exception:
            pass


# ——— /stats ———
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_CHAT_ID:
        return
    db = load_db()
    total = len(db["leads"])
    msg = f"📊 <b>Лиды</b>\n\nВсего: <b>{total}</b>\n\n"
    for source, count in db["stats"].items():
        name = PARTNERS[source]["name"] if source in PARTNERS else source
        msg += f"• {name}: {count}\n"
    if db["leads"]:
        msg += "\n<b>Последние:</b>\n"
        for lead in db["leads"][-5:][::-1]:
            name = f"{lead['first_name']} {lead['last_name']}".strip()
            src = PARTNERS.get(lead["source"], {}).get("name", lead["source"])
            msg += f"• {name} — {src} — {lead['date']}\n"
    await update.message.reply_html(msg)


# ——— /setpartner ———
async def setpartner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_CHAT_ID:
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Формат: /setpartner alexey 123456789")
        return
    ref = context.args[0]
    chat_id = int(context.args[1])
    if ref in PARTNERS:
        PARTNERS[ref]["chat_id"] = chat_id
        await update.message.reply_text(f"✅ {ref} → {chat_id}")
    else:
        await update.message.reply_text(f"❌ {ref} не найден")


# ——— HTTP для Render ———
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        total = get_total_leads()
        self.wfile.write(f"OK | Leads: {total}".encode())

    def do_HEAD(self):
        # UptimeRobot Free шлёт HEAD — без этого метод не реализован,
        # BaseHTTPRequestHandler возвращает 501, монитор показывает Down.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


# ——— Запуск ———
async def _notify_owner_safe(app, text: str):
    """Послать алерт владельцу, не сломаться если Telegram недоступен."""
    try:
        await app.bot.send_message(
            chat_id=OWNER_CHAT_ID, text=text, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"notify owner failed: {e}")


async def run_bot_once():
    """Один полноценный жизненный цикл бота: init → polling → блокирующий sleep.
    Если что-то ломается — exception летит наружу, supervisor перезапустит.
    """
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("setpartner", setpartner))

    logger.info("ARES Lead Bot starting (init + polling)")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("ARES Lead Bot is live, polling Telegram")

    # Сообщаем владельцу что бот ожил (полезно после крэшей).
    await _notify_owner_safe(
        app,
        f"✅ <b>ARES Lead Bot online</b>\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"📊 Лидов в базе: {get_total_leads()}"
    )

    try:
        # Долгий sleep — event loop держится, polling работает в фоне.
        while True:
            await asyncio.sleep(3600)
    finally:
        # Корректное закрытие: stop polling → stop app → shutdown.
        try:
            await app.updater.stop()
        except Exception:
            pass
        try:
            await app.stop()
        except Exception:
            pass
        try:
            await app.shutdown()
        except Exception:
            pass


async def run_bot_forever():
    """Supervisor: если run_bot_once падает — рестартим с backoff.
    Без этого один сетевой сбой укладывал процесс на дни (free Render
    не рестартит web-service от внутренних exception, только от exit code).
    """
    backoff = 5
    crash_count = 0
    while True:
        try:
            await run_bot_once()
            # Если run_bot_once вернулся без ошибки — это странно,
            # но перезапустимся аккуратно.
            logger.warning("run_bot_once returned cleanly, restarting")
            backoff = 5
        except Exception as e:
            crash_count += 1
            tb = traceback.format_exc()
            logger.error(
                f"run_bot_once crashed (#{crash_count}): {e}\n{tb}"
            )
            # Пытаемся пингнуть владельцу через прямой Bot, без app.
            try:
                from telegram import Bot
                bot = Bot(BOT_TOKEN)
                await bot.send_message(
                    chat_id=OWNER_CHAT_ID,
                    text=(
                        f"⚠️ <b>Lead Bot crash #{crash_count}</b>\n"
                        f"<code>{str(e)[:300]}</code>\n"
                        f"Перезапуск через {backoff}s"
                    ),
                    parse_mode="HTML",
                )
            except Exception as ne:
                logger.error(f"crash-notify failed: {ne}")

        await asyncio.sleep(backoff)
        # Экспоненциальный бэкофф до 5 минут — на случай длительного
        # сетевого сбоя или token-проблемы.
        backoff = min(backoff * 2, 300)


def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    asyncio.run(run_bot_forever())


if __name__ == "__main__":
    main()
