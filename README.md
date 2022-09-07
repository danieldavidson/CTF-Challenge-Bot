# CTF Challenge Bot

The CTF challenge bot is a Slack app that helps keep your team communication organized during CTF events.

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
/ctf addchallenge <challenge_name> [challenge_category]         (Adds a new challenge for current ctf)
/ctf addcreds <ctf_user> <ctf_pw> [ctf_url]                     (Add credentials for current ctf)
/ctf addctf <ctf_name> [long_name]                              (Adds a new ctf)
/ctf archivectf                                                 (Archive the challenges of a ctf)
/ctf endctf                                                     (Mark a ctf as ended, but not archive it directly)
/ctf populate                                                   (Invite all absent members of the CTF into the challenge channel)
/ctf reload                                                     (Reload ctf information from slack)
/ctf removetag [challenge_name] <tag> [..<tag>]                 (Remove a tag from a challenge)
/ctf renamechallenge <old_challenge_name> <new_challenge_name>  (Renames a challenge)
/ctf renamectf <old_ctf_name> <new_ctf_name>                    (Renames a ctf)
/ctf showcreds                                                  (Show credentials for current ctf)
/ctf signup [ctf_name]                                          (Join a CTF)
/ctf solve [challenge_name] [support_member]                    (Mark a challenge as solved)
/ctf status                                                     (Show the status for all ongoing ctf's)
/ctf tag [challenge_name] <tag> [..<tag>]                       (Adds a tag to a challenge)
/ctf unsolve [challenge_name]                                   (Remove solve of a challenge)
/ctf workon [challenge_name]                                    (Show that you're working on a challenge)

/syscalls available                                             (Shows the available syscall architectures)
/syscalls show <arch> <syscall name/syscall id>                 (Show information for a specific syscall)

/bot intro                                                      (Show an introduction message for new members)
/bot ping                                                       (Ping the bot)
/bot sysinfo                                                    (Show system information)
/bot version                                                    (Show git information about the running version of the bot)

/admin add_admin <user_id>                                      (Add a user to the admin user group)
/admin as <@user> <command>                                     (Execute a command as another user)
/admin maintenance                                              (Toggle maintenance mode)
/admin remove_admin <user_id>                                   (Remove a user from the admin user group)
/admin show_admins                                              (Show a list of current admin users)
```

## App installation

1. Navigate to https://api.slack.com/apps?new_app=1
2. Create an app.
3. From an app manifest.
4. Pick a workspace for your bot.
5. Copy the contents of [manifest.yml](./manifest.yml) in to the window.
6. Create.
7. Install to workspace.

## Server setup

1. Follow these steps for [setting your app credentials](https://api.slack.com/start/building/bolt-python#credentials).
2. Follow this step for [setting your app-level token](https://api.slack.com/apis/connections/socket#sdks) for Socket Mode.
3. Copy `config/config.json.template` to `config/config.json`.
4. Add your user id (slack id, not the username) to `admin_users` group in `config/config.json`
5. `docker-compose up -d opensearch-node1`
6. `docker-compose up ctfbot`

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
