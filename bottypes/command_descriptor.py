from typing import Type

from pydantic import BaseModel

from bottypes.command import Command


class CommandDesc(BaseModel):
    command: Type[Command]
    description: str
    arguments = []
    opt_arguments = []
    is_admin_cmd = False
