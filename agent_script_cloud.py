########### EDIT THIS SECTION ############
TOKEN = 'YOUR_TOKEN_GOES_HERE'
AGENT_ID = 'AGENT_ID_GOES_HERE'
SERVER_IDS = [12345678901234567890, 12345678901234567890]
##########################################

#########################################
#           DO NOT EDIT BELOW!          #
#########################################

# Import/install necessary packages
import sys
import gzip
import base64
import subprocess
import json
import asyncio
import urllib.request
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
    if message.guild is None or message.guild.id not in SERVER_IDS:
        return

    msg_json = await format_msg(message)
    if msg_json is None:
        return

    async with buffer_lock:
        message_buffer.append(msg_json)

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
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    bot.loop.create_task(flush_buffer_loop())

if TOKEN == 'YOUR_TOKEN_GOES_HERE':
    print(f'[ERROR] You must first enter your token in the script! Please open the script in a text editor like Visual Studio Code or Notepad and follow the instructions in the New Agent Setup Guide to retrieve your token and then enter it in the token variable.')
    exit()
if AGENT_ID == 'AGENT_ID_GOES_HERE':
    print(f'[ERROR] You must first enter your assigned Agent ID in the script! Please open the script in a text editor like Visual Studio Code or Notepad and enter your Agent ID. If you don\'t have one yet, talk to a Chatty Administrator.')
    exit()
bot.run(TOKEN)