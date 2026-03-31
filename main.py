import os
import discord
import random
import asyncio
import time
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
INTERJECTION_CHANCE = 1.0 
COOLDOWN_SECONDS = 0
last_response_time = 0 

# Explicit list of authorized User IDs
ADMIN_USER_IDS = [
    399728552871723008,  # You
    534199350880895019,   # Rolf
    807506325973368832,   # Heb0
    423539861148925954   # B0b2oo0
]
# ---------------------w

intents = discord.Intents.default()
intents.message_content = True 
client = discord.Client(intents=intents)

def get_phrase_from_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            return random.choice(lines) if lines else "My ledgers are empty!"
    except Exception as e:
        return f"Inventory error: {e}"

@client.event
async def on_ready():
    print(f'Salmoneus is online.')
    print(f'Control Console: DM the bot !sal_say [channel_id] [message]')

@client.event
async def on_message(message):
    global last_response_time

    if message.author == client.user:
        return

    content = message.content
    content_lower = content.lower()

    # --- PRIVATE DM CONSOLE (HARDCODED AUTH) ---
    if isinstance(message.channel, discord.DMChannel):
        if content.startswith("!sal_say"):
            if message.author.id in ADMIN_USER_IDS:
                try:
                    parts = content.split(" ", 2)
                    if len(parts) < 3:
                        return await message.author.send("Format: `!sal_say [channel_id] [message]`")

                    target_channel_id = int(parts[1])
                    secret_message = parts[2]
                    
                    target_channel = await client.fetch_channel(target_channel_id)

                    if target_channel:
                        async with target_channel.typing():
                            wait_time = min((len(secret_message) * 0.05) + 0.5, 4)
                            await asyncio.sleep(wait_time)
                            await target_channel.send(secret_message)
                        
                        await message.author.send(f"✅ Message sent to #{target_channel.name}")
                    else:
                        await message.author.send("❌ Invalid Channel ID.")
                except Exception as e:
                    await message.author.send(f"⚠️ Error: {e}")
            else:
                await message.author.send("❌ Access Denied. Your ID is not on the ledger.")
            return 

    # --- PUBLIC SERVER LOGIC ---
    if message.guild:
        current_time = time.time()
        
        mk_triggers = ["mage kid", "magekid", "mk"]
        crypto_triggers = ["crypto", "bitcoin", "money", "business", "profit", "coin"]
        
        has_mk_keyword = any(trigger in content_lower for trigger in mk_triggers)
        has_crypto_keyword = any(trigger in content_lower for trigger in crypto_triggers)
        is_mentioned = client.user.mentioned_in(message)

        is_ready = (current_time - last_response_time) > COOLDOWN_SECONDS
        should_respond = is_mentioned or (is_ready and (has_mk_keyword or has_crypto_keyword) and random.random() < INTERJECTION_CHANCE)

        if should_respond:
            last_response_time = current_time 
            
            if has_mk_keyword:
                response = "Mage Kid is so evil."
            elif has_crypto_keyword:
                response = get_phrase_from_file("crypto_scams.txt")
            else:
                response = get_phrase_from_file("phrases.txt")

            async with message.channel.typing():
                wait_time = min((len(response) * 0.05) + 0.5, 4)
                await asyncio.sleep(wait_time)
                
                # --- THE REPLY LOGIC ---
                # message.reply automatically threads the response to the user's triggering text.
                # mention_author=False ensures the user does not receive a push notification.
                await message.reply(response, mention_author=False)

token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
if not token:
    raise SystemExit(
        "Missing DISCORD_BOT_TOKEN. Add it to a .env file (see .env.example) or your environment."
    )
client.run(token)
