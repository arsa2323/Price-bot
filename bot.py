import os, re, logging
import telebot

# ===== ТОКЕН НЕ ВПИСЫВАЕМ! Оставляем как есть =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "СЮДА_ВАШ_ТОКЕН")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
RUN_MODE = os.environ.get("RUN_MODE", "polling")

MARKUP   = 8
ROUND_TO = 100

bot = telebot.TeleBot(BOT_TOKEN)
OWNER_ID   = None
CHANNEL_ID = None

CONTACT_PATTERNS = [
    r'@[A-Za-z][A-Za-z0-9_]{4,}',
    r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
    r'\b(?:тел|phone|whatsapp|wa|tg|связь|менеджер|по вопросам|писать|звонить)[:\s]*[^\n]*',
]
def clean_contacts(t):
    for p in CONTACT_PATTERNS:
        t = re.sub(p, '', t, flags=re.I)
    
    return re.sub(r'\n{3,}', '\n\n', t).strip()

PRICE_RE = re.compile(r'(?<!\d)(\d{1,3}(?:[ \u00A0\u2009]\d{3})+|\d{2,7})(?!\d)')
def fmt(n):  return f"{n:,}".replace(",", " ")
def bump(m):
    raw = m.group(1).replace(" ", "").replace("\u00A0", "").replace("\u2009", "")
    try:    price = int(raw)
    except: return m.group(0)
    if price < 1000:
        return m.group(0)
    new = round(price * (1 + MARKUP / 100), -2)
    return fmt(int(new))
def transform(text):
    if not text: return ""
    return PRICE_RE.sub(bump, clean_contacts(text))

@bot.message_handler(commands=["start"])
def start(m):
    global OWNER_ID
    if OWNER_ID is None:
        OWNER_ID = m.from_user.id
        bot.reply_to(m, f"OK owner {m.from_user.id}. Forward posts here.")
    elif m.from_user.id == OWNER_ID:
        bot.reply_to(m, "Forward a post, I will process it.")
    else:
        bot.reply_to(m, "No access.")

@bot.channel_post_handler()
def bind_channel(m):
    global CHANNEL_ID
    if CHANNEL_ID != m.chat.id:
        CHANNEL_ID = m.chat.id
        if OWNER_ID:
            try: bot.send_message(OWNER_ID, f"Channel bound: {m.chat.id}")
            except Exception: logging.exception("bind")

@bot.message_handler(content_types=["text", "photo", "document", "video"],
                     func=lambda m: OWNER_ID is not None and m.from_user.id == OWNER_ID)
def on_forward(m):
    if CHANNEL_ID is None:
        bot.reply_to(m, "Add bot as admin to channel and post once there first.")
        return
    new_text = transform(m.text or m.caption or "")
    if not new_text:
        bot.reply_to(m, "No price text found, skipped.")
        return
    try:
        if m.photo:
            bot.send_photo(CHANNEL_ID, m.photo[-1].file_id, caption=new_text)
        else:
            bot.send_message(CHANNEL_ID, new_text)
        bot.reply_to(m, "Posted to channel.")
    except Exception as e:
        bot.reply_to(m, f"Error: {e}")

if RUN_MODE == "webhook":
    from flask import Flask, request
    app = Flask(__name__)
    @app.route("/webhook", methods=["POST"])
    def webhook():
        bot.process_new_updates([telebot.types.Update.de_json(request.get_json())])
        return "ok", 200
    @app.route("/")
    def root(): return "alive"
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8443)))
else:
    print("Bot started (polling).")
    bot.infinity_polling()
