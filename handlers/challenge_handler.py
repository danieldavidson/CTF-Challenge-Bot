import json
import re
import time
from random import randint

from dateutil.relativedelta import relativedelta
from slack_sdk.errors import SlackApiError

from bottypes.challenge import Challenge
from bottypes.command import Command
from bottypes.command_descriptor import CommandDesc
from bottypes.ctf import CTF
from bottypes.invalid_command import InvalidCommand
from bottypes.player import Player
from bottypes.reaction_descriptor import ReactionDesc
from handlers import handler_factory
from handlers.base_handler import BaseHandler
from util.loghandler import log
from util.storage_service import StorageService
from util.util import (
    get_display_name,
    is_valid_name,
    get_display_name_from_user,
    transliterate,
    resolve_user_by_user_id,
    cleanup_reminders,
    load_json,
)


class SignupCommand(Command):
    """
    Invite the user into the specified CTF channel along with any existing challenge channels.
    """

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        enabled = handler_factory.botserver.get_config_option("allow_signup")
        # ctf = get_ctf_by_name(ChallengeHandler.DB, args[0])
        ctf = storage_service.get_ctf(ctf_name=args[0])
        if not enabled or not ctf:
            raise InvalidCommand("No CTF by that name")

        if ctf.finished:
            raise InvalidCommand("That CTF has already concluded")

        members = [user_id]
        current = slack_wrapper.get_channel_members(ctf.channel_id)
        invites = list(set(members) - set(current))

        # Ignore responses, because errors here don't matter
        if len(invites) > 0:
            response = slack_wrapper.invite_user(invites, ctf.channel_id)
        # for chall in get_challenges_for_ctf_id(ChallengeHandler.DB, ctf.channel_id):
        for chall in storage_service.get_challenges(ctf.channel_id):
            current = slack_wrapper.get_channel_members(chall.channel_id)
            invites = list(set(members) - set(current))
            if len(invites) > 0:
                response = slack_wrapper.invite_user(invites, chall.channel_id)


class PopulateCommand(Command):
    """
    Invite a list of members to the CTF channel and add them to any existing
    challenge channels.
    """

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        # ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        ctf = storage_service.get_ctf(ctf_id=channel_id)
        if not ctf:
            raise InvalidCommand(
                "You must be in a CTF or Challenge channel to use this command."
            )

        members = [user.strip("<>@") for user in args]
        current = slack_wrapper.get_channel_members(ctf.channel_id)
        invites = list(set(members) - set(current))

        # Ignore responses, because errors here don't matter
        if len(invites) > 0:
            slack_wrapper.invite_user(invites, ctf.channel_id)
        # for chall in get_challenges_for_ctf_id(ChallengeHandler.DB, ctf.channel_id):
        for chall in storage_service.get_challenges(ctf.channel_id):
            current = slack_wrapper.get_channel_members(chall.channel_id)
            invites = list(set(members) - set(current))
            if len(invites) > 0:
                slack_wrapper.invite_user(invites, chall.channel_id)


class AddChallengeTagCommand(Command):
    """Add a tag or tags to a challenge"""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):

        tags = None
        challenge = storage_service.get_challenge_from_args_or_channel(args, channel_id)

        if challenge.channel_id == channel_id:
            # We were called from the Challenge channel
            tags = args if len(args) > 0 else None
        elif challenge.ctf_channel_id == channel_id:
            # We were called from the CTF channel
            tags = args[1:] if len(args) > 1 else None
        else:
            raise InvalidCommand(
                "You must be in a CTF or Challenge channel to use this command."
            )

        if tags is not None:
            # There may be updates to apply
            dirty = False
            for tag in tags:
                dirty |= challenge.add_tag(tag)

            # Save challenge iff it was modified
            if dirty:
                storage_service.add_challenge(challenge)


class RemoveChallengeTagCommand(Command):
    """Remove a tag or tags from a challenge"""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):

        tags = None
        challenge = storage_service.get_challenge_from_args_or_channel(args, channel_id)

        if challenge.channel_id == channel_id:
            # We were called from the Challenge channel
            tags = args if len(args) > 0 else None
        elif challenge.ctf_channel_id == channel_id:
            # We were called from the CTF channel
            tags = args[1:] if len(args) > 1 else None
        else:
            raise InvalidCommand(
                "You must be in a CTF or Challenge channel to use this command."
            )

        if tags is not None:
            # There may be updates to apply
            dirty = False
            for tag in tags:
                dirty |= challenge.remove_tag(tag)

            # Save challenge iff it was modified
            if dirty:
                storage_service.add_challenge(challenge)


class RollCommand(Command):
    """Roll the dice. ;)"""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute Roll command."""
        val = randint(0, 100)

        member = slack_wrapper.get_member(user_id)
        display_name = get_display_name(member)

        message = "*{}* rolled the dice... *{}*".format(display_name, val)

        slack_wrapper.post_message(channel_id, message)


MAX_CHANNEL_NAME_LENGTH = 80
MAX_CTF_NAME_LENGTH = 40


class AddCTFCommand(Command):
    """Add and keep track of a new CTF."""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute AddCTF command."""
        name = args[0].lower()
        long_name = " ".join(args[1:])

        # Don't allow incorrectly parsed long names
        if "<http" in long_name:
            raise InvalidCommand(
                "Add CTF failed: Long name interpreted as link, try avoid using `.` in it."
            )

        if len(name) > MAX_CTF_NAME_LENGTH:
            raise InvalidCommand(
                "Add CTF failed: CTF name must be <= {} characters.".format(
                    MAX_CTF_NAME_LENGTH
                )
            )

        # Check for invalid characters
        if not is_valid_name(name):
            raise InvalidCommand(
                "Add CTF failed: Invalid characters for CTF name found."
            )

        # Create the channel
        private_ctf = handler_factory.botserver.get_config_option("private_ctfs")
        response = slack_wrapper.create_channel(name, is_private=private_ctf)

        # Validate that the channel was successfully created.
        if not response["ok"]:
            raise InvalidCommand(
                '"{}" channel creation failed:\nError : {}'.format(
                    name, response["error"]
                )
            )

        ctf_channel_id = response["channel"]["id"]

        # New CTF object
        ctf = CTF(channel_id=ctf_channel_id, name=name, long_name=long_name)

        # Update list of CTFs
        storage_service.add_ctf(ctf)

        # Add purpose tag for persistance
        ChallengeHandler.update_ctf_purpose(slack_wrapper, ctf)

        # Invite user
        slack_wrapper.invite_user(user_id, ctf_channel_id)

        # Invite everyone in the auto-invite list
        auto_invite_list = handler_factory.botserver.get_config_option("auto_invite")

        if type(auto_invite_list) == list:
            for invite_user_id in auto_invite_list:
                slack_wrapper.invite_user(invite_user_id, ctf_channel_id)

        # Notify people of new channel
        message = "Created channel #{}".format(response["channel"]["name"]).strip()
        slack_wrapper.post_message(channel_id, message)


class RenameChallengeCommand(Command):
    """Renames an existing challenge channel."""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        old_name = args[0].lower()
        new_name = args[1].lower()

        # Validate that the user is in a CTF channel
        # ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        ctf = storage_service.get_ctf(ctf_id=channel_id)

        if not ctf:
            raise InvalidCommand(
                "Rename challenge failed: You are not in a CTF channel."
            )

        if len(new_name) > (MAX_CHANNEL_NAME_LENGTH - len(ctf.name) - 1):
            raise InvalidCommand(
                "Rename challenge failed: Challenge name must be <= {} characters.".format(
                    MAX_CHANNEL_NAME_LENGTH - len(ctf.name) - 1
                )
            )

        # Check for invalid characters
        if not is_valid_name(new_name):
            raise InvalidCommand(
                "Command failed: Invalid characters for challenge name found."
            )

        old_channel_name = "{}-{}".format(ctf.name, old_name)
        new_channel_name = "{}-{}".format(ctf.name, new_name)

        # Get the channel id for the channel to rename
        # challenge = get_challenge_by_name(ChallengeHandler.DB, old_name, ctf.channel_id)
        challenge = storage_service.get_challenge(
            challenge_name=old_name, ctf_id=ctf.channel_id
        )

        if not challenge:
            raise InvalidCommand(
                "Rename challenge failed: Challenge '{}' not found.".format(old_name)
            )

        log.debug("Renaming channel %s to %s", channel_id, new_name)
        response = slack_wrapper.rename_channel(
            challenge.channel_id, new_channel_name, is_private=True
        )

        if not response["ok"]:
            raise InvalidCommand(
                '"{}" channel rename failed:\nError: {}'.format(
                    old_channel_name, response["error"]
                )
            )

        # Update channel purpose
        slack_wrapper.update_channel_purpose_name(
            challenge.channel_id, new_name, is_private=True
        )

        # Update database
        # update_challenge_name(ChallengeHandler.DB, challenge.channel_id, new_name)
        storage_service.update_challenge_name(challenge.channel_id, new_name)

        text = "Challenge `{}` renamed to `{}` (#{})".format(
            old_name, new_name, new_channel_name
        )
        slack_wrapper.post_message(channel_id, text)


class RenameCTFCommand(Command):
    """Renames an existing challenge channel."""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        old_name = args[0].lower()
        new_name = args[1].lower()

        # ctf = get_ctf_by_name(ChallengeHandler.DB, old_name)
        ctf = storage_service.get_ctf(ctf_name=old_name)

        if not ctf:
            raise InvalidCommand(
                "Rename CTF failed: CTF '{}' not found.".format(old_name)
            )

        ctflen = len(new_name)

        # pre-check challenges, if renaming would break channel name length
        for chall in ctf.challenges:
            if len(chall.name) + ctflen > MAX_CHANNEL_NAME_LENGTH - 1:
                raise InvalidCommand(
                    "Rename CTF failed: Challenge {} would break channel name length restriction.".format(
                        chall.name
                    )
                )

        # still ctf name shouldn't be longer than 10 characters for allowing reasonable challenge names
        if len(new_name) > MAX_CTF_NAME_LENGTH:
            raise InvalidCommand(
                "Rename CTF failed: CTF name must be <= {} characters.".format(
                    MAX_CTF_NAME_LENGTH
                )
            )

        # Check for invalid characters
        if not is_valid_name(new_name):
            raise InvalidCommand(
                "Rename CTF failed: Invalid characters for CTF name found."
            )

        text = "Renaming the CTF might take some time depending on active channels..."
        slack_wrapper.post_message(ctf.channel_id, text)

        # Rename the ctf channel
        response = slack_wrapper.rename_channel(ctf.channel_id, new_name)

        if not response["ok"]:
            raise InvalidCommand(
                '"{}" channel rename failed:\nError : {}'.format(
                    old_name, response["error"]
                )
            )

        # Update channel purpose
        slack_wrapper.update_channel_purpose_name(ctf.channel_id, new_name)

        # Update database
        # update_ctf_name(ChallengeHandler.DB, ctf.channel_id, new_name)
        storage_service.update_ctf_name(ctf.channel_id, new_name)

        # Rename all challenge channels for this ctf
        for chall in ctf.challenges:
            RenameChallengeCommand().execute(
                slack_wrapper,
                storage_service,
                [chall.name, chall.name],
                timestamp,
                ctf.channel_id,
                user_id,
                user_is_admin,
            )

        text = "CTF `{}` renamed to `{}` (#{})".format(old_name, new_name, new_name)
        slack_wrapper.post_message(ctf.channel_id, text)


class AddChallengeCommand(Command):
    """
    Add and keep track of a new challenge for a given CTF.
    """

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the AddChallenge command."""
        name = args[0].lower()
        category = args[1] if len(args) > 1 else ""

        # Validate that the user is in a CTF channel
        # ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        ctf = storage_service.get_ctf(ctf_id=channel_id)

        if not ctf:
            raise InvalidCommand("Add challenge failed: You are not in a CTF channel.")

        if len(name) > (MAX_CHANNEL_NAME_LENGTH - len(ctf.name) - 1):
            raise InvalidCommand(
                "Add challenge failed: Challenge name must be <= {} characters.".format(
                    MAX_CHANNEL_NAME_LENGTH - len(ctf.name) - 1
                )
            )

        # Check for invalid characters
        if not is_valid_name(name):
            raise InvalidCommand(
                "Command failed: Invalid characters for challenge name found."
            )

        # Check for finished ctf
        if ctf.finished and not user_is_admin:
            raise InvalidCommand(
                "Add challenge faild: CTF *{}* is over...".format(ctf.name)
            )

        # Create the challenge channel
        channel_name = "{}-{}".format(ctf.name, name)
        response = slack_wrapper.create_channel(channel_name, is_private=True)

        # Validate that the channel was created successfully
        if not response["ok"]:
            raise InvalidCommand(
                '"{}" channel creation failed:\nError : {}'.format(
                    channel_name, response["error"]
                )
            )

        # Add purpose tag for persistence
        challenge_channel_id = response["channel"]["id"]
        purpose = dict(ChallengeHandler.CHALL_PURPOSE)
        purpose["name"] = name
        purpose["ctf_id"] = ctf.channel_id
        purpose["category"] = category

        slack_wrapper.set_purpose(
            challenge_channel_id, json.dumps(purpose), is_private=True
        )

        if handler_factory.botserver.get_config_option("auto_invite") is True:
            # Invite everyone in the ctf channel
            members = slack_wrapper.get_channel_members(ctf.channel_id)
            present = slack_wrapper.get_channel_members(challenge_channel_id)
            invites = list(set(members) - set(present))
            slack_wrapper.invite_user(invites, challenge_channel_id)
        else:
            # Invite everyone in the auto-invite list
            for invite_user_id in handler_factory.botserver.get_config_option(
                "auto_invite"
            ):
                slack_wrapper.invite_user(
                    invite_user_id, challenge_channel_id, is_private=True
                )

        # New Challenge
        challenge = Challenge(
            ctf_channel_id=ctf.channel_id,
            channel_id=challenge_channel_id,
            name=name,
            category=category,
        )

        # Update database
        storage_service.add_challenge(challenge, ctf.channel_id)

        # Notify the channel
        text = "New challenge *{0}* created in private channel (type `\ctf workon {0}` to join).".format(
            name
        )
        slack_wrapper.post_message(channel_id, text)


class RemoveChallengeCommand(Command):
    """
    Remove a challenge from the CTF.
    """

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the RemoveChallenge command."""
        challenge_name = args[0].lower() if args else None

        # Validate that current channel is a CTF channel
        # ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        ctf = storage_service.get_ctf(ctf_id=channel_id)

        if not ctf:
            raise InvalidCommand(
                "Remove challenge failed: You are not in a CTF channel."
            )

        # Get challenge object for challenge name or channel id
        # if challenge_name:
        #     challenge = get_challenge_by_name(
        #         ChallengeHandler.DB, challenge_name, channel_id
        #     )
        # else:
        #     challenge = get_challenge_by_channel_id(ChallengeHandler.DB, channel_id)
        challenge = storage_service.get_challenge(
            challenge_name=challenge_name, ctf_id=channel_id
        )

        if not challenge:
            raise InvalidCommand("This challenge does not exist.")

        # Remove the challenge channel and ctf challenge entry
        slack_wrapper.archive_private_channel(challenge.channel_id)
        # remove_challenge_by_channel_id(
        #     ChallengeHandler.DB, challenge.channel_id, ctf.channel_id
        # )
        storage_service.remove_challenge(challenge.channel_id, ctf.channel_id)

        # Show confirmation message
        member = slack_wrapper.get_member(user_id)
        display_name = get_display_name(member)

        slack_wrapper.post_message(
            ctf.channel_id,
            text="Challenge *{}* was removed by *{}*.".format(
                challenge.name, display_name
            ),
        )


class StatusCommand(Command):
    """
    Get a status of the currently running CTFs.
    """

    @classmethod
    def build_short_status(cls, ctf_list):
        """Build short status list."""
        finished_response = ""
        running_response = ""

        def get_ctf_status(ctf, append=""):
            # Build short status list
            solved = [c for c in ctf.challenges if c.is_solved]
            return "*#{} : _{}_ [{} solved / {} total] {}*\n".format(
                ctf.name, ctf.long_name, len(solved), len(ctf.challenges), append
            )

        for ctf in ctf_list:
            if ctf.finished:
                finish_info = (
                    "(finished {} ago)".format(cls.get_finished_string(ctf))
                    if ctf.finished_on
                    else "(finished)"
                )
                finished_response += get_ctf_status(ctf, finish_info)
            else:
                running_response += get_ctf_status(ctf)

        running_response = running_response.strip()
        finished_response = finished_response.strip()

        if running_response != "":
            running_response = "*Current CTFs:*\n{}".format(running_response)

        if finished_response != "":
            finished_response = "*Finished CTFs:*\n{}".format(finished_response)

        response = "\n\n".join(
            [resp for resp in [running_response, finished_response] if resp]
        )

        if response == "":  # Response is empty
            response += "*There are currently no running CTFs*"

        return response

    @classmethod
    def get_finished_string(cls, ctf):
        timespan = time.time() - ctf.finished_on

        if timespan < 3600:
            return "less than an hour"

        # https://stackoverflow.com/a/11157649
        attrs = ["years", "months", "days", "hours"]

        def human_readable(delta):
            return [
                "%d %s"
                % (getattr(delta, attr), getattr(delta, attr) > 1 and attr or attr[:-1])
                for attr in attrs
                if getattr(delta, attr)
            ]

        return ", ".join(human_readable(relativedelta(seconds=timespan)))

    @classmethod
    def build_verbose_status(cls, slack_wrapper, ctf_list, check_for_finish, category):
        """Build verbose status list."""
        member_list = slack_wrapper.get_members()

        # Bail out, if we couldn't read member list
        if "members" not in member_list:
            raise InvalidCommand("Status failed. Could not refresh member list...")

        members = {
            m["id"]: get_display_name_from_user(m) for m in member_list["members"]
        }

        response = ""
        for ctf in ctf_list:
            # Build long status list
            solved = sorted(
                [
                    c
                    for c in ctf.challenges
                    if c.is_solved and (not category or c.category == category)
                ],
                key=lambda x: x.solve_date,
            )
            unsolved = [
                c
                for c in ctf.challenges
                if not c.is_solved and (not category or c.category == category)
            ]

            # Don't show ctfs not having a category challenge if filter is active
            if category and not solved and not unsolved:
                continue

            response += "*============= #{} {} {}=============*\n".format(
                ctf.name,
                "(finished)" if ctf.finished else "",
                "[{}] ".format(category) if category else "",
            )

            if ctf.finished and ctf.finished_on:
                response += "* > Finished {} ago*\n".format(
                    cls.get_finished_string(ctf)
                )

            # Check if the CTF has any challenges
            if check_for_finish and ctf.finished and not solved:
                response += "*[ No challenges solved ]*\n"
                continue
            elif not solved and not unsolved:
                response += "*[ No challenges available yet ]*\n"
                continue

            # Solved challenges
            response += "* > Solved*\n" if solved else ""
            for challenge in solved:
                players = []
                response += ":tada: *{}*{} (Solved by : {})\n".format(
                    challenge.name,
                    " ({})".format(challenge.category) if challenge.category else "",
                    transliterate(", ".join(challenge.solver)),
                )

            # Unsolved challenges
            if not check_for_finish or not ctf.finished:
                response += "* > Unsolved*\n" if unsolved else "\n"
                for challenge in unsolved:

                    # Get active players
                    players = []
                    for player_id in challenge.players:
                        if player_id in members:
                            players.append(members[player_id])

                    response += "[{} active] *{}* {}: {}\n".format(
                        len(players),
                        challenge.name,
                        "[{}]".format(", ".join(challenge.tags))
                        if len(challenge.tags) > 0
                        else "",
                        "({})".format(challenge.category) if challenge.category else "",
                    )
        response = response.strip()

        if response == "":  # Response is empty
            response += "*There are currently no running CTFs*"

        return response

    @classmethod
    def build_status_message(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        channel_id,
        user_id,
        user_is_admin,
        verbose=True,
        category="",
    ):
        """Gathers the ctf information and builds the status response."""
        ctfs = storage_service.get_ctfs()

        # Check if the user is in a ctf channel
        # current_ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        current_ctf = storage_service.get_ctf(ctf_id=channel_id)

        if current_ctf:
            ctf_list = [current_ctf]
            check_for_finish = False
            verbose = True  # override verbose for ctf channels
        else:
            ctf_list = ctfs
            check_for_finish = True

        if verbose:
            response = cls.build_verbose_status(
                slack_wrapper, ctf_list, check_for_finish, category
            )
        else:
            response = cls.build_short_status(ctf_list)

        return response, verbose

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the Status command."""
        verbose = args[0] == "-v" if args else False

        if verbose:
            category = args[1] if len(args) > 1 else ""
        else:
            category = args[0] if args else ""

        response, verbose = cls.build_status_message(
            slack_wrapper,
            storage_service,
            args,
            channel_id,
            user_id,
            user_is_admin,
            verbose,
            category,
        )

        if verbose:
            slack_wrapper.post_message(
                channel_id, response, user_id=user_id
            )
        else:
            slack_wrapper.post_message(
                channel_id, response, user_id=user_id
            )


class WorkonCommand(Command):
    """
    Mark a player as "working" on a challenge.
    """

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the Workon command."""
        challenge_name = args[0].lower().strip("*") if args else None

        # Validate that current channel is a CTF channel
        # ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        ctf = storage_service.get_ctf(ctf_id=channel_id)

        if not ctf:
            raise InvalidCommand("Workon failed: You are not in a CTF channel.")

        # Get challenge object for challenge name or channel id
        # if challenge_name:
        #     challenge = get_challenge_by_name(
        #         ChallengeHandler.DB, challenge_name, channel_id
        #     )
        # else:
        #     challenge = get_challenge_by_channel_id(ChallengeHandler.DB, channel_id)
        challenge = storage_service.get_challenge(
            challenge_name=challenge_name, ctf_id=channel_id
        )

        if not challenge:
            raise InvalidCommand("This challenge does not exist.")

        # Don't allow joining already solved challenges (except after finish or for admins)
        if challenge.is_solved and not ctf.finished and not user_is_admin:
            raise InvalidCommand("This challenge is already solved.")

        # Invite user to challenge channel
        slack_wrapper.invite_user(user_id, challenge.channel_id, is_private=True)

        # Update database
        challenge.add_player(Player(user_id=user_id))
        storage_service.add_challenge(challenge, challenge.ctf_channel_id)


class SolveCommand(Command):
    """
    Mark a challenge as solved.
    """

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the Solve command."""
        if args:
            # challenge: Challenge = get_challenge_from_args(ChallengeHandler.DB, args, channel_id)
            challenge = storage_service.get_challenge(
                challenge_name=args[0].lower().strip("*"), ctf_id=channel_id
            )

            if not challenge:
                # challenge: Challenge = get_challenge_by_channel_id(ChallengeHandler.DB, channel_id)
                challenge = storage_service.get_challenge(challenge_id=channel_id)
                additional_args = args if args else []
            else:
                additional_args = args[1:] if len(args) > 1 else []
        else:
            # No arguments => direct way of resolving challenge
            # challenge: Challenge = get_challenge_by_channel_id(ChallengeHandler.DB, channel_id)
            challenge = storage_service.get_challenge(challenge_id=channel_id)

            additional_args = []

        if not challenge:
            raise InvalidCommand("This challenge does not exist.")

        additional_solver = []

        # Get solving member
        member = slack_wrapper.get_member(user_id)
        solver_list = [get_display_name(member)]

        # Find additional members to add
        for add_solve in additional_args:
            user_obj = resolve_user_by_user_id(slack_wrapper, add_solve)

            if user_obj["ok"]:
                add_solve = get_display_name(user_obj)

            if add_solve not in solver_list:
                solver_list.append(add_solve)
                additional_solver.append(add_solve)

        # Update database
        if not challenge.is_solved:
            # Check for finished ctf
            ctf = storage_service.get_ctf(ctf_id=challenge.ctf_channel_id)
            if ctf.finished and not user_is_admin:
                raise InvalidCommand(
                    "Solve challenge faild: CTF *{}* is over...".format(ctf.name)
                )

            member = slack_wrapper.get_member(user_id)
            solver_list = [get_display_name(member)] + additional_solver

            challenge.mark_as_solved(solver_list)
            ctf.add_challenge(challenge)
            storage_service.add_ctf(ctf)

            # Update channel purpose
            purpose = dict(ChallengeHandler.CHALL_PURPOSE)
            purpose["name"] = challenge.name
            purpose["ctf_id"] = ctf.channel_id
            purpose["solved"] = str(solver_list)
            purpose["solve_date"] = str(challenge.solve_date)
            purpose["category"] = challenge.category

            slack_wrapper.set_purpose(
                challenge.channel_id, json.dumps(purpose), is_private=True
            )

            # Announce the CTF channel
            help_members = ""

            if additional_solver:
                help_members = "(together with {})".format(", ".join(additional_solver))

            message = '@here *{}* : {} has solved the "{}" challenge {}'.format(
                challenge.name,
                get_display_name(member),
                challenge.name,
                help_members,
            )
            message += "."

            slack_wrapper.post_message(ctf.channel_id, message)


class UnsolveCommand(Command):
    """
    Mark a solved challenge as unsolved again.
    """

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the Unsolve command."""
        challenge: Challenge | None = None

        if args:
            # challenge = get_challenge_from_args(ChallengeHandler.DB, args, channel_id)
            challenge = storage_service.get_challenge(
                challenge_name=args[0].lower().strip("*"), ctf_id=channel_id
            )

        if not challenge:
            # challenge = get_challenge_by_channel_id(ChallengeHandler.DB, channel_id)
            challenge = storage_service.get_challenge(challenge_id=channel_id)

        if not challenge:
            raise InvalidCommand("This challenge does not exist.")

        # Update database
        if challenge.is_solved:
            member = slack_wrapper.get_member(user_id)

            challenge.unmark_as_solved()

            ctf = storage_service.get_ctf(ctf_id=challenge.ctf_channel_id)
            ctf.add_challenge(challenge)
            storage_service.add_ctf(ctf)

            # Update channel purpose
            purpose = dict(ChallengeHandler.CHALL_PURPOSE)
            purpose["name"] = challenge.name
            purpose["ctf_id"] = challenge.ctf_channel_id
            purpose["category"] = challenge.category

            slack_wrapper.set_purpose(
                challenge.channel_id, json.dumps(purpose), is_private=True
            )

            # Announce the CTF channel
            message = (
                '@here *{}* : {} has reset the solve on the "{}" challenge.'.format(
                    challenge.name, get_display_name(member), challenge.name
                )
            )
            slack_wrapper.post_message(ctf.channel_id, message)

            return

        raise InvalidCommand("This challenge isn't marked as solve.")


class ArchiveCTFCommand(Command):
    """Archive the challenge channels for a given CTF."""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the ArchiveCTF command."""
        no_post = args[0].lower() if args else None

        # ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        ctf = storage_service.get_ctf(ctf_id=channel_id)
        if not ctf or ctf.channel_id != channel_id:
            raise InvalidCommand("Archive CTF failed: You are not in a CTF channel.")

        # Get list of challenges
        # challenges = get_challenges_for_ctf_id(ChallengeHandler.DB, channel_id)
        challenges = storage_service.get_challenges(channel_id)

        message = "Archived the following channels :\n"
        for challenge in challenges:
            message += "- #{}-{}\n".format(ctf.name, challenge.name)
            slack_wrapper.archive_channel(challenge.channel_id)
            # remove_challenge_by_channel_id(
            #     ChallengeHandler.DB, challenge.channel_id, ctf.channel_id
            # )
            storage_service.remove_challenge(challenge.channel_id, ctf.channel_id)

        # Remove possible configured reminders for this ctf
        try:
            cleanup_reminders(slack_wrapper, handler_factory, ctf)
        except SlackApiError as e:
            log.error(f"Error cleaning up reminders: {e}")

        # Stop tracking the main CTF channel
        slack_wrapper.set_purpose(channel_id, "")
        # remove_ctf_by_channel_id(ChallengeHandler.DB, ctf.channel_id)
        storage_service.remove_ctf(ctf.channel_id)

        # Show confirmation message
        slack_wrapper.post_message(channel_id, message)

        # If configured to do so, archive the main CTF channel also to clean up
        if handler_factory.botserver.get_config_option("archive_everything"):
            slack_wrapper.archive_channel(channel_id)
        else:
            # Otherwise, just set the ctf to finished
            if not ctf.finished:
                ctf.finished = True
                ctf.finished_on = int(time.time())


class EndCTFCommand(Command):
    """
    Mark the ctf as finished, not allowing new challenges to be added, and don't show the ctf anymore
    in the status list.
    """

    @classmethod
    def handle_archive_reminder(cls, slack_wrapper, ctf):
        """Sets a reminder for admins to archive this ctf in a set time."""
        reminder_offset = handler_factory.botserver.get_config_option(
            "archive_ctf_reminder_offset"
        )

        if not reminder_offset:
            return

        admin_users = handler_factory.botserver.get_config_option("admin_users")

        if not admin_users:
            return

        msg = "CTF {} - {} (#{}) should be archived.".format(
            ctf.name, ctf.long_name, ctf.name
        )

        for admin in admin_users:
            slack_wrapper.add_reminder_hours(admin, msg, reminder_offset)

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the EndCTF command."""

        # ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        ctf = storage_service.get_ctf(ctf_id=channel_id)
        if not ctf:
            raise InvalidCommand("End CTF failed: You are not in a CTF channel.")

        if ctf.finished:
            raise InvalidCommand("CTF is already marked as finished...")

        def update_func(ctf):
            ctf.finished = True
            ctf.finished_on = int(time.time())

        # Update database
        # ctf = update_ctf(ChallengeHandler.DB, ctf.channel_id, update_func)
        ctf = storage_service.update_ctf(ctf.channel_id, update_func)

        if ctf:
            ChallengeHandler.update_ctf_purpose(slack_wrapper, ctf)
            cls.handle_archive_reminder(slack_wrapper, ctf)
            slack_wrapper.post_message(
                channel_id, "CTF *{}* finished...".format(ctf.name)
            )


class ReloadCommand(Command):
    """Reload the ctf information from slack to reflect updates of channel purposes."""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the Reload command."""

        slack_wrapper.post_message(channel_id, "Updating CTFs and challenges...")
        ChallengeHandler.update_database_from_slack(slack_wrapper, storage_service)
        slack_wrapper.post_message(channel_id, "Update finished...")


class AddCredsCommand(Command):
    """Add credential information for current ctf."""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the AddCreds command."""

        # cur_ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        cur_ctf = storage_service.get_ctf(ctf_id=channel_id)
        if not cur_ctf:
            raise InvalidCommand("Add Creds failed:. You are not in a CTF channel.")

        def update_func(ctf):
            ctf.cred_user = args[0]
            ctf.cred_pw = args[1]

        # Update database
        # ctf = update_ctf(ChallengeHandler.DB, cur_ctf.channel_id, update_func)
        ctf = storage_service.update_ctf(cur_ctf, update_func)

        if ctf:
            ChallengeHandler.update_ctf_purpose(slack_wrapper, ctf)

            ctf_cred_url = args[2] if len(args) > 2 else ""

            if ctf_cred_url:
                slack_wrapper.set_topic(channel_id, ctf_cred_url)

            message = "Credentials for CTF *{}* updated...".format(ctf.name)
            slack_wrapper.post_message(channel_id, message)


class ShowCredsCommand(Command):
    """Shows credential information for current ctf."""

    @classmethod
    def execute(
        cls,
        slack_wrapper,
        storage_service: StorageService,
        args,
        timestamp,
        channel_id,
        user_id,
        user_is_admin,
    ):
        """Execute the ShowCreds command."""

        # cur_ctf = get_ctf_by_channel_id(ChallengeHandler.DB, channel_id)
        cur_ctf = storage_service.get_ctf(ctf_id=channel_id)
        if not cur_ctf:
            raise InvalidCommand("Show creds failed: You are not in a CTF channel.")

        if cur_ctf.cred_user and cur_ctf.cred_pw:
            message = "Credentials for CTF *{}*\n".format(cur_ctf.name)
            message += "```"
            message += "Username : {}\n".format(cur_ctf.cred_user)
            message += "Password : {}\n".format(cur_ctf.cred_pw)
            message += "```"
        else:
            message = "No credentials provided for CTF *{}*.".format(cur_ctf.name)

        slack_wrapper.post_message(channel_id, message, "", parse=None)


class ChallengeHandler(BaseHandler):
    """
    Manages everything related to challenge coordination.

    Commands :
    # Create a defcon-25-quals channel
    \ctf addctf "defcon 25 quals"

    # Create a web-100 channel
    \ctf addchallenge "web 100" "defcon 25 quals"

    # Kick member from other ctf challenge channels and invite the member to the web 100 channel
    \ctf workon "web100"

    # Get status of all CTFs
    \ctf status
    """

    DB = "databases/challenge_handler.bin"
    CTF_PURPOSE = {
        "ctf_bot": "CTFBOT",
        "name": "",
        "type": "CTF",
        "cred_user": "",
        "cred_pw": "",
        "long_name": "",
        "finished": False,
        "finished_on": 0,
    }

    CHALL_PURPOSE = {
        "ctf_bot": "CTFBOT",
        "ctf_id": "",
        "name": "",
        "solved": "",
        "category": "",
        "type": "CHALLENGE",
    }

    def __init__(self):
        self.commands = {
            "addctf": CommandDesc(
                command=AddCTFCommand,
                description="Adds a new ctf",
                arguments=["ctf_name", "long_name"],
            ),
            "addchallenge": CommandDesc(
                command=AddChallengeCommand,
                description="Adds a new challenge for current ctf",
                arguments=["challenge_name"],
                opt_arguments=["challenge_category"],
            ),
            "workon": CommandDesc(
                command=WorkonCommand,
                description="Show that you're working on a challenge",
                opt_arguments=["challenge_name"],
            ),
            "status": CommandDesc(
                command=StatusCommand,
                description="Show the status for all ongoing ctf's",
                opt_arguments=["category"],
            ),
            "signup": CommandDesc(
                command=SignupCommand,
                description="Join a CTF",
                opt_arguments=["ctf_name"],
            ),
            "solve": CommandDesc(
                command=SolveCommand,
                description="Mark a challenge as solved",
                opt_arguments=["challenge_name", "support_member"],
            ),
            "renamechallenge": CommandDesc(
                command=RenameChallengeCommand,
                description="Renames a challenge",
                arguments=["old_challenge_name", "new_challenge_name"],
            ),
            "renamectf": CommandDesc(
                command=RenameCTFCommand,
                description="Renames a ctf",
                arguments=["old_ctf_name", "new_ctf_name"],
            ),
            "reload": CommandDesc(
                command=ReloadCommand,
                description="Reload ctf information from slack",
                is_admin_cmd=True,
            ),
            "archivectf": CommandDesc(
                command=ArchiveCTFCommand,
                description="Archive the challenges of a ctf",
                opt_arguments=["nopost"],
                is_admin_cmd=True,
            ),
            "endctf": CommandDesc(
                command=EndCTFCommand,
                description="Mark a ctf as ended, but not archive it directly",
                is_admin_cmd=True,
            ),
            "addcreds": CommandDesc(
                command=AddCredsCommand,
                description="Add credentials for current ctf",
                arguments=["ctf_user", "ctf_pw"],
                opt_arguments=["ctf_url"],
            ),
            "showcreds": CommandDesc(
                command=ShowCredsCommand, description="Show credentials for current ctf"
            ),
            "tag": CommandDesc(
                command=AddChallengeTagCommand,
                description="Add tag(s) to a challenge",
                arguments=["challenge_tag/name"],
                opt_arguments=["[..challenge_tag(s)]"],
            ),
            "unsolve": CommandDesc(
                command=UnsolveCommand,
                description="Remove solve of a challenge",
                opt_arguments=["challenge_name"],
            ),
            "removechallenge": CommandDesc(
                command=RemoveChallengeCommand,
                description="Remove challenge",
                opt_arguments=["challenge_name"],
                is_admin_cmd=True,
            ),
            "removetag": CommandDesc(
                command=RemoveChallengeTagCommand,
                description="Remove tag(s) from a challenge",
                arguments=["challenge_tag/name"],
                opt_arguments=["[..challenge_tag(s)]"],
            ),
            "populate": CommandDesc(
                command=PopulateCommand,
                description="Invite all non-present members of the CTF challenge into the challenge channel",
            ),
            "roll": CommandDesc(command=RollCommand, description="Roll the dice"),
        }
        self.aliases = {
            "finishctf": "endctf",
            "addchall": "addchallenge",
            "add": "addchallenge",
            "archive": "archivectf",
            "gather": "populate",
            "summon": "populate",
        }

    @staticmethod
    def update_ctf_purpose(slack_wrapper, ctf):
        """
        Update the purpose for the ctf channel.
        """
        purpose = dict(ChallengeHandler.CTF_PURPOSE)
        purpose["ctf_bot"] = "CTFBOT"
        purpose["name"] = ctf.name
        purpose["type"] = "CTF"
        purpose["cred_user"] = ctf.cred_user
        purpose["cred_pw"] = ctf.cred_pw
        purpose["long_name"] = ctf.long_name
        purpose["finished"] = ctf.finished
        purpose["finished_on"] = ctf.finished_on

        slack_wrapper.set_purpose(ctf.channel_id, json.dumps(purpose))

    @staticmethod
    def update_database_from_slack(slack_wrapper, storage_service):
        """
        Reload the ctf and challenge information from slack.
        """
        database = {}
        privchans = slack_wrapper.get_private_channels()
        pubchans = slack_wrapper.get_public_channels()

        # Find active CTF channels
        for channel in [*privchans, *pubchans]:
            try:
                purpose = load_json(channel["purpose"]["value"])

                if (
                    not channel["is_archived"]
                    and purpose
                    and "ctf_bot" in purpose
                    and purpose["type"] == "CTF"
                ):
                    ctf = CTF(
                        channel_id=channel["id"],
                        name=purpose["name"],
                        long_name=purpose["long_name"],
                    )

                    ctf.cred_user = purpose.get("cred_user", "")
                    ctf.cred_pw = purpose.get("cred_pw", "")
                    ctf.finished = purpose.get("finished", False)
                    ctf.finished_on = purpose.get("finished_on", 0)

                    database[ctf.channel_id] = ctf
            except:
                pass

        # Find active challenge channels
        for channel in privchans:
            try:
                purpose = load_json(channel["purpose"]["value"])

                if (
                    not channel["is_archived"]
                    and purpose
                    and "ctf_bot" in purpose
                    and purpose["type"] == "CHALLENGE"
                ):
                    challenge = Challenge(
                        ctf_channel_id=purpose["ctf_id"],
                        channel_id=channel["id"],
                        name=purpose["name"],
                        category=purpose.get("category"),
                    )
                    ctf_channel_id = purpose["ctf_id"]
                    solvers = purpose["solved"]
                    ctf = database.get(ctf_channel_id)

                    # Mark solved challenges
                    if solvers:
                        challenge.mark_as_solved(solvers, purpose.get("solve_date"))

                    if ctf:
                        members = slack_wrapper.get_channel_members(channel["id"])
                        for member_id in members:
                            if member_id != slack_wrapper.user_id:
                                challenge.add_player(Player(user_id=member_id))

                        ctf.add_challenge(challenge)
            except:
                pass

        # Create the database accordingly
        for _ctf in database.values():
            storage_service.add_ctf(_ctf)

    def init(self, slack_wrapper, storage_service):
        ChallengeHandler.update_database_from_slack(slack_wrapper, storage_service)


# Register this handler
handler_factory.register("ctf", ChallengeHandler())
