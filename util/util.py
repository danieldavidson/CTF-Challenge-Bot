import json
import re


#######
# Helper functions
#######


def load_json(string):
    """
    Return a JSON object based on its string representation.
    Return None if the string isn't valid JSON.
    """
    try:
        json_object = json.loads(string)
    except ValueError:
        return None
    return json_object


def transliterate(string):
    """
    Converts ascii characters to a unicode
    equivalent.
    """
    mapping = {
        "a": "ɑ",  # \xc9\x91
        "A": "А",  # \xd0\x90
        "e": "е",  # \xd0\xb5
        "E": "Е",  # \xd0\x95
        "i": "і",  # \xd1\x96
        "I": "І",  # \xd0\x86
        "o": "о",  # \xd0\xbe
        "O": "О",  # \xd0\x9e
        "u": "υ",  # \xcf\x85
        "U": "υ",  # \xcf\x85
    }

    return "".join([mapping[c] if c in mapping else c for c in string])


#######
# Database manipulation
#######


def cleanup_reminders(slack_wrapper, handler_factory, ctf):
    """Remove existing reminders for this ctf, if reminder handling is configured."""
    reminder_offset = handler_factory.botserver.get_config_option(
        "archive_ctf_reminder_offset"
    )

    if not reminder_offset:
        # no reminder handling configured, bail out
        return

    # To save space in channel purpose, we'll just search the reminders by creation text
    slack_wrapper.remove_reminders_by_text("CTF {} - ".format(ctf.name))


def parse_user_id(user_id):
    """
    Parse a user_id, removing possible @-notation and make sure it's uppercase.
    """
    if user_id.startswith("<@") and user_id.endswith(">"):
        return user_id[2:-1].upper()

    return user_id.upper()


def resolve_user_by_user_id(slack_wrapper, user_id):
    """
    Resolve a user id to a user object.
    """
    return slack_wrapper.get_member(parse_user_id(user_id))


def get_display_name(member):
    return get_display_name_from_user(member["user"])


def get_display_name_from_user(user):
    if "profile" in user:
        if user["profile"]["display_name"]:
            return user["profile"]["display_name"]

        if user["profile"]["real_name"]:
            return user["profile"]["real_name"]

    if "real_name" in user:
        if user["real_name"]:
            return user["real_name"]

    if "name" in user:
        if user["name"]:
            return user["name"]

    return user["id"]


def is_valid_name(name):
    if re.match(r"^[\w\-_]+$", name):
        return True
    return False
