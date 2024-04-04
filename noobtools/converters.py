import discord
import noobutils as nu

from redbot.core.bot import commands

from typing import Union


class ModifiedFuzzyRole(nu.NoobFuzzyRole):
    def __init__(self, role: discord.Role):
        super().__init__(role=role)

    @classmethod
    async def convert(
        cls, ctx: commands.Context, argument: str
    ) -> Union[discord.Role, str]:
        arg = argument.lower().strip()
        if arg in {"@here", "here", "@everyone", "everyone"}:
            return arg.replace("@", "")
        role = await super().convert(ctx, argument)
        return cls(role=role)
