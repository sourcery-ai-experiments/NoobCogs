import asyncio
import discord
import noobutils as nu
import random

from redbot.core.bot import commands, Red
from redbot.core.utils import chat_formatting as cf, mod

from typing import Literal, TYPE_CHECKING, Union

from .checks import (
    check_if_is_a_dono_manager_or_higher,
    check_if_setup_done,
    has_dono_permissions,
)
from .views import DonationLoggerSetupView, TotalDonoView

if TYPE_CHECKING:
    from . import DonationLogger


class HYBRIDS:
    @staticmethod
    async def hybrid_send(
        obj: Union[commands.Context, discord.Interaction[Red]], **payload
    ) -> discord.Message:
        if isinstance(obj, commands.Context):
            return await obj.send(
                content=payload.get("content"),
                embed=payload.get("embed"),
                allowed_mentions=payload.get("allowed_mentions"),
            )
        elif obj.response.is_done():
            return await obj.followup.send(
                content=payload.get("content"),
                embed=payload.get("embed"),
                allowed_mentions=payload.get("allowed_mentions"),
                ephemeral=payload.get("ephemeral"),
            )
        else:
            return await obj.response.send_message(
                content=payload.get("content"),
                embed=payload.get("embed"),
                allowed_mentions=payload.get("allowed_mentions"),
                ephemeral=payload.get("ephemeral"),
            )

    @classmethod
    async def hybrid_setup(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
    ):
        if isinstance(obj, discord.Interaction):
            if not obj.channel.permissions_for(obj.guild.me).embed_links:
                return await cls.hybrid_send(
                    obj,
                    content='I require the "Embed Links" permission to run this command.',
                    ephemeral=True,
                )
            if not has_dono_permissions(
                obj, manage_guild=True
            ) and not await mod.is_mod_or_superior(obj.client, obj.user):
                return await cls.hybrid_send(
                    obj,
                    content="You need to be a guild admin or a guild manager + to run this command.",
                    ephemeral=True,
                )
        if await cog.config.guild(obj.guild).setup():
            content = (
                "It appears this guild is already set up, "
                "you can run this command again when you reset this guild."
            )
            return await cls.hybrid_send(obj, content=content, ephemeral=True)
        conf = (
            "You are about to set up DonationLogger system in your server.\n"
            "Click Yes to continue or No to abort."
        )
        act = "Alright sending set up interactions, please wait..."
        view = nu.NoobConfirmation()
        await view.start(obj, act, content=conf)
        await view.wait()
        await asyncio.sleep(3)
        if view.value:
            if obj.guild.id in cog.setupcache:
                return await cls.hybrid_send(
                    obj, content="Only one setup interaction per guild."
                )
            cog.setupcache.append(obj.guild.id)
            ctx = (
                obj
                if isinstance(obj, commands.Context)
                else await obj.client.get_context(obj)
            )
            await DonationLoggerSetupView(cog).start(ctx)

    @classmethod
    async def hybrid_resetuser(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
        user: Union[discord.User, discord.Member],
        bank_name: str = None,
    ):
        if isinstance(obj, discord.Interaction):
            if not obj.channel.permissions_for(obj.guild.me).embed_links:
                return await cls.hybrid_send(
                    obj,
                    content='I require the "Embed Links" permission to run this command.',
                    ephemeral=True,
                )
            if not await check_if_setup_done(obj):
                return await cls.hybrid_send(
                    obj,
                    content="DonationLogger has not been setup in this guild yet.",
                    ephemeral=True,
                )
            if not await check_if_is_a_dono_manager_or_higher(obj):
                return await cls.hybrid_send(
                    obj,
                    content="You need to be a donationlogger manager or higher to run this command.",
                    ephemeral=True,
                )
        if not bank_name:
            act = f"Successfully cleared all bank donations from **{user.name}**."
            conf = f"Are you sure you want to erase all bank donations from **{user.name}**?"
            view = nu.NoobConfirmation()
            await view.start(obj, act, content=conf)
            await view.wait()
            if view.value:
                async with cog.config.guild(obj.guild).banks() as banks:
                    for bank in banks.values():
                        donos = bank["donators"].get(str(user.id))
                        if donos is not None:
                            del bank["donators"][str(user.id)]
            return
        act = f"Successfully cleared **{bank_name.title()}** donations from **{user.name}**."
        conf = f"Are you sure you want to clear **{bank_name.title()}** donations from **{user.name}**"
        view = nu.NoobConfirmation()
        await view.start(obj, act, content=conf)
        await view.wait()
        if view.value:
            async with cog.config.guild(obj.guild).banks() as banks:
                donations = banks[bank_name.lower()]["donators"].get(str(user.id))
                if donations is not None:
                    del banks[bank_name.lower()]["donators"][str(user.id)]

    @classmethod
    async def hybrid_balance(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
        member: discord.Member,
        bank_name: str = None,
    ):
        if (
            isinstance(obj, discord.Interaction)
            and not obj.channel.permissions_for(obj.guild.me).embed_links
        ):
            return await cls.hybrid_send(
                obj,
                content='I require the "Embed Links" permission to run this command.',
                ephemeral=True,
            )
        if bank_name:
            async with cog.config.guild(obj.guild).banks() as banks:
                bank = banks[bank_name.lower()]
                if bank["hidden"]:
                    return await cls.hybrid_send(obj, content="This bank is hidden")
                donations = bank["donators"].get(str(member.id), 0)
                embed = discord.Embed(
                    title=f"{member.name} ({member.id})",
                    description=(
                        f"Bank: {bank_name.title()}\n"
                        f"Total amount donated: {bank['emoji']} {cf.humanize_number(donations)}"
                    ),
                    timestamp=discord.utils.utcnow(),
                    colour=member.colour,
                )
                embed.set_thumbnail(url=nu.is_have_avatar(member))
                embed.set_footer(
                    text=f"{obj.guild.name} admires your donations!",
                    icon_url=nu.is_have_avatar(obj.guild),
                )
                return await cls.hybrid_send(obj, embed=embed)
        embed = await cog.get_all_bank_member_dono(obj.guild, member)
        await cls.hybrid_send(obj, embed=embed)

    @classmethod
    async def hybrid_donationcheck(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
        bank_name: str,
        mla: Literal["more", "less", "all"],
        amount: int = None,
    ):
        if (
            isinstance(obj, discord.Interaction)
            and not obj.channel.permissions_for(obj.guild.me).embed_links
        ):
            return await cls.hybrid_send(
                obj,
                content='I require the "Embed Links" permission to run this command.',
                ephemeral=True,
            )
        if isinstance(obj, commands.Context):
            ctx: commands.Context = obj
        else:
            ctx: commands.Context = await obj.client.get_context(obj)
        if mla == "all":
            embeds = await cog.get_dc_from_bank(ctx, bank_name)
            if not embeds:
                return await cls.hybrid_send(obj, content="This bank is hidden.")
            await nu.NoobPaginator(embeds).start(obj)
            return

        if not amount:
            return await ctx.send_help()

        banks_config = await cog.config.guild(obj.guild).banks()
        bank_data = banks_config.get(bank_name.lower(), {})
        if bank_data.get("hidden"):
            return await cls.hybrid_send(obj, content="This bank is hidden.")

        donators = bank_data.get("donators", {})
        filtered_donators = {
            k: v
            for k, v in donators.items()
            if (mla == "more" and v >= amount) or (mla == "less" and v < amount)
        }

        sorted_donators = sorted(
            filtered_donators.items(), key=lambda u: u[1], reverse=(mla == "more")
        )

        output_list = []
        for index, (donator_id, donation_amount) in enumerate(sorted_donators, 1):
            member = obj.guild.get_member(int(donator_id))
            mention = (
                f"{member.mention} (`{member.id}`)"
                if member
                else f"Member not found in server. (`{donator_id}`)"
            )
            e = (
                "➡️ "
                if member and member.id == (getattr(obj, "user", obj.author)).id
                else ""
            )
            output_list.append(
                f"{e}{index}. {mention}: **{cf.humanize_number(donation_amount)}**"
            )

        output_text = "\n".join(
            output_list
            or [f"No one has donated {mla} than **{cf.humanize_number(amount)}** yet."]
        )

        paginated_output = await nu.pagify_this(
            output_text,
            "\n",
            "Page ({index}/{pages})",
            embed_title=f"All members who have donated {mla} than {cf.humanize_number(amount)} "
            f"for [{bank_name.title()}]",
            embed_colour=await ctx.embed_colour(),
        )

        await nu.NoobPaginator(paginated_output).start(obj)

    @classmethod
    async def hybrid_leaderboard(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
        bank_name: str,
        top: int,
        show_left_users: bool,
    ):
        if (
            isinstance(obj, discord.Interaction)
            and not obj.channel.permissions_for(obj.guild.me).embed_links
        ):
            return await cls.hybrid_send(
                obj,
                content='I require the "Embed Links" permission to run this command.',
                ephemeral=True,
            )
        banks = await cog.config.guild(obj.guild).banks()
        if banks[bank_name.lower()]["hidden"]:
            return await cls.hybrid_send(obj, content="This bank is hidden.")
        donors = banks[bank_name.lower()]["donators"]
        emoji = banks[bank_name.lower()]["emoji"]
        filtered_donors = {}
        for i, j in donors.items():
            if j <= 0:
                continue
            memb = obj.guild.get_member(int(i))
            if not memb and not show_left_users:
                continue
            member = memb.name if memb else f"[Member not found in guild] ({i})"
            filtered_donors[member] = j

        sorted_donors = dict(
            sorted(filtered_donors.items(), key=lambda m: m[1], reverse=True)
        )
        embed = discord.Embed(
            title=f"Top {top} donators for [{bank_name.title()}]",
            colour=random.randint(0, 0xFFFFFF),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=obj.guild.name)
        embed.set_thumbnail(url=nu.is_have_avatar(obj.guild))
        if not sorted_donors:
            embed.description = "It seems no one has donated from this bank yet."
        for index, (k, v) in enumerate(sorted_donors.items(), 1):
            if index > top:
                break
            embed.add_field(
                name=f"{index}. {k}",
                value=f"{emoji} {cf.humanize_number(v)}",
                inline=False,
            )
        await cls.hybrid_send(obj, embed=embed)

    @classmethod
    async def hybrid_add(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
        bank_name: str,
        amount: int,
        member: discord.Member,
        note: str = None,
    ):
        if isinstance(obj, discord.Interaction):
            if not obj.channel.permissions_for(obj.guild.me).embed_links:
                return await cls.hybrid_send(
                    obj,
                    content='I require the "Embed Links" permission to run this command.',
                    ephemeral=True,
                )
            if not await check_if_setup_done(obj):
                return await cls.hybrid_send(
                    obj,
                    content="DonationLogger has not been setup in this guild yet.",
                    ephemeral=True,
                )
            if not await check_if_is_a_dono_manager_or_higher(obj):
                return await cls.hybrid_send(
                    obj,
                    content="You need to be a donationlogger manager or higher to run this command.",
                    ephemeral=True,
                )
        if isinstance(obj, commands.Context):
            ctx = obj
        else:
            ctx = await obj.client.get_context(obj)
        async with cog.config.guild(obj.guild).banks() as banks:
            bank = banks[bank_name.lower()]
            emoji = bank["emoji"]
            if bank["hidden"]:
                return await cls.hybrid_send(obj, content="This bank is hidden.")
            multi = bank.get("multi")
            if multi:
                amount = round(amount * multi)
            if amount > 999999999999999:
                return await cls.hybrid_send(
                    obj,
                    ephemeral=True,
                    content="The amount you provided is way too high, consider adding something reasonable.",
                )
            bank["donators"].setdefault(str(member.id), 0)
            bank["donators"][str(member.id)] += amount
            updated = bank["donators"][str(member.id)]
            previous = updated - amount
            donated = cf.humanize_number(amount)
            total = cf.humanize_number(updated)
            roles = await cog.update_dono_roles(
                ctx, "add", updated, member, bank["roles"]
            )
            humanized_roles = cf.humanize_list([role.mention for role in roles])
            rep = (
                f"{emoji} **{donated}** was added to **{member.name}**'s **__{bank_name.title()}__** "
                f"donation balance.\nTheir total donation balance is now **{emoji} {total}** on "
                f"**__{bank_name.title()}__**."
            )
            embed = discord.Embed(
                title="Successfully Added",
                description=rep,
                colour=member.colour,
                timestamp=discord.utils.utcnow(),
            )
            if multi:
                embed.set_footer(text=f"Donation Multiplier: x{multi}")
            if humanized_roles:
                embed.add_field(
                    name="Added Donation Roles:", value=humanized_roles, inline=False
                )
            await TotalDonoView(cog).start(
                ctx, member, content=member.mention, embed=embed
            )
            await cog.send_to_log_channel(
                ctx,
                "add",
                bank_name,
                emoji,
                amount,
                previous,
                updated,
                member,
                humanized_roles,
                note,
            )

    @classmethod
    async def hybrid_remove(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
        bank_name: str,
        amount: int,
        member: discord.Member,
        note: str = None,
    ):
        if isinstance(obj, discord.Interaction):
            if not obj.channel.permissions_for(obj.guild.me).embed_links:
                return await cls.hybrid_send(
                    obj,
                    content='I require the "Embed Links" permission to run this command.',
                    ephemeral=True,
                )
            if not await check_if_setup_done(obj):
                return await cls.hybrid_send(
                    obj,
                    content="DonationLogger has not been setup in this guild yet.",
                    ephemeral=True,
                )
            if not await check_if_is_a_dono_manager_or_higher(obj):
                return await cls.hybrid_send(
                    obj,
                    content="You need to be a donationlogger manager or higher to run this command.",
                    ephemeral=True,
                )
        if isinstance(obj, commands.Context):
            ctx: commands.Context = obj
        else:
            ctx: commands.Context = await obj.client.get_context(obj)
        async with cog.config.guild(obj.guild).banks() as banks:
            bank = banks[bank_name.lower()]
            donators = bank["donators"]
            emoji = bank["emoji"]
            member_id = str(member.id)
            if bank["hidden"]:
                return await cls.hybrid_send(obj, content="This bank is hidden.")
            d = donators.get(member_id)
            if d == 0 or d is None:
                return await cls.hybrid_send(
                    obj, content="This member has 0 donation balance for this bank."
                )
            donators[member_id] -= amount
            updated1 = donators[member_id]
            if updated1 < 0:
                del donators[member_id]
            updated2 = donators.get(member_id, 0)
            previous = updated1 + amount
            donated = cf.humanize_number(amount)
            total = cf.humanize_number(updated2)
            roles = await cog.update_dono_roles(
                ctx, "remove", updated2, member, bank["roles"]
            )
            humanized_roles = cf.humanize_list([role.mention for role in roles])
            rep = (
                f"{emoji} **{donated}** was removed from **{member.name}**'s **__{bank_name.title()}__** "
                f"donation balance.\nTheir total donation balance is now **{emoji} {total}** on "
                f"**__{bank_name.title()}__**."
            )
            embed = discord.Embed(
                title="Successfully Removed",
                description=rep,
                colour=member.colour,
                timestamp=discord.utils.utcnow(),
            )
            if humanized_roles:
                embed.add_field(
                    name="Removed Donation Roles:", value=humanized_roles, inline=False
                )
            await TotalDonoView(cog).start(
                ctx, member, content=member.mention, embed=embed
            )
            await cog.send_to_log_channel(
                ctx,
                "remove",
                bank_name,
                emoji,
                amount,
                previous,
                updated2,
                member,
                humanized_roles,
                note,
            )

    @classmethod
    async def hybrid_set(
        cls,
        cog: "DonationLogger",
        obj: Union[commands.Context, discord.Interaction[Red]],
        bank_name: str,
        amount: int,
        member: discord.Member,
        note: str = None,
    ):
        if isinstance(obj, discord.Interaction):
            if not obj.channel.permissions_for(obj.guild.me).embed_links:
                return await cls.hybrid_send(
                    obj,
                    content='I require the "Embed Links" permission to run this command.',
                    ephemeral=True,
                )
            if not await check_if_setup_done(obj):
                return await cls.hybrid_send(
                    obj,
                    content="DonationLogger has not been setup in this guild yet.",
                    ephemeral=True,
                )
            if not await check_if_is_a_dono_manager_or_higher(obj):
                return await cls.hybrid_send(
                    obj,
                    content="You need to be a donationlogger manager or higher to run this command.",
                    ephemeral=True,
                )
        if isinstance(obj, commands.Context):
            ctx: commands.Context = obj
        else:
            ctx: commands.Context = await obj.client.get_context(obj)
        async with cog.config.guild(obj.guild).banks() as banks:
            bank = banks[bank_name.lower()]
            donators = bank["donators"]
            emoji = bank["emoji"]
            if bank["hidden"]:
                return await cls.hybrid_send(obj, content="This bank is hidden.")
            donators.setdefault(str(member.id), 0)
            previous = donators[str(member.id)]
            donators[str(member.id)] = amount
            aroles = await cog.update_dono_roles(
                ctx, "add", amount, member, bank["roles"]
            )
            rrole = await cog.update_dono_roles(
                ctx, "remove", amount, member, bank["roles"]
            )
            roles = aroles + rrole
            humanized_roles = cf.humanize_list([role.mention for role in roles])
            rep = (
                f"{emoji} **{cf.humanize_number(amount)}** was set as **{member.name}**'s "
                f"**__{bank_name.title()}__** donation balance."
            )
            embed = discord.Embed(
                title="Successfully Set",
                description=rep,
                colour=member.colour,
                timestamp=discord.utils.utcnow(),
            )
            if humanized_roles:
                embed.add_field(
                    name="Added/Removed Donation Roles:",
                    value=humanized_roles,
                    inline=False,
                )
            await TotalDonoView(cog).start(
                ctx, member, content=member.mention, embed=embed
            )
            await cog.send_to_log_channel(
                ctx,
                "set",
                bank_name,
                emoji,
                amount,
                previous,
                amount,
                member,
                humanized_roles,
                note,
            )
