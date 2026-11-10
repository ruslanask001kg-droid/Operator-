
#!/usr/bin/env python3
"""BigPay help — Telegram support bot (pyTelegramBotAPI + Flask).

Переменные окружения: BOT_TOKEN, PORT (задаёт Render).
Оператор отвечает клиенту реплаем на пересланное сообщение.
"""
import json
import os
import threading

import telebot
from telebot import types
from flask import Flask

TOKEN = os.environ["BOT_TOKEN"]
OPERATOR_CHAT_ID = -1004313280509  # Установлен ID группы операторов
MAP_FILE = "reply_map.json"  # message_id у оператора -> chat_id клиента

bot = telebot.TeleBot(TOKEN, parse_mode=None)
app = Flask(__name__)

# ---------- Тексты ----------
GREETING = (
    "Здравствуйте!\n"
    "Вас приветствует оператор.\n"
    "Напишите ваш вопрос — ответ в течение 24 часов.\n"
    "Сразу отправьте сумму вывода или чек."
)
TEXT_PAYMENT = (
    "💳 Проблема с оплатой\n\n"
    "Отправьте одним сообщением:\n"
    "• скриншот чека об оплате\n"
    "• ваш ID\n"
    "• сумму\n\n"
    "Оператор проверит платёж и ответит в течение 24 часов."
)
TEXT_WITHDRAW = (
    "💸 Проблема с выводом\n\n"
    "Отправьте одним сообщением:\n"
    "• ваш ID\n"
    "• сумму вывода\n"
    "• код или чек, если есть\n\n"
    "Оператор проверит и ответит в течение 24 часов."
)
TEXT_ADDRESS = (
    "📍 Адрес для вывода в кассе\n\n"
    "🔹 1xBet\n"
    "Город: Бишкек\n"
    "Адрес: Mobcash BigPay\n\n"
    "Закажите вывод в кассе на этот адрес, получите код и отправьте его боту."
)
TEXT_CALL = "✅ Оператор вызван. Напишите ваш вопрос — ответим в течение 24 часов."

BTN_PAY = "💳 Проблема с оплатой"
BTN_WD = "💸 Проблема с выводом"
BTN_ADDR = "📍 Адрес вывода"
BTN_OP = "👤 Позвать оператора"
BUTTON_ANSWERS = {BTN_PAY: TEXT_PAYMENT, BTN_WD: TEXT_WITHDRAW,
                  BTN_ADDR: TEXT_ADDRESS, BTN_OP: TEXT_CALL}


def keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
    kb.row(types.KeyboardButton(BTN_PAY), types.KeyboardButton(BTN_WD))
    kb.row(types.KeyboardButton(BTN_ADDR))
    kb.row(types.KeyboardButton(BTN_OP))
    return kb


# ---------- Связь оператор <-> клиент ----------
def load_map():
    try:
        with open(MAP_FILE) as f:
            return {int(k): v for k, v in json.load(f).items()}
    except Exception:
        return {}


reply_map = load_map()


def save_map():
    try:
        with open(MAP_FILE, "w") as f:
            json.dump(reply_map, f)
    except Exception as e:
        print("save_map error", e)


# ---------- Обработчики ----------
@bot.message_handler(commands=["start"])
def on_start(m):
    bot.send_message(m.chat.id, GREETING, reply_markup=keyboard())


# Сообщения оператора (реплай на пересланное сообщение клиента)
@bot.message_handler(func=lambda m: m.chat.id == OPERATOR_CHAT_ID,
                     content_types=["text", "photo", "document", "video", "voice"])
def from_operator(m):
    if m.reply_to_message is None:
        return
    target = reply_map.get(m.reply_to_message.message_id)
    if target:
        bot.copy_message(target, m.chat.id, m.message_id)


@bot.message_handler(func=lambda m: m.text in BUTTON_ANSWERS)
def on_button(m):
    bot.send_message(m.chat.id, BUTTON_ANSWERS[m.text], reply_markup=keyboard())
    if m.text == BTN_OP:
        u = m.from_user
        bot.send_message(OPERATOR_CHAT_ID,
                         f"🔔 Клиент зовёт оператора: {u.first_name} "
                         f"@{u.username or '-'} (id {u.id})")


@bot.message_handler(content_types=["text", "photo", "document", "video", "voice"])
def from_client(m):
    fwd = bot.forward_message(OPERATOR_CHAT_ID, m.chat.id, m.message_id)
    reply_map[fwd.message_id] = m.chat.id
    u = m.from_user
    info = bot.send_message(
        OPERATOR_CHAT_ID,
        f"От: {u.first_name} @{u.username or '-'} (id {u.id})\n"
        "Ответьте реплаем на это или пересланное сообщение.",
        reply_to_message_id=fwd.message_id)
    reply_map[info.message_id] = m.chat.id
    save_map()
    bot.send_message(m.chat.id, "Принято ✅ Оператор ответит в течение 24 часов.",
                     reply_markup=keyboard())


# ---------- Flask (для Render) ----------
@app.route("/")
def index():
    return "ok"


def run_bot():
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    bot.remove_webhook()
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
