import os

import discord

import random

import asyncio

import time

from collections import deque

from dotenv import load_dotenv



load_dotenv()



# --- CONFIGURATION ---

# Random line from phrases.txt when @mentioned; per-guild cooldown between such replies.

DEFAULT_MENTION_COOLDOWN_SECONDS = 60

# Optional overrides: {guild_id: seconds}

PER_GUILD_MENTION_COOLDOWN = {}



# Channel IDs used for greetings and farewells (main + test server). Guild is detected at startup.

GREET_FAREWELL_CHANNEL_IDS = (

    315482478527643650,

    1482573126385795113,

)



# Per file: avoid reusing the same line within this many picks from that file.

AVOID_REPEAT_LAST_N = 10



_recent_phrases = deque(maxlen=AVOID_REPEAT_LAST_N)

_recent_greetings = deque(maxlen=AVOID_REPEAT_LAST_N)

_recent_farewells = deque(maxlen=AVOID_REPEAT_LAST_N)



last_mention_response_by_guild: dict[int, float] = {}

_greet_farewell_channel_by_guild: dict[int, discord.TextChannel] = {}



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

intents.members = True

client = discord.Client(intents=intents)





def mention_cooldown_seconds(guild_id: int) -> int:

    return PER_GUILD_MENTION_COOLDOWN.get(guild_id, DEFAULT_MENTION_COOLDOWN_SECONDS)





def get_phrase_from_file(filename: str, recent: deque) -> str:

    try:

        with open(filename, "r", encoding="utf-8") as f:

            lines = [line.strip() for line in f if line.strip()]

        if not lines:

            return "My ledgers are empty!"

        banned = set(recent)

        candidates = [line for line in lines if line not in banned]

        if not candidates:

            candidates = lines

        choice = random.choice(candidates)

        recent.append(choice)

        return choice

    except Exception as e:

        return f"Inventory error: {e}"





@client.event

async def on_ready():

    print("Salmoneus is online.")

    print("Control Console: DM the bot !sal_say [channel_id] [message]")



    _greet_farewell_channel_by_guild.clear()

    for cid in GREET_FAREWELL_CHANNEL_IDS:

        try:

            ch = await client.fetch_channel(cid)

            if isinstance(ch, discord.TextChannel) and ch.guild:

                _greet_farewell_channel_by_guild[ch.guild.id] = ch

                print(f"Greet/farewell: guild \"{ch.guild.name}\" -> #{ch.name} ({ch.id})")

            else:

                print(f"Greet/farewell: channel {cid} is not a server text channel.")

        except Exception as e:

            print(f"Greet/farewell: could not load channel {cid}: {e}")





@client.event

async def on_member_join(member: discord.Member):

    if member.bot:

        return

    channel = _greet_farewell_channel_by_guild.get(member.guild.id)

    if not channel:

        return

    try:

        text = get_phrase_from_file("greeting.txt", _recent_greetings)

        text = text.replace("{user}", member.mention)

        await channel.send(text)

    except Exception as e:

        print(f"greeting send failed: {e}")





@client.event

async def on_member_remove(member: discord.Member):

    if member.bot:

        return

    channel = _greet_farewell_channel_by_guild.get(member.guild.id)

    if not channel:

        return

    try:

        text = get_phrase_from_file("farewell.txt", _recent_farewells)

        text = text.replace("{user}", member.mention)

        await channel.send(text)

    except Exception as e:

        print(f"farewell send failed: {e}")





@client.event

async def on_message(message: discord.Message):

    if message.author == client.user:

        return



    content = message.content



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



    # --- @mention replies (phrases.txt only) ---

    if not message.guild:

        return

    if not client.user.mentioned_in(message):

        return



    guild_id = message.guild.id

    now = time.time()

    cooldown = mention_cooldown_seconds(guild_id)

    last = last_mention_response_by_guild.get(guild_id, 0.0)

    if now - last < cooldown:

        return



    response = get_phrase_from_file("phrases.txt", _recent_phrases)

    async with message.channel.typing():

        wait_time = min((len(response) * 0.05) + 0.5, 4)

        await asyncio.sleep(wait_time)

        await message.reply(response, mention_author=False)

    last_mention_response_by_guild[guild_id] = time.time()





token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

if not token:

    raise SystemExit(

        "Missing DISCORD_BOT_TOKEN. Add it to a .env file (see .env.example) or your environment."

    )

client.run(token)

