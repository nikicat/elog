import socket
import platform
import logging
import functools
import time


##### Public classes #####
class LogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        logging.LogRecord.__init__(self, *args, **kwargs)
        self.fqdn = _cached_getfqdn(int(time.time() / 60))  # Cached value FQDN, updated every minute
        self.node = platform.uname()[1]  # Nodename from uname


##### Private methods #####
@functools.lru_cache(1)  # Python <= 3.3 -- pylint: disable=W0613
def _cached_getfqdn(every):  # Python >= 3.4 -- pylint: disable=W0613
    return socket.getfqdn()
