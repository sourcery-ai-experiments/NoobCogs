import discord
import noobutils as nu

from redbot.core.bot import app_commands, commands, Red

from typing import Literal


DEFAULT_GUILD = {"nick": True}
DEFAULT_MEMBER = {
    "afk": False,
    "sticky": False,
    "toggle_logs": True,
    "reason": None,
    "timestamp": None,
    "pinglogs": [],
}
DEFAULT_GLOBAL = {"delete_after": 10}


class Afk(nu.Cog):
    """
    Notify users whenever you go AFK with pings logging.

    Be afk and notify users who ping you with a reason of your choice.
    """

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(
            bot=bot,
            cog_name=self.__class__.__name__,
            version="1.6.1",
            authors=["NoobInDaHause"],
            use_config=True,
            identifier=54646544526864548,
            force_registration=True,
            *args,
            **kwargs,
        )
        self.config.register_guild(**DEFAULT_GUILD)
        self.config.register_member(**DEFAULT_MEMBER)
        self.config.register_global(**DEFAULT_GLOBAL)

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        """
        This cog stores data provided by users for the express purpose of
        notifying users whenever they go AFK and only for that reason.
        It does not store user data which was not provided through a command.
        Users may remove their own content without making a data removal request.
        This cog does not support data requests, but will respect deletion requests.

        Also thanks sravan and aikaterna for the end user data statement!
        """
        for g in (await self.config.all_guilds()).keys():
            if guild := self.bot.get_guild(g):
                guild_data = await self.config.all_members(guild)
                if user_id in guild_data.keys():
                    await self.config.member_from_ids(guild.id, user_id).clear()
                async with self.config.member_from_ids(
                    guild.id, user_id
                ).pinglogs() as pl:
                    if not pl:
                        continue
                    for i in pl:
                        if i["pinger_id"] == user_id:
                            i["pinger_id"] = None

    async def start_afk(
        self, message: discord.Message, user: discord.Member, reason: str
    ):
        """
        Start AFK status.
        """
        await self.config.member(user).afk.set(True)
        await self.config.member(user).timestamp.set(
            round(discord.utils.utcnow().timestamp())
        )
        await self.config.member(user).reason.set(reason)
        channel = message.channel
        guild = message.guild

        if await self.config.guild(guild).nick():
            try:
                await user.edit(
                    nick=f"[AFK] {user.display_name}", reason="Member is AFK."
                )
            except discord.errors.Forbidden:
                if user.id == guild.owner.id:
                    await channel.send(
                        content="Could not change your nick cause you are the guild owner.",
                        delete_after=10,
                    )
                    return
                await channel.send(
                    content="Could not change your nick due to role hierarchy or "
                    "I'm missing the manage nicknames permission.",
                    delete_after=10,
                )
            except discord.errors.HTTPException:
                await channel.send(
                    content="It seems your nick name is too long for me to add '[AFK]' beside it."
                )

    async def end_afk(self, message: discord.Message, user: discord.Member):
        """
        End AFK status.
        """
        await message.channel.send(
            content=f"Welcome back {user.name}! I have removed your AFK status."
        )
        await self.config.member(user).afk.set(False)
        await self.config.member(user).timestamp.clear()
        await self.config.member(user).reason.clear()
        channel = message.channel
        guild = message.guild

        if await self.config.guild(guild).nick():
            try:
                await user.edit(
                    nick=f"{user.display_name}".replace("[AFK]", ""),
                    reason="Member is no longer AFK.",
                )
            except discord.errors.Forbidden:
                if user.id == guild.owner.id:
                    await channel.send(
                        content="Could not change your nick cause you are the guild owner.",
                        delete_after=10,
                    )
                    return
                await channel.send(
                    content="Could not change your nick due to role hierarchy or "
                    "I'm missing the manage nicknames permission.",
                    delete_after=10,
                )
            except discord.errors.HTTPException:
                await channel.send(
                    content="It seems your nick name is too long for me to add '[AFK]' beside it."
                )

        if pings := await self.config.member(user).pinglogs():
            final_log = []
            for i in pings:
                try:
                    member = await self.bot.get_or_fetch_user(i["pinger_id"])
                    m = member.mention
                except (discord.errors.NotFound, discord.errors.HTTPException):
                    m = "||Unknown or Deleted User||"
                logs = (
                    f"` #{len(final_log) + 1} ` {m} [pinged you in]({i['jump_url']}) <#{i['channel_id']}>"
                    f" <t:{i['timestamp']}:R>.\n**Message:** {i['message']}"
                )
                final_log.append(logs)

            pinglist = "\n".join(final_log)
            final_page = await nu.pagify_this(
                pinglist,
                "` - `",
                "Page {index}/{pages}",
                embed_title=f"You have recieved some pings while you were AFK, {user.display_name}.",
                embed_colour=user.colour,
                footer_icon=nu.is_have_avatar(user),
            )
            context = await self.bot.get_context(message)
            await self.config.member(user).pinglogs.clear()
            await nu.NoobPaginator(final_page, timeout=60.0).start(context)

    async def maybe_log_and_notify(
        self, message: discord.Message, afk_user: discord.Member
    ):
        """
        Log pings and at the same time notify members when they mentioned an AFK memebr.
        """
        if await self.config.member(afk_user).toggle_logs():
            async with self.config.member(afk_user).pinglogs() as ping_logs:
                pl: list = ping_logs
                dict_log = {
                    "pinger_id": message.author.id,
                    "jump_url": message.jump_url,
                    "channel_id": message.channel.id,
                    "timestamp": round(discord.utils.utcnow().timestamp()),
                    "message": message.content,
                }
                pl.append(dict_log)

        afk_reason = await self.config.member(afk_user).reason()
        timestamp = await self.config.member(afk_user).timestamp()
        embed = discord.Embed(
            description=f"{afk_user.mention} is currently AFK since <t:{timestamp}:R>.\n\n"
            f"**Reason:**\n{afk_reason}",
            colour=afk_user.colour,
        ).set_thumbnail(url=nu.is_have_avatar(afk_user))

        da = await self.config.delete_after()

        return (
            await message.channel.send(
                embed=embed, reference=message, mention_author=False, delete_after=da
            )
            if da != 0
            else await message.channel.send(
                embed=embed, reference=message, mention_author=False
            )
        )

    @commands.Cog.listener("on_member_remove")
    async def m_remove(self, member: discord.Member):
        guild_data = await self.config.all_members(member.guild)
        if (
            member.id in guild_data.keys()
            and await self.config.member_from_ids(member.guild.id, member.id).afk()
        ):
            await self.config.member_from_ids(member.guild.id, member.id).afk.clear()
            await self.config.member_from_ids(
                member.guild.id, member.id
            ).timestamp.clear()
            await self.config.member_from_ids(member.guild.id, member.id).reason.clear()
            await self.config.member_from_ids(
                member.guild.id, member.id
            ).pinglogs.clear()

    @commands.Cog.listener("on_message")
    async def afk_listener(self, message: discord.Message):
        context: commands.Context = await self.bot.get_context(message)
        tuple_cmds = (f"{context.prefix}afk", f"{context.prefix}away")
        if not message.guild:
            return
        if message.is_system():
            return
        if not message.channel.permissions_for(message.guild.me).send_messages:
            return
        if message.author.bot:
            return
        if await self.bot.cog_disabled_in_guild(cog=self, guild=message.guild):
            return
        if message.mentions:
            for afk_user in message.mentions:
                if (
                    afk_user != message.author
                    and await self.config.member(afk_user).afk()
                ):
                    await self.maybe_log_and_notify(message=message, afk_user=afk_user)
        if message.content.startswith(tuple_cmds):
            return
        if await self.config.member(message.author).sticky():
            return
        if await self.config.member(message.author).afk():
            await self.end_afk(message=message, user=message.author)

    @commands.hybrid_command(name="afk", aliases=["away"])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.bot_has_permissions(embed_links=True, manage_nicknames=True)
    @app_commands.guild_only()
    @app_commands.describe(reason="The optional reason for the AFK.")
    async def afk(self, context: commands.Context, *, reason: str = "No reason given."):
        """
        Be afk and notify users whenever they ping you.

        The reason is optional.
        """
        if await self.config.member(context.author).afk():
            return await context.send(content="It appears you are already AFK.")

        await context.send(
            content="You are now AFK. Any member that pings you will now get notified."
        )
        await self.start_afk(
            message=context.message, user=context.author, reason=reason
        )

    @commands.group(name="afkset", aliases=["awayset"])
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def afkset(self, context: commands.Context):
        """
        Settings for the AFK cog.
        """
        pass

    @afkset.command(name="deleteafter", aliases=["da"])
    @commands.is_owner()
    async def afkset_deleteafter(self, context: commands.Context, seconds: int = None):
        """
        Change the delete after on every AFK notify.

        Leave `seconds` blank to disable.
        Default is 10 seconds.
        """
        if not seconds:
            await self.config.delete_after.set(0)
            return await context.send(content="The delete after has been disabled.")

        if seconds < 0:
            return await context.send(
                content="You can not set the delete after lower than 0."
            )
        if seconds > 120:
            return await context.send(
                content="The maximum seconds of delete after is 120 seconds."
            )

        await self.config.delete_after.set(seconds)
        await context.send(
            content=f"Successfully set the delete after to {seconds} seconds."
        )

    @afkset.command(name="forceafk", aliases=["forceaway"])
    @commands.admin_or_permissions(manage_guild=True)
    async def afkset_forceafk(
        self,
        context: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason given.",
    ):
        """
        Forcefully add or remove an AFK status on a user.
        """
        if member.bot:
            return await context.send(content="I'm afraid you can not do that to bots.")
        if member == context.guild.owner:
            return await context.send(
                content="I'm afraid you can not do that to the guild owner."
            )
        if member == context.author:
            return await context.send(
                content=f"Why would you force AFK yourself? Please use `{context.prefix}afk`."
            )
        if (
            member.top_role >= context.author.top_role
            and context.author != context.guild.owner
        ):
            return await context.send(
                content="I'm afraid you can not do that due to role hierarchy."
            )

        if await self.config.member(member).afk():
            await context.send(content=f"Forcefully removed **{member}**'s AFK status.")
            return await self.end_afk(message=context.message, user=member)

        await context.send(content=f"Forcefully added **{member}**'s AFK status.")
        await self.start_afk(message=context.message, user=member, reason=reason)

    @afkset.command(name="members")
    @commands.admin_or_permissions(manage_guild=True)
    async def afkset_members(self, context: commands.Context):
        """
        Check who are all the afk members in your guild.
        """
        members = await self.config.all_members(guild=context.guild)

        afk_list = [
            f"<@{member_id}> (`{member_id}`) AFK since **<t:{member_data['timestamp']}:R>**."
            for member_id, member_data in members.items()
            if member_data["afk"]
        ]

        if not afk_list:
            return await context.send(content="No members are AFK in this guild.")

        afk_users = "\n".join(afk_list)
        final_page = await nu.pagify_this(
            afk_users,
            "\n",
            "Page {index}/{pages}",
            embed_title="Here are the members who are afk in this guild.",
            embed_colour=await context.embed_colour(),
            footer_icon=nu.is_have_avatar(context.guild),
        )
        await nu.NoobPaginator(final_page, timeout=60.0).start(context)

    @afkset.command(name="nick")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def afkset_nick(self, context: commands.Context):
        """
        Toggle whether to change the users nick with ***[AFK] {user_display_name}*** or not.

        This defaults to `True`.
        """
        current = await self.config.guild(context.guild).nick()
        await self.config.guild(context.guild).nick.set(not current)
        status = "will not" if current else "will now"
        await context.send(
            content=f"I {status} edit the users nick whenever they go AFK."
        )

    @afkset.command(name="reset")
    async def afkset_reset(self, context: commands.Context):
        """
        Reset your AFK settings to default.
        """
        confirm_msg = "Are you sure you want to reset your AFK settings?"
        confirm_action = "Successfully resetted your AFK settings."
        view = nu.NoobConfirmation(timeout=30)
        await view.start(
            object=context, confirm_action=confirm_action, content=confirm_msg
        )

        await view.wait()

        if view.value:
            await self.config.member(context.author).clear()

    @afkset.command(name="resetcog")
    @commands.is_owner()
    async def afkset_resetcog(self, context: commands.Context):
        """
        Reset the AFK cogs configuration. (Bot owners only.)
        """
        confirm_msg = "Are you sure you want to reset the AFK cogs whole configuration?"
        confirm_action = "Successfully resetted the AFK cogs configuration."
        view = nu.NoobConfirmation(timeout=30)
        await view.start(
            object=context, confirm_action=confirm_action, content=confirm_msg
        )

        await view.wait()

        if view.value:
            await self.config.clear_all()
            await self.config.clear_all_guilds()
            await self.config.clear_all_members()

    @afkset.command(name="showsettings", aliases=["ss"])
    async def afkset_showsettings(self, context: commands.Context):
        """
        See your AFK settings.

        Guild settings show up when you have manage_guild permission.
        """
        member_settings = await self.config.member(context.author).all()
        guild_settings = await self.config.guild(context.guild).all()
        delete_after = await self.config.delete_after()
        da = f"{delete_after} seconds." if delete_after != 0 else "Disabled."
        aset = f"`Nick change:` {guild_settings['nick']}"
        globe = f"`Delete after:` {da}"

        embed = discord.Embed(
            title=f"{context.author.name}'s AFK settings.",
            description=f"`Is afk:` {member_settings['afk']}\n`Is sticky:` {member_settings['sticky']}\n"
            f"`Ping logging:` {member_settings['toggle_logs']}",
            colour=context.author.colour,
            timestamp=discord.utils.utcnow(),
        )

        if (
            await context.bot.is_owner(context.author)
            or context.author.guild_permissions.manage_guild
        ):
            embed.add_field(name="Guild settings:", value=aset, inline=False)
        if await context.bot.is_owner(context.author):
            embed.add_field(name="Delete After:", value=globe, inline=False)
        await context.send(embed=embed)

    @afkset.command(name="sticky")
    async def afkset_sticky(self, context: commands.Context):
        """
        Toggle whether to sticky your afk or not.

        This defaults to `False`.
        """
        current = await self.config.member(context.author).sticky()
        await self.config.member(context.author).sticky.set(not current)
        status = "will not" if current else "will now"
        await context.send(content=f"I {status} sticky your AFK.")

    @afkset.command(name="togglelogs", aliases=["tl"])
    async def afkset_togglelogs(self, context: commands.Context):
        """
        Toggle whether to log all pings you recieved or not.
        """
        current = await self.config.member(context.author).toggle_logs()
        await self.config.member(context.author).toggle_logs.set(not current)
        status = "will not" if current else "will now"
        await context.send(content=f"I {status} log all the pings you recieved.")
