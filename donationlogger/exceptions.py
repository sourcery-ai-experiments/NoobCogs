from redbot.core.commands import BadArgument


class AmountConversionFailure(BadArgument):
    pass


class MemberOrUserNotFound(BadArgument):
    pass


class MoreThanThreeRoles(BadArgument):
    pass


class BankConversionFailure(BadArgument):
    pass
