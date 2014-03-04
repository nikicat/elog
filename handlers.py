import socket
import urllib.request
import json
import logging
import datetime


##### Public classes #####
class ElasticHandler(logging.Handler):
    """
        Example config:
            ...
            elastic:
                level: DEBUG
                class: elog.handlers.ElasticHandler
                url: http://example.com:9200/log-{utc:%Y}-{utc:%m}-{utc:%d}/gns2
                time_field: "@timestamp"
                time_format: "{utc:%Y}-{utc:%m}-{utc:%d}T{utc:%H}:{utc:%M}:{utc:%S}.{utc:%f}"
            ...

        URL components:
            example.com:9200 -- host/port
            log-{utc:%Y}-{utc:%m}-{utc:%d} -- index
            gns2 -- doctype

        The class does not use any formatters.
    """

    def __init__(self, url, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, time_field=None, time_format=None): # pylint: disable=W0212
        logging.Handler.__init__(self)
        self._url = url
        self._timeout = timeout
        self._time_field = time_field
        self._time_format = time_format


    def emit(self, record):
        # Formatters are not used
        msg = self._make_message(record)
        url = self._url.format(**msg)
        del msg["utc"] # Remove the inner object utc
        request = urllib.request.Request(url, data=json.dumps(msg).encode())
        urllib.request.build_opener().open(request, timeout=self._timeout)

    def _make_message(self, record):
        msg = {
            name: getattr(record, item)
            for (name, item) in (
                ("time",      "created"),
                ("msecs",     "msecs"),
                ("logger",    "name"),
                ("level",     "levelname"),
                ("level_no",  "levelno"),
                ("msg",       "msg"),
                ("args",      "args"),
                ("file",      "pathname"),
                ("line",      "lineno"),
                ("func",      "funcName"),
                ("pid",       "process"),
                ("process",   "processName"),
                ("tid",       "tid"), # Linux TID (from elog.records.LogRecord)
                ("thread",    "threadName"),
                ("thread_id", "thread"), # Python-specific thread id
                ("exc_text",  "exc_text"), # Text exception
                ("extra",     "extra"), # Custom fields
            )
            if hasattr(record, item)
        }
        msg["utc"] = datetime.datetime.utcfromtimestamp(record.created) # Only for config placeholders
        if self._time_field is not None:
            msg[self._time_field] = self._time_format.format(**msg)
        return msg

