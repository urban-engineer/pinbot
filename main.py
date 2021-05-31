import discord
import discord.ext.commands
import pathlib
import sqlite3
import uuid

from utils import config
from utils import log


BOT = discord.ext.commands.Bot(command_prefix='!')
DATABASE_CONNECTION = sqlite3.connect("pinbot.db")


def check_reaction(reaction):
    log.debug("{}: {}".format(reaction, type(reaction)))
    return str(reaction.emoji) == "📌"


@BOT.event
async def on_ready():
    log.debug("Logged in as: [{}] [{}]".format(BOT.user.name, BOT.user.id))


@BOT.event
async def on_reaction_add(reaction: discord.reaction.Reaction, user: discord.member.Member):
    # log.debug("{}: {}".format(reaction, type(reaction)))
    # log.debug("{}: {}".format(reaction.message.content, type(reaction.message)))
    # log.debug("{}: {}".format(user, type(user)))

    # We don't care about reaction that aren't :pushpin:
    if str(reaction) == "📌":
        # We don't care about reactions sent in channels that aren't registered source channels
        select_command = "SELECT * FROM channel_connections WHERE source_channel=?"
        cursor = DATABASE_CONNECTION.cursor()
        channel_connections = list(cursor.execute(select_command, (str(reaction.message.channel.id),)))
        if len(channel_connections) == 0:
            log.warning("Channel [{}] has no pin connections".format(reaction.message.channel.name))
            return

        # Author's choice: either embed something (links, usually) or attach it.  Not both.
        if len(reaction.message.attachments) > 0 and len(reaction.message.embeds) > 0:
            log.warning("Will not pin something with attachments _and_ embeds, separate them.")
            return

        if len(reaction.message.attachments) == 0 and len(reaction.message.embeds) == 0:
            log.warning("Cannot pin message without media to pin.")
            return

        # For every pin channel the source channel is connected to, post the attachments/embeds
        pin_channel_ids = [x[2] for x in channel_connections]
        for channel_id in pin_channel_ids:
            log.debug("Pinning [{}] to channel [{}]".format(reaction.message.id, channel_id))
            channel = BOT.get_channel(int(channel_id))
            if len(reaction.message.attachments) > 0:
                files = []
                for attachment in reaction.message.attachments:
                    filename = attachment.filename
                    await attachment.save(filename)
                    files.append(discord.File(filename))
                await channel.send("Pinned by [{}]".format(user.display_name), files=files)
                for file in files:
                    pathlib.Path(file.filename).unlink()
            elif len(reaction.message.embeds) > 0:
                for embed in reaction.message.embeds:
                    await channel.send("Pinned by [{}]".format(user.display_name), embed=embed)


@BOT.command()
async def register_source_channel(ctx: discord.ext.commands.context.Context):
    # Create UUID for this channel connection
    channel_connection_uuid = str(uuid.uuid4())
    source_channel_id = ctx.message.channel.id

    log.debug("Logging connection for `{}` with key `{}`".format(source_channel_id, channel_connection_uuid))

    # Create DB entry
    #   channel_key = generated uuid
    #   source_channel = ctx.message.channel.id
    #   pin_channel = null
    db_entry_command = "INSERT INTO channel_connections(channel_key,source_channel,pin_channel) VALUES(?,?,NULL)"
    cursor = DATABASE_CONNECTION.cursor()
    cursor.execute(db_entry_command, (channel_connection_uuid, source_channel_id))

    # 'Done'
    DATABASE_CONNECTION.commit()
    log.debug("Added record to DB: [{} | {} | {}]".format(channel_connection_uuid, source_channel_id, "NULL"))
    await ctx.message.author.send("Register pin channel with `!register_pin_channel {}`".format(channel_connection_uuid))


@BOT.command()
async def register_pin_channel(ctx: discord.ext.commands.context.Context, channel_connection_key: str):
    # if uuid exists in channel_connections & can post in pin channel:
    #   update DB record with pin channel id
    cursor = DATABASE_CONNECTION.cursor()

    select_command = "SELECT * FROM channel_connections WHERE channel_key=? AND pin_channel IS ?"
    channel_connections = list(cursor.execute(select_command, (channel_connection_key, None)))

    if len(channel_connections) == 0:
        await ctx.send("No pending channel registrations with key `{}`".format(channel_connection_key))
        return
    elif len(channel_connections) > 1:
        raise RuntimeError(
            "Returned [{}] connections for UUID [{}]".format(len(channel_connections), channel_connection_key)
        )

    pending_connection = channel_connections[0]
    source_channel_id = int(pending_connection[1])
    pin_channel_id = int(ctx.message.channel.id)
    source_channel = BOT.get_channel(source_channel_id)
    log.debug("Setting up connection from [{}] to [{}]".format(source_channel_id, pin_channel_id))

    # Developer choice - you can't pin messages to the same chat, because _why_ would you?
    if source_channel_id == ctx.message.channel.id:
        await ctx.send("Will not pin messages to the same chat")
        return

    update_command = '''UPDATE channel_connections 
                        SET channel_key=?, source_channel=?, pin_channel=?
                        WHERE channel_key=?'''
    cursor.execute(
        update_command,
        (str(channel_connection_key), str(source_channel_id), str(ctx.message.channel.id), str(channel_connection_key))
    )

    # 'Done'
    DATABASE_CONNECTION.commit()
    await ctx.send("Registered pinning `{}` -> `{}`".format(source_channel.name, ctx.message.channel.name))


if __name__ == '__main__':
    database_cursor = DATABASE_CONNECTION.cursor()
    database_cursor.execute(
        '''CREATE TABLE IF NOT EXISTS channel_connections (channel_key text, source_channel text, pin_channel text)'''
    )
    DATABASE_CONNECTION.commit()

    BOT.run(config.load_discord_token())

