import discord
import noobutils as nu

from redbot.core.bot import commands

from typing import Union


class ModifiedFuzzyRole(nu.NoobFuzzyRole):
    async def convert(
        self, ctx: commands.Context, argument: str
    ) -> Union[discord.Role, str]:
        arg = argument.lower().strip()
        if arg in {"@here", "here", "@everyone", "everyone"}:
            return arg.replace("@", "")
        else:
            return await super().convert(ctx, argument)
