from typing import Type, List

from pydantic import BaseModel

from bottypes.command import Command


class CommandDesc(BaseModel):
    command: Type[Command]
    description: str
    arguments: List[str] = []
    opt_arguments: List[str] = []
    is_admin_cmd = False
