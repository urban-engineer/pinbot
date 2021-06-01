import discord
import discord.ext.commands
import sqlite3
import uuid

from utils import config
from utils import log


BOT = discord.ext.commands.Bot(command_prefix='!')
DATABASE_CONNECTION = sqlite3.connect("pinbot.db")

# TODO: Support pinning messages from a public channel to user DMs.


def delete_record(channel_connection_key: str) -> None:
    """
    Given a channel connection key (a uuid4), check if it exists and delete it from the DB

    :param channel_connection_key: the uuid4 used to register channels
    :return: None
    """
    log.debug("Checking if [{}] exists in DB".format(channel_connection_key))
    with DATABASE_CONNECTION:
        select_command = "SELECT * FROM channel_connections WHERE channel_key=?"
        pending_connection = DATABASE_CONNECTION.execute(select_command, (channel_connection_key, )).fetchone()
        if pending_connection:
            log.debug(
                "Deleting record [{} | {} | {} | {}] from the DB".format(
                    pending_connection[0], pending_connection[1], pending_connection[2], pending_connection[3]
                )
            )
            delete_command = "DELETE FROM channel_connections WHERE channel_key=?"
            DATABASE_CONNECTION.execute(delete_command, (channel_connection_key,))
        else:
            log.warning("Key [{}] does not exist in DB".format(channel_connection_key))


@BOT.event
async def on_reaction_add(reaction: discord.reaction.Reaction, user: discord.member.Member) -> None:
    """
    Pinning function, called whenever PinBot can see a reaction added.  Checks if the reaction emoji is 📌 and the
    channel it's in has pin connection.  If so, repost the reacted message's attachments/embeds to the connected
    pin channels.

    :param reaction: The reaction action, used to get the message to post.
    :param user: The user that pinned the post.
    :return: None
    """
    post_to_pin = reaction.message
    source_channel = post_to_pin.channel
    log.debug("Saw user [{}] react to [{}] in [{}]".format(user.display_name, post_to_pin.id, source_channel.id))


    # We don't care about reaction that aren't :pushpin:
    if str(reaction) == "📌":
        # We don't care about reactions sent in channels that aren't registered source channels
        log.debug("Searching DB for records where source channel is [{}]".format(source_channel.id))
        with DATABASE_CONNECTION:
            select_command = "SELECT * FROM channel_connections WHERE source_channel=?"
            channel_connections = DATABASE_CONNECTION.execute(select_command, (source_channel.id,)).fetchall()

        if len(channel_connections) == 0:
            log.warning("Channel [{}] has no pin connections".format(post_to_pin.channel.name))
            return
        else:
            log.debug(
                "Got [{}] connections for source channel [{}]".format(len(channel_connections), source_channel.id)
            )

        if len(post_to_pin.attachments) == 0 and len(post_to_pin.embeds) == 0:
            message = "Cannot pin message without media to pin."
            log.warning(message)
            await user.send(message)
            return

        # Author's choice: either embed something (links, usually) or attach it.  Not both.
        if len(post_to_pin.attachments) > 0 and len(post_to_pin.embeds) > 0:
            message = "Will not pin something with attachments and embeds, separate them."
            log.warning(message)
            await user.send(message)
            return

        # For every pin channel the source channel is connected to, post the attachments/embeds
        # set/listing it to guarantee only unique places get posted to.
        pin_channel_ids = list(set([x[2] for x in channel_connections]))
        for channel_id in pin_channel_ids:
            log.debug("Pinning [{}] to [{}]".format(post_to_pin.id, channel_id))
            channel = await BOT.fetch_channel(channel_id)
            if len(post_to_pin.attachments) > 0:
                files = []
                for attachment in post_to_pin.attachments:
                    files.append(await attachment.to_file())
                await channel.send("Pinned by `{}`".format(user.display_name), files=files)
            elif len(post_to_pin.embeds) > 0:
                for embed in post_to_pin.embeds:
                    # TODO: if it's a tweet, check how many images there are, so mobile users know.
                    await channel.send("Pinned by `{}`".format(user.display_name), embed=embed)
            log.debug("Pinned [{}] to [{}]".format(post_to_pin.id, channel_id))


@BOT.command()
async def register_source_channel(ctx: discord.ext.commands.context.Context) -> None:
    """
    The !register_source_channel command function.  Will create a pending record in the DB where pin_channel is NULL.
    DMs the registering user with the command to register a pin channel.

    :param ctx: discord context when someone calls !register_source_channel
    :return: None
    """
    source_channel: discord.TextChannel = ctx.message.channel
    registering_user: discord.User = ctx.message.author

    if type(source_channel) == discord.DMChannel:
        log.warning("User [{}] tried to register DMs as a source channel".format(registering_user.id))
        await registering_user.send("You cannot make your DMs with PinBot a source for other channels.")
        return

    log.debug(
        "User [{}] ([{}]) began registering channel [{}] ([{}])".format(
            registering_user.display_name, registering_user.id, source_channel, source_channel.id
        )
    )

    # If they already have a pending connection to this channel, give that key to them instead of making a new one.
    with DATABASE_CONNECTION:
        select_command = """
            SELECT * FROM channel_connections 
            WHERE source_channel=? and pin_channel IS NULL and registering_user=?
        """
        pending_connections = DATABASE_CONNECTION.execute(select_command, (source_channel.id, registering_user.id))
        pending_connections = pending_connections.fetchall()
        if len(pending_connections) > 0:
            log.debug(
                "User [{}] already has pending connection, sending them key [{}] again".format(
                    registering_user.id, pending_connections[0][0]
                )
            )
            await registering_user.send(
                "Register pin channel with `!register_pin_channel {}`".format(pending_connections[0][0])
            )
            return

    # Create UUID for this channel connection
    channel_connection_key = str(uuid.uuid4())
    log.debug("Logging connection for [{}] with key [{}]".format(source_channel.id, channel_connection_key))

    # Create DB entry
    with DATABASE_CONNECTION:
        db_entry_command = """
            INSERT INTO channel_connections(channel_key,source_channel,pin_channel,registering_user) 
            VALUES(?,?,NULL,?)
        """
        DATABASE_CONNECTION.execute(db_entry_command, (channel_connection_key, source_channel.id, registering_user.id))
    log.debug("Added record to DB: [{} | {} | {}]".format(channel_connection_key, source_channel.id, "NULL"))

    # Done - send the user a DM with the registration command
    await registering_user.send("Register pin channel with `!register_pin_channel {}`".format(channel_connection_key))


@BOT.command()
async def register_pin_channel(ctx: discord.ext.commands.context.Context, channel_connection_key: str) -> None:
    """
    The !register_pin_channel command function.  Must be supplied with the connection key.
    Will register the channel the command was posted in as a channel to post 'pinned' messages.

    Updates the record with the channel_connection_key so the pin_channel value is the ID of the message's channel.

    If the connection has already been registered, it will delete the pending registration.  I'm open to leaving
    pending records in the DB, theoretically, but I think it's cleaner to just remove them for now.

    :param ctx: discord context when someone calls !register_pin_channel <key>
    :param channel_connection_key: <key>, the channel_key PinBot generated for this connection
    :return: None
    """
    registering_user: discord.User = ctx.message.author
    pin_channel: discord.TextChannel = ctx.message.channel

    if type(pin_channel) == discord.DMChannel:
        log.warning("User [{}] tried to register DMs as a pin channel, not supported.".format(registering_user.id))
        await registering_user.send("Sending pins as DMs not supported at this time, deleting pending key.")
        delete_record(channel_connection_key)
        return

    bot_member = await pin_channel.guild.fetch_member(BOT.user.id)
    if not pin_channel.permissions_for(bot_member).send_messages:
        log.warning("Cannot send messages to [{}], will not pin.")
        await registering_user.send("Cannot send messages in `{}`, deleting pending key.".format(pin_channel.name))
        delete_record(channel_connection_key)
        return

    log.debug(
        "Attempting to register channel [{}] ([{}]) by [{}] ([{}])".format(
            pin_channel.name, pin_channel.id, registering_user.display_name, registering_user.id
        )
    )

    with DATABASE_CONNECTION:
        select_command = "SELECT * FROM channel_connections WHERE channel_key=?"
        # Since channel_key is UNIQUE on the table, we know this will always return None, or the pending record.
        pending_connection = DATABASE_CONNECTION.execute(select_command, (channel_connection_key, )).fetchone()
        if not pending_connection:
            log.warning(
                "User [{}] ([{}]) tried connecting with nonexistent key [{}]".format(
                    ctx.message.author.display_name, ctx.message.author.id, channel_connection_key
                )
            )
            await ctx.send("No pending channel registrations with key `{}`".format(channel_connection_key))
            return

        # Make sure the user the ran the command is the user that ran the first command.
        original_registering_user: discord.User = await BOT.fetch_user(pending_connection[3])
        log.debug("{}: {}".format(pending_connection[3], type(pending_connection[3])))
        if original_registering_user.id != registering_user.id:
            log.warning(
                "User [{}] ([{}]) tried registering key made by User [{}] ([{}])".format(
                    registering_user.display_name, registering_user.id, original_registering_user.display_name,
                    original_registering_user.id
                )
            )
            await ctx.send("Cannot use another user's key, please run `!register_source_channel` yourself.")
            return

        # Pending record exists, the user is the same, let's see if a completed source -> pin record exists.
        source_channel: discord.TextChannel = BOT.get_channel(pending_connection[1])
        select_command = "SELECT * FROM channel_connections WHERE source_channel=? and pin_channel=?"
        source_connections = DATABASE_CONNECTION.execute(select_command, (source_channel.id, pin_channel.id)).fetchall()

        # If the record exists, let the user know and delete pending record.
        # It's probably not great from a UX perspective, but it keeps the DB clean.
        # And since I am a dunce, keeping the DB clean is paramount.
        if source_connections:
            log.warning(
                "User [{}] ([{}]) tried registering [{}] which has already been registered with key [{}]".format(
                    registering_user.display_name, registering_user.id, pin_channel.id, source_connections[0][0]
                )
            )
            await ctx.send(
                "`{}` -> `{}` already registered, will not register twice.  Deleting key `{}`".format(
                    source_channel.name, pin_channel.name, channel_connection_key
                )
            )
            delete_record(channel_connection_key)

        # Theoretically, that should always return 0 or 1 records.  But just in case, let's check that too
        if len(source_connections) > 1:
            log.error(
                "[{}] -> [{}] connection registered [{}] times, investigation required!".format(
                    source_channel.id, pin_channel.id, len(source_connections)
                )
            )
            # TODO: figure out how to handle this case.

    if source_channel.is_nsfw() and not pin_channel.is_nsfw():
        log.error("Will not pin possibly NSFW messages to non-NSFW channel, deleting pending record")
        await ctx.send(
            "Detected `{}` as NSFW and `{}` as SFW, will not pin NSFW content to SFW channel, deleting key `{}`".format(
                source_channel.name, pin_channel.name, channel_connection_key
            )
        )
        delete_record(channel_connection_key)

    # Developer choice - you can't pin messages to the same chat, because _why_ would you?
    if source_channel.id == pin_channel.id:
        await ctx.send("Will not pin messages to the same chat; deleting pending key.")
        delete_record(channel_connection_key)
        return

        # So by this point, we've verified:
        #  * The pending record for the key exists
        #  * The user registering is the user the initially requested it
        #  * No one has registered this source channel -> pin channel connection yet
        #  * The pin channel isn't the same as the source channel
        #  * The both channels as NSFW, SFW, or the source channel is SFW and the pin channel is NSFW
        # That means we're good to go to register it.

    log.debug("Setting up connection from [{}] to [{}]".format(source_channel.id, pin_channel.id))
    with DATABASE_CONNECTION:
        update_command = "UPDATE channel_connections SET pin_channel=? WHERE channel_key=?"
        DATABASE_CONNECTION.execute(update_command, (pin_channel.id, channel_connection_key))
        log.debug(
            "Updated record in DB: [{} | {} | {}]".format(channel_connection_key, source_channel.id, pin_channel.id)
        )

    # Done
    await ctx.send("Registered pinning from `{}` to `{}`".format(source_channel.name, pin_channel.name))


if __name__ == '__main__':
    log.info("Starting PinBot.  Initializing database")
    with DATABASE_CONNECTION:
        table_creation_command = """
            CREATE TABLE IF NOT EXISTS channel_connections (
                channel_key text UNIQUE,
                source_channel INTEGER,
                pin_channel INTEGER,
                registering_user INTEGER 
            )
        """
        DATABASE_CONNECTION.execute(table_creation_command)

    # TODO: figure out if sqlite can table-ly stop a source channel from being equal to a pin channel.
    # TODO: figure out if sqlite can table-ly stop multiple of the same source/pin channel records.

    log.info("Database initialized, running bot")

    BOT.run(config.load_discord_token())
