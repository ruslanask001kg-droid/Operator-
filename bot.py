#!/usr/bin/env python3
"""BigPay help — Telegram support bot (только стандартная библиотека Python 3.8+).

Запуск:
    export BOT_TOKEN="токен от @BotFather для @Bighp_bot"
    export OPERATOR_CHAT_ID="ваш Telegram ID или ID группы операторов"
    python3 bigpay_help_bot.py

Как это работает:
  * /start -> приветствие + 4 кнопки.
  * Кнопки показывают инструкции (тексты ниже можно менять).
  * Любое сообщение клиента (текст, фото, чек) пересылается оператору.
  * Оператор отвечает через «Ответить» (reply) на пересланное сообщение —
    бот отправляет ответ клиенту.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import urllib.error

TOKEN = os.environ["BOT_TOKEN"]
OPERATOR_CHAT_ID = int(os.environ["OPERATOR_CHAT_ID"])
API = f"https://api.telegram.org/bot{TOKEN}/"
MAP_FILE = "reply_map.json"  # message_id у оператора -> chat_id клиента

# ---------- Тексты (редактируйте под себя) ----------
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

# Статичная (постоянная) клавиатура внизу экрана
KEYBOARD = {
    "keyboard": [
        [{"text": BTN_PAY}, {"text": BTN_WD}],
        [{"text": BTN_ADDR}],
        [{"text": BTN_OP}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}
BUTTON_ANSWERS = {BTN_PAY: TEXT_PAYMENT, BTN_WD: TEXT_WITHDRAW,
                  BTN_ADDR: TEXT_ADDRESS, BTN_OP: TEXT_CALL}


def call(method, **params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        API + method, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=70) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print("HTTP error", method, e.read().decode(errors="ignore"))
    except Exception as e:  # сеть и т.п.
        print("Error", method, e)
        time.sleep(3)
    return {"ok": False}


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


def send_menu(chat_id):
    call("sendMessage", chat_id=chat_id, text=GREETING, reply_markup=KEYBOARD)


def handle_message(m):
    chat_id = m["chat"]["id"]
    text = m.get("text", "")

    # Сообщение от оператора (reply на пересланное сообщение клиента)
    if chat_id == OPERATOR_CHAT_ID:
        target = reply_map.get(m.get("reply_to_message", {}).get("message_id"))
        if target:
            call("copyMessage", chat_id=target, from_chat_id=chat_id,
                 message_id=m["message_id"])
        return

    if text.startswith("/start"):
        send_menu(chat_id)
        return

    # Нажатие статичной кнопки
    if text in BUTTON_ANSWERS:
        call("sendMessage", chat_id=chat_id, text=BUTTON_ANSWERS[text],
             reply_markup=KEYBOARD)
        if text == BTN_OP:
            u = m.get("from", {})
            call("sendMessage", chat_id=OPERATOR_CHAT_ID,
                 text=f"🔔 Клиент зовёт оператора: {u.get('first_name', '')} "
                      f"@{u.get('username', '-')} (id {u.get('id')})")
        return

    # Сообщение клиента -> оператору
    fwd = call("forwardMessage", chat_id=OPERATOR_CHAT_ID, from_chat_id=chat_id,
               message_id=m["message_id"])
    if fwd.get("ok"):
        reply_map[fwd["result"]["message_id"]] = chat_id
        u = m.get("from", {})
        info = call("sendMessage", chat_id=OPERATOR_CHAT_ID,
                    text=f"От: {u.get('first_name', '')} @{u.get('username', '-')} "
                         f"(id {u.get('id')})\nОтветьте реплаем на это или пересланное сообщение.",
                    reply_to_message_id=fwd["result"]["message_id"])
        if info.get("ok"):
            reply_map[info["result"]["message_id"]] = chat_id
        save_map()
        call("sendMessage", chat_id=chat_id,
             text="Принято ✅ Оператор ответит в течение 24 часов.",
             reply_markup=KEYBOARD)


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def start_health_server():
    """Render Web Service требует открытый порт ($PORT)."""
    port = os.environ.get("PORT")
    if port:
        srv = HTTPServer(("0.0.0.0", int(port)), Health)
        threading.Thread(target=srv.serve_forever, daemon=True).start()


def main():
    start_health_server()
    print("Bot started")
    offset = 0
    while True:
        res = call("getUpdates", offset=offset, timeout=50,
                   allowed_updates=["message"])
        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            try:
                if "message" in upd:
                    handle_message(upd["message"])
            except Exception as e:
                print("handler error", e)


if __name__ == "__main__":
    main()
