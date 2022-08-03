#!/usr/bin/python
import logging
import os

CONSOLELOGLEVEL = logging.DEBUG
LOGDIR = "logs"
LOGPREFIX = "bot"

# Someone fix this ;)
# Didn't get 'log' available for other modules...

log = logging.getLogger("log")

log.setLevel(logging.DEBUG)

# Error log file
if not os.path.exists(LOGDIR):
    os.makedirs(LOGDIR)

elog = logging.FileHandler(os.path.join(LOGDIR, "{}_error.log".format(LOGPREFIX)))
elog.setLevel(logging.ERROR)

# Console logging
clog = logging.StreamHandler()
clog.setLevel(CONSOLELOGLEVEL)

# formatter = logging.Formatter("%(asctime)s - %(module)-20s - %(message)s")
formatter = logging.Formatter("%(levelname)s -- %(asctime)-15s -- %(filename)s:%(funcName)s:%(lineno)d -- %(message)s")

clog.setFormatter(formatter)
elog.setFormatter(formatter)

log.addHandler(elog)
log.addHandler(clog)
