import json
import os
from json import JSONDecodeError

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from util.loghandler import log


class SlackWrapper:
    """
    Slack API wrapper
    """

    def __init__(self):
        """
        SlackWrapper constructor.
        Connect to the real-time messaging API and
        load the bot's login data.
        """

        self.client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

    def invite_user(self, users, channel, is_private=False):
        """
        Invite the given user(s) to the given channel.
        """

        users = [users] if not type(users) == list else users
        return self.client.conversations_invite(channel=channel, users=users)

    def set_purpose(self, channel: str, purpose: str, is_private=False):
        """
        Set the purpose of a given channel.
        """

        return self.client.conversations_setPurpose(purpose=purpose, channel=channel)

    def set_topic(self, channel, topic, is_private=False):
        """Set the topic of a given channel."""

        return self.client.conversations_setTopic(topic=topic, channel=channel)

    def get_members(self):
        """
        Return a list of all members.
        """

        return self.client.users_list()

    def get_member(self, user_id):
        """
        Return a member for a given user_id.
        """

        return self.client.users_info(user=user_id)

    def create_channel(self, name, is_private=False):
        """
        Create a channel with a given name.
        """

        return self.client.conversations_create(name=name, is_private=is_private)

    def rename_channel(self, channel_id, new_name, is_private=False):
        """
        Rename an existing channel.
        """

        return self.client.conversations_rename(
            channel=channel_id, name=new_name, validate=False
        )

    def get_channel_info(self, channel_id, is_private=False):
        """
        Return the channel info of a given channel ID.
        """

        return self.client.conversations_info(channel=channel_id)

    def get_channel_members(self, channel_id, next_cursor=None):
        """Recursively fetch members of the given channel, until none remain to be fetched"""

        response = self.client.conversations_members(
            channel=channel_id, cursor=next_cursor
        )
        members = response["members"]
        next_cursor = response["response_metadata"]["next_cursor"]
        if not next_cursor:
            return members
        else:
            return members + self.get_channel_members(channel_id, next_cursor)

    def update_channel_purpose_name(self, channel_id, new_name, is_private=False):
        """
        Updates the channel purpose 'name' field for a given channel ID.
        """

        # Update channel purpose
        channel_info = self.get_channel_info(channel_id, is_private)

        if channel_info:
            try:
                purpose = json.loads(channel_info["channel"]["purpose"]["value"])
                purpose["name"] = new_name

                self.set_purpose(channel_id, json.dumps(purpose), is_private)
            except JSONDecodeError:
                log.error(f"Failed to decode {channel_info}")

    def post_message(self, channel_id, text, timestamp="", parse="full", user_id=None):
        """
        Post a message in a given channel.
        channel_id can also be a user_id for private messages.
        Add timestamp for replying to a specific message.
        """

        try:
            self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                as_user=True,
                parse=parse,
                thread_ts=timestamp,
            )
        except SlackApiError as e:
            log.debug(e)
            if user_id is not None:
                self.client.chat_postMessage(
                    channel=user_id,
                    text=text,
                    as_user=True,
                    parse=parse,
                    thread_ts=timestamp,
                )

    def post_message_with_react(
            self, channel_id, text, reaction, parse="full", user_id=None
    ):
        """Post a message in a given channel and add the specified reaction to it."""

        result = self.client.chat_postMessage(
            channel=channel_id,
            text=text,
            as_user=True,
            parse=parse,
        )

        try:
            if result["ok"]:
                self.client.reactions_add(
                    channel=channel_id,
                    name=reaction,
                    timestamp=result["ts"],
                )
        except SlackApiError as e:
            log.warning(e)

    def get_message(self, channel_id, timestamp):
        """Retrieve a message from the channel with the specified timestamp."""

        return self.client.conversations_history(
            channel=channel_id,
            latest=timestamp,
            count=1,
            inclusive=True,
        )

    def update_message(self, channel_id, msg_timestamp, text, parse="full"):
        """Update a message, identified by the specified timestamp with a new text."""

        self.client.chat_update(
            channel=channel_id,
            text=text,
            ts=msg_timestamp,
            as_user=True,
            parse=parse,
        )

    def get_channels(self, types, next_cursor=None):
        """Recursively fetch channels, until there are no more to be fetched."""

        types = [types] if type(types) != list else types
        response = self.client.conversations_list(types=types, cursor=next_cursor)
        channels = response["channels"]
        next_cursor = response["response_metadata"]["next_cursor"]
        if not next_cursor:
            return channels
        else:
            return channels + self.get_channels(types, next_cursor)

    def get_all_channels(self):
        """Fetch all channels."""

        return self.get_channels(["public_channel", "private_channel"])

    def get_channel_by_name(self, name):
        """Fetch a channel with a given name."""

        channels = self.get_all_channels()
        for channel in channels:
            if channel["name"] == name:
                return channel

    def get_public_channels(self):
        """Fetch all public channels."""

        return self.get_channels("public_channel")

    def get_private_channels(self):
        """Fetch all private channels in which the user participates."""

        return self.get_channels("private_channel")

    def archive_channel(self, channel_id):
        """Archive a channel"""

        return self.client.conversations_archive(channel=channel_id)

    def archive_private_channel(self, channel_id):
        """Archive a private channel"""

        return self.client.conversations_archive(channel=channel_id)

    def archive_public_channel(self, channel_id):
        """Archive a public channel"""

        return self.client.conversations_archive(channel=channel_id)

    def add_reminder_hours(self, user, msg, offset):
        """Add a reminder with a given text for the specified user."""

        return self.client.reminders_add(
            text=msg, time="in {} hours".format(offset), user=user
        )

    def get_reminders(self):
        """Retrieve all reminders created by the bot."""

        return self.client.reminders_list()

    def remove_reminder(self, reminder_id):
        return self.client.reminders_delete(reminder=reminder_id)

    def remove_reminders_by_text(self, text):
        """Remove all reminders that contain the specified text."""
        reminders = self.get_reminders()

        if reminders and "reminders" in reminders:
            for reminder in reminders["reminders"]:
                if text in reminder["text"]:
                    self.remove_reminder(reminder["id"])
