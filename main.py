import logging

import os

import re

import discord

import random

import asyncio

import time

from collections import deque

from pathlib import Path

from dotenv import load_dotenv



_DATA_DIR = Path(__file__).resolve().parent

load_dotenv(_DATA_DIR / ".env")


def _configure_app_logging() -> logging.Logger:
    log = logging.getLogger("salmoneus")
    if log.handlers:
        return log
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log


log = _configure_app_logging()


def _member_label(member: discord.Member) -> str:
    return f"{member.id} ({member})"


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("Invalid %s value %r, using default %s.", name, raw, default)
        return default



# --- CONFIGURATION ---
NEW_MEMBER_ROLE_ID = _get_env_int("NEW_MEMBER_ROLE_ID", 315490765226639361)

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

        with open(_DATA_DIR / filename, "r", encoding="utf-8") as f:

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


# First http(s) URL in farewell.txt splits the template: text before, GIF embed, text after.

_FAREWELL_URL_RE = re.compile(r"https?://[^\s]+")

# Strip one layer of matching outer quotes (ASCII or common Unicode) from a segment.

_FAREWELL_QUOTE_PAIRS = (
    ('"', '"'),
    ("\u201c", "\u201d"),
    ("\u2018", "\u2019"),
    ("'", "'"),
)


def _strip_outer_quotes(s: str) -> str:

    s = s.strip()

    for open_q, close_q in _FAREWELL_QUOTE_PAIRS:

        if s.startswith(open_q) and s.endswith(close_q) and len(s) >= 2:

            return s[len(open_q) : -len(close_q)].strip()

    return s


async def send_farewell(channel: discord.TextChannel, member: discord.Member) -> None:

    with open(_DATA_DIR / "farewell.txt", "r", encoding="utf-8") as f:

        raw = f.read().strip()

    if not raw:

        log.info(
            "Farewell skipped (empty farewell.txt): member %s guild %s (%s)",
            _member_label(member),
            member.guild.id,
            member.guild.name,
        )
        return

    mention = member.mention

    m = _FAREWELL_URL_RE.search(raw)

    if not m:

        await channel.send(raw.replace("{user}", mention))

        log.info(
            "Farewell sent: member %s -> #%s (%s) in guild %s (%s)",
            _member_label(member),
            channel.name,
            channel.id,
            member.guild.name,
            member.guild.id,
        )
        return

    before = _strip_outer_quotes(raw[: m.start()].strip())

    url = m.group(0)

    after = _strip_outer_quotes(raw[m.end() :].strip())

    before = before.replace("{user}", mention)

    after = after.replace("{user}", mention)

    if before:

        await channel.send(before)

    await channel.send(url)

    if after:

        await channel.send(f"*{after}*")

    log.info(
        "Farewell sent (multi-part): member %s -> #%s (%s) in guild %s (%s)",
        _member_label(member),
        channel.name,
        channel.id,
        member.guild.name,
        member.guild.id,
    )





@client.event

async def on_ready():

    log.info("Salmoneus is online.")

    log.info("Control Console: DM the bot !sal_say [channel_id] [message]")



    _greet_farewell_channel_by_guild.clear()

    for cid in GREET_FAREWELL_CHANNEL_IDS:

        try:

            ch = await client.fetch_channel(cid)

            if isinstance(ch, discord.TextChannel) and ch.guild:

                _greet_farewell_channel_by_guild[ch.guild.id] = ch

                log.info('Greet/farewell: guild "%s" -> #%s (%s)', ch.guild.name, ch.name, ch.id)

            else:

                log.warning("Greet/farewell: channel %s is not a server text channel.", cid)

        except Exception as e:

            log.warning("Greet/farewell: could not load channel %s: %s", cid, e)





@client.event

async def on_member_join(member: discord.Member):

    if member.bot:

        return

    log.info(
        "Member joined: %s in guild %s (%s)",
        _member_label(member),
        member.guild.name,
        member.guild.id,
    )

    try:
        role = member.guild.get_role(NEW_MEMBER_ROLE_ID)
        if role is None:
            log.warning(
                "Role assignment skipped: role %s not found in guild %s (%s)",
                NEW_MEMBER_ROLE_ID,
                member.guild.id,
                member.guild.name,
            )
        else:
            await member.add_roles(role, reason="Auto-assign default Salmon role to new member")
            log.info(
                "Assigned role %s (%s) to %s",
                role.name,
                role.id,
                _member_label(member),
            )
    except Exception as e:
        log.error("Role assignment failed: %s", e)

    channel = _greet_farewell_channel_by_guild.get(member.guild.id)

    if not channel:

        log.info(
            "Greeting skipped (no greet/farewell channel for this guild): %s (%s)",
            member.guild.name,
            member.guild.id,
        )
        return

    try:

        text = get_phrase_from_file("greeting.txt", _recent_greetings)

        text = text.replace("{user}", member.mention)

        await channel.send(text)

        log.info(
            "Greeting sent: member %s -> #%s (%s)",
            _member_label(member),
            channel.name,
            channel.id,
        )

    except Exception as e:

        log.error("Greeting send failed: %s", e)





@client.event

async def on_member_remove(member: discord.Member):

    if member.bot:

        return

    log.info(
        "Member left: %s from guild %s (%s)",
        _member_label(member),
        member.guild.name,
        member.guild.id,
    )

    channel = _greet_farewell_channel_by_guild.get(member.guild.id)

    if not channel:

        log.info(
            "Farewell skipped (no greet/farewell channel for this guild): %s (%s)",
            member.guild.name,
            member.guild.id,
        )
        return

    try:

        await send_farewell(channel, member)

    except Exception as e:

        log.error("Farewell send failed: %s", e)





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

                        log.warning(
                            "!sal_say rejected (bad format) from admin %s",
                            message.author.id,
                        )
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

                        preview = secret_message if len(secret_message) <= 120 else secret_message[:117] + "..."
                        if isinstance(target_channel, discord.TextChannel) and target_channel.guild:
                            log.info(
                                "!sal_say sent by admin %s -> #%s (%s) guild %s (%s) len=%s preview=%r",
                                message.author.id,
                                target_channel.name,
                                target_channel.id,
                                target_channel.guild.name,
                                target_channel.guild.id,
                                len(secret_message),
                                preview,
                            )
                        else:
                            log.info(
                                "!sal_say sent by admin %s -> channel %s len=%s preview=%r",
                                message.author.id,
                                getattr(target_channel, "id", target_channel_id),
                                len(secret_message),
                                preview,
                            )
                    else:

                        log.warning("!sal_say failed: invalid channel id %s", target_channel_id)
                        await message.author.send("❌ Invalid Channel ID.")

                except Exception as e:

                    log.exception("!sal_say error: %s", e)
                    await message.author.send(f"⚠️ Error: {e}")

            else:

                log.warning("!sal_say denied (not admin): user %s", message.author.id)
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

    preview = response if len(response) <= 100 else response[:97] + "..."
    log.info(
        "Mention reply sent: author %s (%s) in #%s (%s) guild %s (%s) len=%s preview=%r",
        message.author.id,
        message.author,
        message.channel.name,
        message.channel.id,
        message.guild.name,
        guild_id,
        len(response),
        preview,
    )





token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

if not token:

    raise SystemExit(

        "Missing DISCORD_BOT_TOKEN. Add it to a .env file (see .env.example) or your environment."

    )

client.run(token)

