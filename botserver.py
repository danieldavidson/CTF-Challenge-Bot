import json
import os
import threading

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from bottypes.invalid_console_command import InvalidConsoleCommand
from handlers import handler_factory
from util.loghandler import log
from util.slack_wrapper import SlackWrapper


class BotServer:
    # Global lock for locking global data in bot server
    thread_lock = threading.Lock()
    user_list = {}

    def __init__(self):
        log.debug("Parse config file and initialize threading...")
        self.running = False
        self.config = {}
        self.load_config()
        self.slack_wrapper = SlackWrapper()
        self.init_bot_data()

    def lock(self):
        """Acquire global lock for working with global (not thread-safe) data."""
        BotServer.thread_lock.acquire()

    def release(self):
        """Release global lock after accessing global (not thread-safe) data."""
        BotServer.thread_lock.release()

    def quit(self):
        """Inform the application that it is quitting."""
        log.info("Shutting down")
        self.running = False

    def load_config(self):
        """Load configuration file."""
        self.lock()
        with open("./config/config.json") as f:
            self.config = json.load(f)
        self.release()

    def get_config_option(self, option):
        """Get configuration option."""
        self.lock()
        result = self.config.get(option)
        self.release()

        return result

    def set_config_option(self, option, value):
        """Set configuration option."""
        self.lock()

        try:
            if option in self.config:
                self.config[option] = value
                log.info("Updated configuration: %s => %s", option, value)

                with open("./config/config.json", "w") as f:
                    json.dump(self.config, f, indent=4)
            else:
                raise InvalidConsoleCommand(
                    "The specified configuration option doesn't exist: {}".format(
                        option
                    )
                )
        finally:
            self.release()

    def parse_slack_message(self, msg):
        """
        Return (message, channel, ts, user) if the message is directed at the bot,
        otherwise return (None, None, None, None).
        """
        return (
            msg.get("command").strip("/") if msg.get("command") else None,
            msg.get("text"),
            msg.get("channel_id"),
            msg.get("thread_ts") if "thread_ts" in msg else msg.get("ts"),
            msg.get("user_id"),
        )

    def init_bot_data(self):
        """
        Fetches the bot user information such as
        bot_name, bot_id and bot_at.
        """
        self.running = True

        # Might even pass the bot server for handlers?
        log.info("Initializing handlers...")
        handler_factory.initialize(self.slack_wrapper, self)

    def handle_message(self, body):
        command, params, channel, time_stamp, user = self.parse_slack_message(body)

        try:
            log.debug("Received bot command : %s %s (%s)", command, params, channel)
            handler_factory.process(self.slack_wrapper, command, params, time_stamp, channel, user)
        except Exception as e:
            log.exception(e)


app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

botserver = BotServer()


@app.command("/admin")
@app.command("/bot")
@app.command("/ctf")
@app.command("/syscalls")
def handle_message(ack, body):
    ack()
    botserver.handle_message(body)


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
