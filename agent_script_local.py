########### EDIT THIS SECTION ############
TOKEN = 'YOUR_TOKEN_GOES_HERE'
AGENT_ID = 'AGENT_ID_GOES_HERE'
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
import datetime
import asyncio
import urllib.request
try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QListWidget, QPushButton,
        QVBoxLayout, QLabel, QMessageBox, QListWidgetItem,
        QComboBox, QCheckBox, QHBoxLayout
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
except ImportError:
    print("PyQt6 not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt6"])
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QListWidget, QPushButton,
        QVBoxLayout, QLabel, QMessageBox, QListWidgetItem,
        QComboBox, QCheckBox, QHBoxLayout
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
servers = []

message_buffer = []
buffer_lock = asyncio.Lock()

os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts.warning=false;*.warning=false" # Suppress an annoying warning from PyQT
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)
default_font = QFont("Segoe UI", 10)
app.setFont(default_font)

bot = commands.Bot(command_prefix='/', self_bot=True)

async def format_msg(message):
    # Safely get avatar URL
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

    if message.guild is not None:  # Server Messages
        message_json['server'] = [message.guild.name, message.guild.id]
        message_json['to'] = [message.channel.name, message.channel.id]
        message_json['content'] = message.content

        if message.attachments:
            message_json['files'] = [a.url for a in message.attachments]

        if message.reference:  # This message is a reply
            ref = message.reference
            reply_info = {
                'message_id': ref.message_id,
                'user_id': None,
                'content': None
            }

            # Try to get the original message (if cached or fetchable)
            if ref.message_id:
                try:
                    original_msg = await message.channel.fetch_message(ref.message_id)
                    reply_info['user_id'] = original_msg.author.id
                    reply_info['content'] = original_msg.content[:500]  # Limit length
                except Exception:
                    # If fetch fails (e.g. message deleted or no permission), keep what we have
                    pass

            message_json['reply_to'] = reply_info

    else:
        return None  # Skip DMs

    return message_json

async def choose_prev_messages_options():
    window = QWidget()
    window.setWindowTitle("Previous Messages Options")
    window.setFixedSize(420, 220)
    window.setStyleSheet("""
        QWidget {
            background-color: #2b2d31;
            color: #ffffff;
            font-family: 'Segoe UI';
        }
        QLabel {
            font-size: 15px;
            margin-bottom: 8px;
        }
        QCheckBox, QComboBox {
            font-size: 14px;
            padding: 4px;
        }
        QPushButton {
            background-color: #5865F2;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 14px;
        }
        QPushButton:hover { background-color: #4752C4; }
        QPushButton:pressed { background-color: #3C45A5; }
    """)

    layout = QVBoxLayout(window)
    layout.setSpacing(15)

    label = QLabel("Would you like to retrieve previous messages?")
    layout.addWidget(label)

    # Checkbox + Dropdown in one row
    options_layout = QHBoxLayout()
    
    retrieve_checkbox = QCheckBox("Yes, retrieve history")
    retrieve_checkbox.setChecked(False)   # default on
    options_layout.addWidget(retrieve_checkbox)

    days_combo = QComboBox()
    days_combo.addItems(["1 day", "5 days", "15 days", "30 days"])
    days_combo.setCurrentIndex(0)  # default = 1 day
    options_layout.addWidget(days_combo)

    layout.addLayout(options_layout)

    confirm_button = QPushButton("Continue")
    layout.addWidget(confirm_button, alignment=Qt.AlignmentFlag.AlignCenter)

    selected_days = None

    def on_confirm():
        nonlocal selected_days
        if retrieve_checkbox.isChecked():
            # Parse the selected text e.g. "30 days" → 30
            text = days_combo.currentText()
            selected_days = int(text.split()[0])
        else:
            selected_days = 0  # 0 means "do not retrieve"
        window.close()

    confirm_button.clicked.connect(on_confirm)

    window.show()

    while window.isVisible():
        app.processEvents()
        await asyncio.sleep(0.05)

    return selected_days

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
    if message.guild is None or message.guild.id not in servers:
        return

    msg_json = await format_msg(message)
    if msg_json is None:
        return

    async with buffer_lock:
        message_buffer.append(msg_json)

async def get_prev_messages(bot, days):
    if days <= 0:
        return None

    print(f"Fetching messages from the last {days} day(s)... This may take a while.")
    all_msgs = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    for guild in bot.guilds:
        if guild.id not in servers:
            continue
        print(f"Processing guild: {guild.name}")

        for channel in guild.channels:
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                continue

            try:
                print(f"  → Fetching from #{channel.name}")
                async for msg in channel.history(limit=None, after=cutoff, oldest_first=False):
                    formatted = await format_msg(msg)
                    if formatted:
                        all_msgs.append(formatted)

                await asyncio.sleep(0.3)

            except discord.Forbidden:
                print(f"    No permission to read #{channel.name}")
            except discord.HTTPException as e:
                print(f"    HTTP error in #{channel.name}: {e}")
                await asyncio.sleep(1.5)  # Back off a bit
            except Exception as e:
                print(f"    Unexpected error in #{channel.name}: {e}")

    if not all_msgs:
        print("No previous messages found in the selected period.")
        return None

    print(f"Collected {len(all_msgs)} messages. Compressing and sending...")
    compressed = gzip.compress(json.dumps(all_msgs).encode('utf-8'))
    return base64.b64encode(compressed)

async def flush_buffer_loop():
    global message_buffer

    await bot.wait_until_ready()

    while not bot.is_closed():
        await asyncio.sleep(30)

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
            print(f"[ERROR] Failed to send batch: {e}; trying with next batch")
            async with buffer_lock:
                message_buffer = batch + message_buffer

@bot.event
async def on_ready():
    global servers

    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    servers = await choose_servers_gui(bot.guilds)
    if servers == []:
        print('[ERROR] No servers selected, quitting...')
        exit()
    
    days_to_fetch = await choose_prev_messages_options()
    if days_to_fetch and days_to_fetch > 0:
        msgs = await get_prev_messages(bot, days_to_fetch)
        if msgs:
            await send_msg(msgs, content_type='gzip')
            print(f"Successfully sent previous {days_to_fetch} day(s) of messages.")
        else:
            print("No previous messages were sent.")

    bot.loop.create_task(flush_buffer_loop())

if TOKEN == 'YOUR_TOKEN_GOES_HERE':
    print(f'[ERROR] You must first enter your token in the script! Please open the script in a text editor like Visual Studio Code or Notepad and follow the instructions in the New Agent Setup Guide to retrieve your token and then enter it in the token variable.')
    exit()
if AGENT_ID == 'AGENT_ID_GOES_HERE':
    print(f'[ERROR] You must first enter your assigned Agent ID in the script! Please open the script in a text editor like Visual Studio Code or Notepad and enter your Agent ID. If you don\'t have one yet, talk to a Chatty Administrator.')
    exit()
bot.run(TOKEN)