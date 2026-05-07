########### EDIT THIS SECTION ############
TOKEN = "TOKEN_GOES_HERE"
AGENT_ID = 'AGENT_ID_GOES_HERE'
SERVERS = [] # Only modify for cloud deployment
##########################################

#########################################
#           DO NOT EDIT BELOW!          #
#########################################

# Import/install necessary packages
import os
import sys
import gzip
import base64
import subprocess
import json
import asyncio
import urllib.request
import random
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "discord.py-self"]) # always keep discord.py-self updated since this gets important updates to help avoid detection by Discord!
except Exception as e:
    print(f"[Setup] Warning: Could not update discord.py-self: {e}")
try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QListWidget, QPushButton,
        QVBoxLayout, QLabel, QMessageBox, QListWidgetItem
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
except ImportError:
    print("PyQt6 not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt6"])
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QListWidget, QPushButton,
        QVBoxLayout, QLabel, QMessageBox, QListWidgetItem
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
try:
    import discord
    from discord.ext import commands
except:
    print("Discord.py-self not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "discord.py-self"])
    import discord
    from discord.ext import commands

##################################################################################

server_url = 'https://chatty-eb46.onrender.com/message'

message_buffer = []
buffer_lock = asyncio.Lock()

os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts.warning=false;*.warning=false" # Suppress an annoying warning from PyQT
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)
default_font = QFont("Segoe UI", 10)
app.setFont(default_font)

bot = commands.Bot(
    command_prefix='/',
    self_bot=True,
    chunk_guilds_at_startup=False,
    guild_subscriptions=False,
    reconnect=True,
    heartbeat_timeout=120,          # Increased from default
    max_messages=2000,
)

async def format_msg(message):
    avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url

    message_json = {
        'verify': AGENT_ID,
        'server': None,
        'from': [message.author.display_name, message.author.name, message.author.id, avatar_url],
        'to': None,
        'content': None,
        'files': None,
        'time': message.created_at.timestamp(),
        'reply_to': None,
        'link': message.jump_url,
        'bot': message.author.bot
    }

    if message.guild is not None:
        message_json['server'] = [message.guild.name, message.guild.id]
        message_json['to'] = [message.channel.name, message.channel.id]
        message_json['content'] = message.content

        if message.attachments:
            message_json['files'] = [a.url for a in message.attachments]

        if message.reference:
            message_json['reply_to'] = message.reference.message_id
    else:
        return None

    return message_json

async def choose_servers_gui(guilds):
    selected_servers = []

    # ---- Window Setup ----
    window = QWidget()
    window.setWindowTitle("Select Discord Servers")
    window.setFixedSize(500, 450)
    window.setStyleSheet("""
        QWidget {
            background-color: #2b2d31;
            color: #ffffff;
            font-family: 'Segoe UI';
        }
        QLabel {
            font-size: 16px;
            margin-bottom: 8px;
        }
        QListWidget {
            background-color: #313338;
            border: 1px solid #202225;
            padding: 6px;
            selection-background-color: #5865F2;
            font-size: 13px;
        }
        QPushButton {
            background-color: #5865F2;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #4752C4;
        }
        QPushButton:pressed {
            background-color: #3C45A5;
        }
    """)

    # ---- Layout ----
    layout = QVBoxLayout(window)

    label = QLabel("Select servers to collect from:")
    layout.addWidget(label)

    list_widget = QListWidget()
    list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    for g in guilds:
        item = QListWidgetItem(f"{g.name} ({g.id})")
        list_widget.addItem(item)
    layout.addWidget(list_widget)

    confirm_button = QPushButton("Confirm")
    layout.addWidget(confirm_button, alignment=Qt.AlignmentFlag.AlignCenter)

    # ---- Confirm Logic ----
    def on_confirm():
        selections = list_widget.selectedItems()
        if not selections:
            QMessageBox.warning(window, "No Selection", "Please select at least one server.")
            return
        for item in selections:
            text = item.text()
            guild_id = int(text.split("(")[-1].split(")")[0])
            selected_servers.append(guild_id)
        window.close()

    confirm_button.clicked.connect(on_confirm)

    # ---- Show GUI ----
    window.show()

    # Keep running while window open
    while window.isVisible():
        app.processEvents()
        await asyncio.sleep(0.05)

    return selected_servers

async def send_msg(data, content_type='application/json'):
    if data is None:
        return

    headers = {"Content-Type": content_type}
    if content_type == "gzip":
        headers["Content-Encoding"] = "gzip"   # Helps some servers

    req = urllib.request.Request(server_url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60) as response:  # longer timeout for big payloads
            result = response.read().decode('utf-8', errors='ignore')
            print(f'[SUCCESS] Sent successfully. Status: {response.status} | Response: {result[:300]}')
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')[:500]
        print(f'[ERROR] HTTP {e.code} {e.reason} | Body: {error_body}')
    except urllib.error.URLError as e:
        print(f'[ERROR] Connection error: {e.reason}')
    except Exception as e:
        print(f'[ERROR] Unexpected send error: {e}')

# Listen for new messages
@bot.listen('on_message')
async def on_message(message):
    if message.guild is None or message.guild.id not in SERVERS:
        return
    
    await asyncio.sleep(random.uniform(0.05, 0.7))

    msg_json = await format_msg(message)
    if msg_json is None:
        return

    async with buffer_lock:
        message_buffer.append(msg_json)

async def flush_buffer_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(18 + random.uniform(12, 35))

        async with buffer_lock:
            if not message_buffer:
                continue
            batch = message_buffer.copy()
            message_buffer.clear()

        try:
            print(f"[BATCH] Sending {len(batch)} messages...")
            compressed = gzip.compress(json.dumps(batch).encode('utf-8'))
            encoded = base64.b64encode(compressed)
            await send_msg(encoded, content_type='gzip')
        except Exception as e:
            print(f"[ERROR] Batch failed: {e}")
            async with buffer_lock:
                message_buffer.extend(batch)

# List of possible presences
PRESENCE_OPTIONS = [
    {"status": discord.Status.online,  "activity": None},                                   # Idle / No activity
    {"status": discord.Status.idle,    "activity": None},                                   # Idle status
    {"status": discord.Status.online, 
     "activity": discord.Activity(type=discord.ActivityType.playing, name="Roblox")},       # Playing Roblox
]

async def presence_rotator():
    """Randomly changes presence every 45-90 minutes"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            choice = random.choice(PRESENCE_OPTIONS)
            
            await bot.change_presence(
                status=choice["status"],
                activity=choice.get("activity")
            )
            
            # Random delay between 521 - 4053 minutes
            await asyncio.sleep(random.randint(521, 4053) * 60)
            
        except Exception as e:
            print(f"[Presence] Error changing status: {e}")
            await asyncio.sleep(624)  # Wait ~10 minutes on error

async def gateway_keepalive():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Small no-op to help maintain connection
            if bot.is_ready():
                pass
        except:
            pass
        await asyncio.sleep(240)  # Every 4 minutes

@bot.event
async def on_ready():
    global SERVERS

    # Start the rotator task
    bot.loop.create_task(presence_rotator())

    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    if SERVERS == []:
        SERVERS = await choose_servers_gui(bot.guilds)
    if SERVERS == []:
        print('[ERROR] No servers selected, quitting...')
        exit()

    bot.loop.create_task(flush_buffer_loop())
    bot.loop.create_task(gateway_keepalive())

if TOKEN == 'TOKEN_GOES_HERE':
    print(f'[ERROR] You must first enter your token in the script! Please open the script in a text editor like Visual Studio Code or Notepad and follow the instructions in the New Agent Setup Guide to retrieve your token and then enter it in the token variable.')
    exit()
if AGENT_ID == 'AGENT_ID_GOES_HERE':
    print(f'[ERROR] You must first enter your assigned Agent ID in the script! Please open the script in a text editor like Visual Studio Code or Notepad and enter your Agent ID. If you don\'t have one yet, talk to a Chatty Administrator.')
    exit()
bot.run(TOKEN)