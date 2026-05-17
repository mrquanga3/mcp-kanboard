from __future__ import annotations


class KanboardError(Exception):
    pass


class AuthError(KanboardError):
    pass


class NotFoundError(KanboardError):
    pass


class ConfirmRequiredError(KanboardError):
    pass
