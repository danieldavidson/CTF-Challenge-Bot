import time
from typing import Dict

from pydantic import BaseModel

from bottypes.player import Player


class Challenge(BaseModel):
    """
    An object representation of an ongoing challenge.
    """

    MAX_TAGS = 5

    channel_id: str
    ctf_channel_id: str
    name: str
    category: str
    players: Dict[str, Player] = {}
    is_solved = False
    solver = []
    solve_date = 0
    tags = []

    def mark_as_solved(self, solver_list, solve_date=None):
        """
        Mark a challenge as solved.
        solver_list : List of usernames, that solved the challenge.
        solve_date : Time of solve (epoch) (None: current time / value: set to specified value).
        """
        self.is_solved = True
        self.solver = solver_list
        self.solve_date = solve_date or int(time.time())

    def unmark_as_solved(self):
        """
        Unmark a challenge as solved.
        """
        self.is_solved = False
        self.solver = []

    def add_tag(self, tag):
        """
        Update the list of tags for this challenge by adding the given tag.
        Return True if a modification was made, False otherwise.
        """
        dirty = False
        if tag not in self.tags and len(self.tags) < self.MAX_TAGS:
            # The tag doesn't exist and there's room to add it, let's do so
            self.tags.append(tag)
            dirty = True
        return dirty

    def remove_tag(self, tag):
        """
        Update the list of tags for this challenge by removing the given tag.
        Return True if a modification was made, False otherwise.
        """
        dirty = False
        if tag in self.tags:
            # The tag exists, let's remove it
            self.tags.remove(tag)
            dirty = True
        return dirty

    def add_player(self, player):
        """
        Add a player to the list of working players.
        """
        self.players[player.user_id] = player

    def remove_player(self, user_id):
        """
        Remove a player from the list of working players using a given slack
        user ID.
        """
        try:
            del self.players[user_id]
        except KeyError:
            # TODO: Should we allow this to percolate up to the caller?
            pass
