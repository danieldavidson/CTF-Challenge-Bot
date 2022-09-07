from typing import Type

from pydantic import BaseModel

from bottypes.command import Command


class ReactionDesc(BaseModel):
    command: Type[Command]
