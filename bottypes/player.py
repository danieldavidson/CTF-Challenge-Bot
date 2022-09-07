from pydantic import BaseModel


class Player(BaseModel):
    """
    An object representation of a CTF player.
    """

    user_id: str
