class EmptyAPIResponseError(Exception):
    pass


class TokenNotFoundError(Exception):
    pass


class APIResponseError(Exception):
    pass


class FailedToSendMessageError(Exception):
    pass
