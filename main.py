import os
import json
import logging
from pathlib import Path

from telegram import (
Update,
InlineKeyboardButton,
InlineKeyboardMarkup,
)
from telegram.ext import (
Application,
CommandHandler,
MessageHandler,
ContextTypes,
ConversationHandler,
filters,
)

logging.basicConfig(
format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
level=logging.INFO,
)
logger = logging.getLogger(name)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

DATA_FILE = Path(os.environ.get("DATA_FILE", "data.json"))

ADD_NAME, ADD_LINKS, ADD_POSTER = range(3)
DELETE_NAME = 3

def load_data():
if not DATA_FILE.exists():
return {}
try:
with DATA_FILE.open("r", encoding="utf-8") as file:
data = json.load(file)
return data if isinstance(data, dict) else {}
except (json.JSONDecodeError, OSError):
logger.exception("Could not load database")
return {}

def save_data(data):
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
temp_file = DATA_FILE.with_suffix(".tmp")
with temp_file.open("w", encoding="utf-8") as file:
json.dump(data, file, ensure_ascii=False, indent=2)
temp_file.replace(DATA_FILE)

anime_db = load_data()

def is_admin(update: Update):
return (
update.effective_user is not None
and update.effective_user.id == ADMIN_ID
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = (
"🎬 Welcome to Anime Channel Filter Bot!\n\n"
"🔎 Search for your favourite anime by name.\n"
"🔗 Get matching public or private channel links.\n\n"
"Use /search <anime name> to search."
)
await update.effective_message.reply_text(text)

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = " ".join(context.args).strip()

if not query:
    await update.effective_message.reply_text(
        "🔎 Usage: /search Black Clover"
    )
    return

matches = [
    (name, details)
    for name, details in anime_db.items()
    if query.casefold() in name.casefold()
]

if not matches:
    await update.effective_message.reply_text(
        f"❌ No anime found for: {query}"
    )
    return

for name, details in matches[:10]:
    links = details.get("links", [])
    keyboard = [
        [InlineKeyboardButton(label, url=url)]
        for label, url in links
    ]

    caption = f"🎬 {name}\n\n👇 Choose a channel below!"

    poster = details.get("poster")
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if poster:
        try:
            await update.effective_message.reply_photo(
                photo=poster,
                caption=caption,
                reply_markup=markup,
            )
            continue
        except Exception:
            logger.warning("Could not send poster for %s", name)

    await update.effective_message.reply_text(
        caption,
        reply_markup=markup,
    )

async def add_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
await update.effective_message.reply_text("⛔ Admin only.")
return ConversationHandler.END

await update.effective_message.reply_text(
    "🎬 Send the anime name."
)
return ADD_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
name = update.effective_message.text.strip()

if not name:
    await update.effective_message.reply_text("Please enter a name.")
    return ADD_NAME

context.user_data["anime_name"] = name
await update.effective_message.reply_text(
    "🔗 Send channel links, one per line.\n\n"
    "Format:\n"
    "Tamil Anime | https://t.me/Tamil_New_Animes\n"
    "Private Channel | https://t.me/+YOUR_INVITE_HASH\n\n"
    "Use the full invite URL for private channels."
)
return ADD_LINKS

async def receive_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
lines = update.effective_message.text.splitlines()
links = []

for line in lines:
    if "|" not in line:
        continue

    label, url = [part.strip() for part in line.split("|", 1)]

    if not label:
        label = "📢 Open Channel"

    if not (
        url.startswith("https://t.me/")
        or url.startswith("http://t.me/")
    ):
        continue

    links.append((label, url))

if not links:
    await update.effective_message.reply_text(
        "❌ No valid Telegram links found.\n"
        "Send at least one link as Label | https://t.me/username"
    )
    return ADD_LINKS

context.user_data["anime_links"] = links

await update.effective_message.reply_text(
    "🖼️ Send a poster image as a photo, or type /skip to continue."
)
return ADD_POSTER

async def receive_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_message.photo:
poster = update.effective_message.photo[-1].file_id
else:
poster = None

name = context.user_data["anime_name"]

anime_db[name] = {
    "links": context.user_data["anime_links"],
    "poster": poster,
}

save_data(anime_db)
context.user_data.clear()

await update.effective_message.reply_text(
    f"✅ Anime added successfully!\n\n🎬 {name}"
)
return ConversationHandler.END

async def skip_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
name = context.user_data["anime_name"]

anime_db[name] = {
    "links": context.user_data["anime_links"],
    "poster": None,
}

save_data(anime_db)
context.user_data.clear()

await update.effective_message.reply_text(
    f"✅ Anime added successfully!\n\n🎬 {name}"
)
return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
context.user_data.clear()
await update.effective_message.reply_text("❎ Operation cancelled.")
return ConversationHandler.END

async def delete_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
await update.effective_message.reply_text("⛔ Admin only.")
return

name = " ".join(context.args).strip()

if not name:
    await update.effective_message.reply_text(
        "Usage: /delanime Black Clover"
    )
    return

key = next(
    (item for item in anime_db if item.casefold() == name.casefold()),
    None,
)

if key is None:
    await update.effective_message.reply_text("❌ Anime not found.")
    return

del anime_db[key]
save_data(anime_db)

await update.effective_message.reply_text(
    f"🗑️ Deleted: {key}"
)

async def list_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
await update.effective_message.reply_text("⛔ Admin only.")
return

if not anime_db:
    await update.effective_message.reply_text("📚 No anime added yet.")
    return

names = list(anime_db.keys())
text = "📚 Registered Anime:\n\n" + "\n".join(
    f"{i}. {name}" for i, name in enumerate(names, 1)
)

for start_index in range(0, len(text), 3500):
    await update.effective_message.reply_text(
        text[start_index:start_index + 3500]
    )

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = update.effective_message.text.strip()

if text.startswith("/"):
    return

context.args = text.split()
await search(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
logger.error("Unhandled bot error", exc_info=context.error)

def main():
app = Application.builder().token(BOT_TOKEN).build()

add_conversation = ConversationHandler(
    entry_points=[CommandHandler("addanime", add_anime)],
    states={
        ADD_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
        ],
        ADD_LINKS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_links)
        ],
        ADD_POSTER: [
            MessageHandler(filters.PHOTO, receive_poster),
            CommandHandler("skip", skip_poster),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("search", search))
app.add_handler(CommandHandler("delanime", delete_anime))
app.add_handler(CommandHandler("listanime", list_anime))
app.add_handler(add_conversation)
app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text)
)
app.add_error_handler(error_handler)

logger.info("Anime Channel Filter Bot started.")
app.run_polling(drop_pending_updates=True)

if name == "main":
main()
