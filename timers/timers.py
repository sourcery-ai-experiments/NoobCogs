import asyncio
import discord
import noobutils as nu
import logging

from redbot.core.bot import commands, Config, Red
from redbot.core.utils import chat_formatting as cf

from datetime import datetime, timezone
from discord.ext import tasks
from typing import Literal, Union

from .views import TimersView


class Timers(commands.Cog):
    """
    Start a timer countdown.

    All purpose timer countdown.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot

        self.config = Config.get_conf(
            self, identifier=65466546, force_registration=True
        )
        default_guild = {
            "timer_button_colour": {"ended": "grey", "started": "green"},
            "notify_members": True,
            "timer_emoji": "⏰",
            "timers": {},
        }
        default_global = {"maximum_duration": 1209600}
        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)
        self.log = logging.getLogger("red.NoobCogs.Timers")

    __version__ = "1.3.5"
    __author__ = ["NoobInDaHause"]
    __docs__ = "https://github.com/NoobInDaHause/NoobCogs/blob/red-3.5/timers/README.md"

    def format_help_for_context(self, context: commands.Context) -> str:
        plural = "s" if len(self.__author__) > 1 else ""
        return (
            f"{super().format_help_for_context(context)}\n\n"
            f"Cog Version: **{self.__version__}**\n"
            f"Cog Author{plural}: {cf.humanize_list([f'**{auth}**' for auth in self.__author__])}\n"
            f"Cog Documentation: [[Click here]]({self.__docs__})"
        )

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        """
        This cog stores user ID's for timer host and users who get notified when timer ends if enabled.

        Users can delete their data at any time.
        """
        for g in (await self.config.all_guilds()).keys():
            async with self.config.guild_from_id(g).timers() as timers:
                guild = self.bot.get_guild(g)
                for tid, value in timers.items():
                    if value["host_id"] == user_id:
                        await self.end_timer(guild, int(tid))
                        continue
                    if user_id in value["members"]:
                        value["members"].remove(user_id)

    async def cog_load(self):
        asyncio.create_task(self.initialize())

    async def initialize(self):
        await self.bot.wait_until_ready()
        for gid, data in (await self.config.all_guilds()).items():
            if guild := self.bot.get_guild(gid):
                if timers := data.get("timers"):
                    for tid, value in timers.items():
                        try:
                            channel = guild.get_channel(value["channel_id"])
                            msg = await channel.fetch_message(int(tid))
                            self.bot.add_view(TimersView(self), message_id=msg.id)
                        except Exception:
                            continue
        self.log.info("Timer ending loop task started.")
        self._timer_end.start()

    async def cog_unload(self):
        for data in (await self.config.all_guilds()).values():
            if timers := data.get("timers"):
                for tid in timers:
                    if view := discord.utils.get(
                        self.bot.persistent_views, _cache_key=int(tid)
                    ):
                        view.stop()
        self.log.info("Timer ending loop task cancelled.")
        self._timer_end.cancel()

    async def end_timer(self, guild: discord.Guild, message_id: int):
        emoji = await self.config.guild(guild).timer_emoji()
        notif = await self.config.guild(guild).notify_members()
        end = await self.config.guild(guild).timer_button_colour.ended()
        async with self.config.guild(guild).timers() as timers:
            try:
                host = guild.get_member(timers[str(message_id)]["host_id"])
                channel = guild.get_channel(timers[str(message_id)]["channel_id"])
                try:
                    msg = await channel.fetch_message(message_id)
                except discord.errors.NotFound:
                    del timers[str(message_id)]
                    return
                members = [host.id] + timers[str(message_id)]["members"]
                view = discord.ui.View().add_item(
                    discord.ui.Button(
                        label=str(len(members) - 1),  # minus host
                        emoji=emoji,
                        disabled=True,
                        style=nu.get_button_colour(end),
                    )
                )
                context = await self.bot.get_context(msg)
                embed = await self.timer_embed_msg(
                    context,
                    host,
                    timers[str(message_id)]["title"],
                    timers[str(message_id)]["end_timestamp"],
                    True,
                    emoji,
                )
                await msg.edit(embed=embed, view=view)
                if notif:
                    c = ",".join(
                        [
                            member.mention
                            for m in members
                            if (member := guild.get_member(m))
                        ]
                    )
                    for page in cf.pagify(c, delims=[","], page_length=1900):
                        await asyncio.sleep(0.5)
                        await channel.send(page, delete_after=3)
                jump_view = discord.ui.View().add_item(
                    discord.ui.Button(label="Jump To Timer", url=msg.jump_url)
                )
                await msg.reply(
                    content=f"The timer for **{timers[str(message_id)]['title']}** has ended!",
                    view=jump_view,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                del timers[str(message_id)]
            except Exception as e:
                self.log.exception(
                    f"Error ending timer with message ID: {message_id}", exc_info=e
                )

    async def timer_embed_msg(
        self,
        context: commands.Context,
        host: discord.Member,
        title: str,
        timestamp: int,
        ended: bool,
        emoji: str,
    ) -> discord.Embed:
        h = host.mention if host else "[Host not found in guild]"
        if ended:
            desc = f"This timer has ended.\nHosted by: {h}"
        else:
            m = (
                f"Click the {emoji} button to get notified when this timer ends.\n"
                if await self.config.guild(context.guild).notify_members()
                else ""
            )
            desc = (
                f"{m}Time left: <t:{timestamp}:R> (<t:{timestamp}:F>)\nHosted by: {h}"
            )
        embed = discord.Embed(
            title=title,
            description=desc,
            colour=0x2F3136 if ended else await context.embed_colour(),
            timestamp=datetime.now(timezone.utc)
            if ended
            else datetime.fromtimestamp(timestamp),
        )
        embed.set_footer(text="Ended at" if ended else "Ends at")
        embed.set_thumbnail(url=nu.is_have_avatar(context.guild))
        return embed

    @tasks.loop(seconds=3)
    async def _timer_end(self):
        for gid, data in (await self.config.all_guilds()).items():
            if guild := self.bot.get_guild(gid):
                if timers := data.get("timers"):
                    for tid, value in timers.items():
                        try:
                            endtime = datetime.fromtimestamp(
                                value["end_timestamp"], timezone.utc
                            )
                            if datetime.now(timezone.utc) > endtime:
                                await self.end_timer(guild, int(tid))
                        except Exception:
                            continue

    @_timer_end.before_loop
    async def _timer_end_before_loop(self):
        await self.bot.wait_until_red_ready()

    @commands.Cog.listener("on_raw_message_delete")
    @commands.Cog.listener("on_raw_bulk_message_delete")
    async def message_delete_handler(
        self,
        payload: Union[
            discord.RawMessageDeleteEvent, discord.RawBulkMessageDeleteEvent
        ],
    ):
        if not payload.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id)

        try:
            if isinstance(payload, discord.RawMessageDeleteEvent):
                msg_ids = [payload.message_id]
            else:
                msg_ids = payload.message_ids

            async with self.config.guild(guild).timers() as timers:
                for msg_id in msg_ids:
                    try:
                        del timers[str(msg_id)]
                    except KeyError:
                        continue
        except Exception as e:
            self.log.exception(
                "Error occurred while handling message delete event.", exc_info=e
            )

    @commands.group(name="timer", invoke_without_command=True)
    @commands.bot_has_permissions(manage_messages=True, embed_links=True)
    @commands.mod()
    @commands.guild_only()
    async def timer(
        self,
        context: commands.Context,
        duration: commands.TimedeltaConverter,
        *,
        title: str = "New Timer!",
    ):
        """
        Timer.
        """
        _max = await self.config.maximum_duration()
        emoji = await self.config.guild(context.guild).timer_emoji()
        notif = await self.config.guild(context.guild).notify_members()
        started = await self.config.guild(context.guild).timer_button_colour.started()
        if int(duration.total_seconds()) > _max:
            return await context.send(
                content=f"Max duration for timers is: **{cf.humanize_timedelta(seconds=_max)}**."
            )
        if int(duration.total_seconds()) < 10:
            return await context.send(
                content="Duration must be greater than **10 Seconds**."
            )
        time = datetime.now(timezone.utc) + duration
        stamp = round(time.timestamp())
        embed = await self.timer_embed_msg(
            context, context.author, title, stamp, False, emoji
        )
        view = TimersView(self)
        view.notify_button.label = "0" if notif else "Disabled"
        view.notify_button.emoji = emoji
        view.notify_button.disabled = not notif
        view.notify_button.style = nu.get_button_colour(started)
        msg = await context.send(embed=embed, view=view)
        await context.message.delete()
        async with self.config.guild(context.guild).timers() as timers:
            timers |= {
                str(msg.id): {
                    "end_timestamp": stamp,
                    "host_id": context.author.id,
                    "channel_id": context.channel.id,
                    "title": title,
                    "members": [],
                }
            }

    @timer.command(name="end")
    async def timer_end(
        self, context: commands.Context, message: discord.Message = None
    ):
        """
        Manually end a timer.
        """
        timers = await self.config.guild(context.guild).timers()
        if not timers:
            return await context.send(
                content="There are no active timers in this guild."
            )
        if not message and not context.message.reference:
            return await context.send_help()
        message = message or context.message.reference.resolved
        try:
            timers[str(message.id)]
            await self.end_timer(context.guild, message.id)
            await context.message.delete()
        except KeyError:
            return await context.send(
                content="That does not seem to be a valid timer or timer already ended or cancelled."
            )

    @timer.command(name="cancel")
    async def timer_cancel(
        self, context: commands.Context, message: discord.Message = None
    ):
        """
        Cancel a timer.
        """
        if not message and not context.message.reference:
            return await context.send_help()
        message = message or context.message.reference.resolved
        emoji = await self.config.guild(context.guild).timer_emoji()
        notif = await self.config.guild(context.guild).notify_members()
        async with self.config.guild(context.guild).timers() as timers:
            if not timers:
                return await context.send(
                    content="There are no active timers in this guild."
                )
            try:
                del timers[str(message.id)]
                await context.message.delete()
                embed = message.embeds[0]
                embed.description = (
                    f"This timer was cancelled.\nCancelled by: {context.author.mention}"
                )
                embed.colour = discord.Colour.red()
                embed.timestamp = datetime.now(timezone.utc)
                embed.set_footer(text="Cancelled at")
                view = discord.ui.View().add_item(
                    discord.ui.Button(
                        emoji=emoji, disabled=True, style=nu.get_button_colour("green")
                    )
                )
                await message.edit(embed=embed, view=view)
            except Exception:
                return await context.send(
                    content="That does not seem to be a valid timer or timer already ended or cancelled."
                )

    @timer.command(name="list")
    async def timer_list(self, context: commands.Context):
        """
        Show running timers from this guild.
        """
        timers = await self.config.guild(context.guild).timers()
        list_timer = []
        for index, (k, v) in enumerate(timers.items(), 1):
            link = (
                f"https://discord.com/channels/{context.guild.id}/{v['channel_id']}/{k}"
            )
            list_timer.append(
                (
                    f"**{index}.** {v['title']}\n"
                    f"` - ` Message ID: {k}\n"
                    f"` - ` Jump URL: [[HERE]]({link})\n"
                    f"` - ` Host: <@{v['host_id']}>\n"
                    f"` - ` Ends: <t:{v['end_timestamp']}:R> (<t:{v['end_timestamp']}:F>)"
                )
            )
        final = "\n".join(list_timer or ["There are no active timers in this guild."])
        pagified = await nu.pagify_this(
            final,
            ")",
            "Page ({index}/{pages})",
            embed_colour=await context.embed_colour(),
            embed_title=f"List of active timers in [{context.guild.name}]",
        )
        await nu.NoobPaginator(pagified).start(context)

    @commands.group(name="timerset")
    @commands.admin_or_permissions(manage_guild=True)
    async def timerset(self, context: commands.Context):
        """
        Configure timer settings.
        """
        pass

    @timerset.command(name="buttoncolour", aliases=["buttoncolor"])
    async def timerset_buttoncolour(
        self,
        context: commands.Context,
        button_type: Literal["ended", "started"],
        colour_type: Literal["green", "grey", "blurple", "red", "reset"] = None,
    ):
        """
        Change the timer ended or started button colour.

        Pass without colour to check current set colour.
        Pass `reset` in colour to reset.
        """
        if button_type == "started":
            if not colour_type:
                col = await self.config.guild(
                    context.guild
                ).timer_button_colour.started()
                return await context.send(
                    content=f"Your current timer started button colour is: {col}"
                )
            if colour_type == "reset":
                await self.config.guild(
                    context.guild
                ).timer_button_colour.started.clear()
                return await context.send(
                    content="The timer started button colour has been reset."
                )
            await self.config.guild(context.guild).timer_button_colour.started.set(
                colour_type
            )
            await context.send(
                content=f"The timer started button colour has been set to: {colour_type}"
            )
        else:
            if not colour_type:
                col = await self.config.guild(context.guild).timer_button_colour.ended()
                return await context.send(
                    content=f"Your current timer ended button colour is: {col}"
                )
            if colour_type == "reset":
                await self.config.guild(context.guild).timer_button_colour.ended.clear()
                return await context.send(
                    content="The timer ended button colour has been reset."
                )
            await self.config.guild(context.guild).timer_button_colour.ended.set(
                colour_type
            )
            await context.send(
                content=f"The timer endeded button colour has been set to: {colour_type}"
            )

    @timerset.command(name="emoji")
    async def timerset_emoji(
        self, context: commands.Context, emoji: nu.NoobEmojiConverter = None
    ):
        """
        Change or reset the timer emoji.
        """
        if not emoji:
            await self.config.guild(context.guild).timer_emoji.clear()
            return await context.send(content="The timer emoji has been reset.")
        await self.config.guild(context.guild).timer_emoji.set(str(emoji))
        await context.send(content=f"Set {str(emoji)} as the timer emoji.")

    @timerset.command(name="notifymembers")
    async def timerset_notifymembers(self, context: commands.Context):
        """
        Toggle whether to notify members when the timer ends or not.
        """
        current = await self.config.guild(context.guild).notify_members()
        await self.config.guild(context.guild).notify_members.set(not current)
        status = "will no longer" if current else "will now"
        await context.send(content=f"I {status} notify members whenever a timer ends.")

    @timerset.command(name="maxduration", aliases=["md"])
    @commands.is_owner()
    async def timerset_maxduration(
        self, context: commands.Context, maxduration: commands.TimedeltaConverter
    ):
        """
        Set the maximum duration a timer can countdown.
        """
        md = int(maxduration.total_seconds())
        if md < 10 or md > (14 * 86400):
            return await context.send(
                content="The max duration time must be greater than 10 seconds or less than 14 days."
            )
        await self.config.maximum_duration.set(md)
        await context.send(
            content=f"The maximum duration is now: **{cf.humanize_timedelta(timedelta=maxduration)}**"
        )

    @timerset.command(name="resetguild")
    async def timerset_resetguild(self, context: commands.Context):
        """
        Reset this guild's timer settings.
        """
        act = "This guilds timer settings has been cleared."
        conf = "Are you sure you want to clear this guilds timer settings?"
        view = nu.NoobConfirmation()
        await view.start(context, act, content=conf)
        await view.wait()
        if view.value:
            await self.config.guild(context.guild).clear()

    @timerset.command(name="resetcog")
    @commands.is_owner()
    async def timerset_resetcog(self, context: commands.Context):
        """
        Reset this cogs whole config.
        """
        act = "This cogs config has been cleared."
        conf = "Are you sure you want to clear this cogs config?"
        view = nu.NoobConfirmation()
        await view.start(context, act, content=conf)
        await view.wait()
        if view.value:
            await self.config.clear_all_guilds()
            await self.config.clear_all()

    @timerset.command(name="showsettings", aliases=["ss"])
    async def timerset_showsettings(self, context: commands.Context):
        """
        Show current timer settings.
        """
        config = await self.config.guild(context.guild).all()
        ended = config["timer_button_colour"]["ended"]
        started = config["timer_button_colour"]["started"]
        md = await self.config.maximum_duration()
        c = (
            f"Max Duration: **{cf.humanize_timedelta(seconds=md)}**"
            if await context.bot.is_owner(context.author)
            else ""
        )
        embed = discord.Embed(
            title=f"Timer settings for [{context.guild.name}]",
            description=f"Notify Members: {config['notify_members']}\n"
            f"Timer Emoji: {config['timer_emoji']}\nTimer Button Colour:\n` - ` Ended: {ended}\n"
            f"` - ` Started: {started}\n{c}",
            timestamp=datetime.now(timezone.utc),
            colour=await context.embed_colour(),
        )
        await context.send(embed=embed)
