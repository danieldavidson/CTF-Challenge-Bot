# CTF Challenge Bot

The CTF challenge bot is a helper tool to be used during CTF events through the Slack platform.

## Features

Main features :
- Tracking CTFs
- Tracking CTF challenges
- Tracking member participation in challenges
- Displaying announcements upon solving a challenge

Secondary features :
- Syscall table for arm, armthumb, x64 and x86

## Usage

```
/ctf addctf <ctf_name>                                          (Adds a new ctf)
/ctf addchallenge <challenge_name> <challenge_category>         (Adds a new challenge for current ctf)
/ctf tag [<challenge_name>] <tag> [..<tag>]                     (Adds a tag to a challenge)
/ctf workon [challenge_name]                                    (Show that you're working on a challenge)
/ctf status                                                     (Show the status for all ongoing ctf's)
/ctf solve [challenge_name] [support_member]                    (Mark a challenge as solved)
/ctf renamechallenge <old_challenge_name> <new_challenge_name>  (Renames a challenge)
/ctf renamectf <old_ctf_name> <new_ctf_name>                    (Renames a ctf)
/ctf reload                                                     (Reload ctf information from slack)
/ctf removetag [<challenge_name] <tag> [..<tag>]                (Remove a tag from a challenge)
/ctf archivectf                                                 (Archive the challenges of a ctf)
/ctf addcreds <ctf_user> <ctf_pw> [ctf_url]                     (Add credentials for current ctf)
/ctf showcreds                                                  (Show credentials for current ctf)
/ctf unsolve [challenge_name]                                   (Remove solve of a challenge)

/syscalls available                                             (Shows the available syscall architectures)
/syscalls show <arch> <syscall name/syscall id>                 (Show information for a specific syscall)

/bot ping                                                       (Ping the bot)
/bot intro                                                      (Show an introduction message for new members)
/bot version                                                    (Show git information about the running version of the bot)

/admin show_admins                                              (Show a list of current admin users)
/admin add_admin <user_id>                                      (Add a user to the admin user group)
/admin remove_admin <user_id>                                   (Remove a user from the admin user group)
/admin as <@user> <command>                                     (Execute a command as another user)
```

## Installation

1. Navigate to https://api.slack.com/apps?new_app=1
2. Create an app.
3. From an app manifest.
4. Pick a workspace for your bot.
5. Copy the contents of [manifest.yml](./manifest.yml) in to the window.
6. Create.
7. Install to workspace.

## Setup

1. Follow these steps for [setting your app credentials](https://api.slack.com/start/building/bolt-python#credentials).
2. Follow this step for [setting your app-level token](https://api.slack.com/apis/connections/socket#sdks) for Socket Mode.
3. Copy `config/config.json.template` to `config/config.json`.
6. Add your user id (slack id, not the username) to `admin_users` group in `config/config.json`
9. `docker build -t ctf-challenge-bot .`
10. `docker run -it --rm --name live-ctf-challenge-bot ctf-challenge-bot`

## Development

1. Copy `config/config.json.template` to `config/config.json`
2. Fill the API token and bot name in the config.json file.
3. Create a virtual env: `python3 -m venv .venv`
4. Enter the virtual env: `source .venv/bin/activate`
5. Install requirements: `pip install -r requirements.txt`

## Archive reminder

To enable archive reminders set an offset (in hours) in `config/config.json` for `archive_ctf_reminder_offset`. Clear or remove the setting to disable reminder handling.

If active, the bot will create a reminder for every bot admin on `/endctf` to inform him, when the ctf was finished for the specified time and it should be archived.

Example (for being reminded one week after the ctf has finished):
```
{
    ...
    "archive_ctf_reminder_offset" : "168"
}
```

## Log command deletion

To enable logging of deleting messages containing specific keywords, set `delete_watch_keywords` in `config/config.json` to a comma separated list of keywords. 
Clear or remove the setting to disable deletion logging.

Example
```
{
    "delete_watch_keywords" : "workon, reload, endctf"
}
