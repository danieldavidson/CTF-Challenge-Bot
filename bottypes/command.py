from abc import ABC

from pydantic import BaseModel


class Command(BaseModel, ABC):
    """Defines the command interface."""

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        pass
