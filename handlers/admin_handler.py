from bottypes.command import Command
from bottypes.command_descriptor import CommandDesc
from bottypes.invalid_command import InvalidCommand
from handlers import handler_factory
from handlers.base_handler import BaseHandler
from util.util import get_display_name_from_user, parse_user_id, resolve_user_by_user_id


class MakeCTFCommand(Command):
    """
    Update the channel purpose to be that of a CTF.
    """

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        if user_is_admin:
            purpose = {
                "ctf_bot": "CTFBOT",
                "name": args[0],
                "type": "CTF",
                "cred_user": "",
                "cred_pw": "",
                "long_name": args[0],
                "finished": False,
                "finished_on": "",
            }
            slack_wrapper.set_purpose(channel_id, purpose)


class StartDebuggerCommand(Command):
    """
    Break into pdb. Better have a tty open!
    Must be in maintenance mode to use.
    """

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        if user_is_admin:
            if handler_factory.botserver.get_config_option("maintenance_mode"):
                import pdb

                pdb.set_trace()
            else:
                InvalidCommand("Must be in maintenance mode to open a shell")


class JoinChannelCommand(Command):
    """
    Join the named channel.
    """

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        if user_is_admin:
            channel = slack_wrapper.get_channel_by_name(args[0])
            if channel:
                slack_wrapper.invite_user(user_id, channel["id"])
            else:
                slack_wrapper.post_message(user_id, "No such channel")


class ToggleMaintenanceModeCommand(Command):
    """Update maintenance mode configuration."""

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        """Execute the ToggleMaintenanceModeCommand command."""
        mode = not bool(handler_factory.botserver.get_config_option("maintenance_mode"))
        state = "enabled" if mode else "disabled"
        handler_factory.botserver.set_config_option("maintenance_mode", mode)
        text = "Maintenance mode " + state
        slack_wrapper.post_message(channel_id, text)


class ShowAdminsCommand(Command):
    """Shows list of users in the admin user group."""

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        """Execute the ShowAdmins command."""

        admin_users = handler_factory.botserver.get_config_option("admin_users")

        if admin_users:
            response = "Administrators\n"
            response += "===================================\n"

            for admin_id in admin_users:
                user_object = slack_wrapper.get_member(admin_id)

                if user_object["ok"]:
                    response += "*{}* ({})\n".format(
                        get_display_name_from_user(user_object["user"]), admin_id
                    )

            response += "==================================="

            response = response.strip()

            if response == "":  # Response is empty
                response += "*No entries found*"

            slack_wrapper.post_message(channel_id, response)
        else:
            response = "No admin_users group found. Please check your configuration."

            slack_wrapper.post_message(channel_id, response)


class AddAdminCommand(Command):
    """Add a user to the admin user group."""

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        """Execute the AddAdmin command."""
        user_object = resolve_user_by_user_id(slack_wrapper, args[0])

        admin_users = handler_factory.botserver.get_config_option("admin_users")

        if user_object["ok"] and admin_users:
            if user_object["user"]["id"] not in admin_users:
                admin_users.append(user_object["user"]["id"])

                handler_factory.botserver.set_config_option("admin_users", admin_users)

                response = "User *{}* added to the admin group.".format(
                    user_object["user"]["name"]
                )
                slack_wrapper.post_message(channel_id, response)
            else:
                response = "User *{}* is already in the admin group.".format(
                    user_object["user"]["name"]
                )
                slack_wrapper.post_message(channel_id, response)
        else:
            response = "User *{}* not found. You must provide the slack user id, not the username.".format(
                args[0]
            )
            slack_wrapper.post_message(channel_id, response)


class RemoveAdminCommand(Command):
    """Remove a user from the admin user group."""

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        """Execute the RemoveAdmin command."""
        user = parse_user_id(args[0])

        admin_users = handler_factory.botserver.get_config_option("admin_users")

        if admin_users and user in admin_users:
            admin_users.remove(user)
            handler_factory.botserver.set_config_option("admin_users", admin_users)

            response = "User *{}* removed from the admin group.".format(user)
            slack_wrapper.post_message(channel_id, response)
        else:
            response = "User *{}* doesn't exist in the admin group".format(user)
            slack_wrapper.post_message(channel_id, response)


class AsCommand(Command):
    """Execute a command as another user."""

    @classmethod
    def execute(
        cls, slack_wrapper, args, timestamp, channel_id, user_id, user_is_admin
    ):
        """Execute the As command."""
        dest_user = args[0].lower()
        dest_command = args[1].lower().lstrip("/")

        dest_arguments = args[2:]

        user_obj = resolve_user_by_user_id(slack_wrapper, dest_user)

        if user_obj["ok"]:
            dest_user_id = user_obj["user"]["id"]

            # Redirecting command execution to handler factory
            handler_factory.process_command(
                slack_wrapper,
                None,
                dest_command,
                [dest_command] + dest_arguments,
                timestamp,
                channel_id,
                dest_user_id,
                user_is_admin,
            )
        else:
            raise InvalidCommand("You have to specify a valid user (use @-notation).")


class AdminHandler(BaseHandler):
    """
    Handles configuration options for administrators.
    """

    def __init__(self):
        self.commands = {
            "show_admins": CommandDesc(
                command=ShowAdminsCommand,
                description="Show a list of current admin users",
                is_admin_cmd=True,
            ),
            "add_admin": CommandDesc(
                command=AddAdminCommand,
                description="Add a user to the admin user group",
                arguments=["user_id"],
                is_admin_cmd=True,
            ),
            "remove_admin": CommandDesc(
                command=RemoveAdminCommand,
                description="Remove a user from the admin user group",
                arguments=["user_id"],
                is_admin_cmd=True,
            ),
            "as": CommandDesc(
                command=AsCommand,
                description="Execute a command as another user",
                arguments=["@user", "command"],
                is_admin_cmd=True,
            ),
            "maintenance": CommandDesc(
                command=ToggleMaintenanceModeCommand,
                description="Toggle maintenance mode",
                is_admin_cmd=True,
            ),
            "debug": CommandDesc(
                command=StartDebuggerCommand,
                description="Break into a debugger shell",
                is_admin_cmd=True,
            ),
            "join": CommandDesc(
                command=JoinChannelCommand,
                description="Join a channel",
                arguments=["channel_name"],
                is_admin_cmd=True,
            ),
            "makectf": CommandDesc(
                command=MakeCTFCommand,
                description="Turn the current channel into a CTF channel by setting the purpose. Requires reload to take effect",
                arguments=["ctf_name"],
                is_admin_cmd=True,
            ),
        }


handler_factory.register("admin", AdminHandler())
