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
                time_field: "@timestamp"
                time_format: "%Y-%m-%dT%H:%M:%S.%f"
                url: http://example.com:9200/log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d}/gns2
            ...

        URL components:
            example.com:9200 -- host/port
            log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d} -- index
            gns2 -- doctype

        The class does not use any formatters.
    """

    def __init__(self, url, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, time_field="time", time_format="%s"): # pylint: disable=W0212
        logging.Handler.__init__(self)
        self._url = url
        self._timeout = timeout
        self._time_field = time_field
        self._time_format = time_format


    def emit(self, record):
        # Formatters are not used
        msg = self._make_message(record)
        url = self._url.format(**msg)
        msg_json = json.dumps(msg, cls=_DatetimeEncoder, time_format=self._time_format)
        request = urllib.request.Request(url, data=msg_json.encode())
        urllib.request.build_opener().open(request, timeout=self._timeout)

    def _make_message(self, record):
        msg = {
            name: getattr(record, item)
            for (name, item) in (
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
        msg[self._time_field] = datetime.datetime.utcfromtimestamp(record.created)
        return msg

class _DatetimeEncoder(json.JSONEncoder):
    def __init__(self, time_format, *args, **kwargs):
        json.JSONEncoder.__init__(self, *args, **kwargs)
        self._time_format = time_format

    def default(self, obj): # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return format(obj, self._time_format)
        return json.JSONEncoder.default(self, obj)

