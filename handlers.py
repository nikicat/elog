import threading
import queue
import socket
import urllib.request
import urllib.error
import json
import logging
import datetime
import time


##### Private objects #####
_logger = logging.getLogger(__name__)


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
                url: http://example.com/9200
                index: log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d}
                doctype: gns2
            ...

        Required arguments:
            url
            index
            doctype

        Optional arguments:
            time_field    -- Timestamp field name
            time_format   -- Timestamp format
            queue_size    -- The maximum size of the send queue, after which the caller thread is blocked
            bulk_size     -- Number of messages in one session
            retries       -- If the bulk will not be sent to N times, it will be lost
            retries_sleep -- Delay between attempts to send
            url_timeout   -- Socket timeout
            log_timeout   -- Maximum waiting time of sending

        The class does not use any formatters.
    """

    def __init__(self, **kwargs):
        logging.Handler.__init__(self)
        self._time_field = kwargs.pop("time_field", "time")
        self._sender = _Sender(**kwargs)
        self._sender.start()


    ### Public ###

    def emit(self, record):
        # Formatters are not used
        self._sender.send(self._make_message(record))


    ### Private ###

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


##### Private classes #####
class _Sender(threading.Thread):
    def __init__(
            self,
            url,
            index,
            doctype,
            time_format="%s",
            queue_size=512,
            bulk_size=512,
            retries=5,
            retries_sleep=1,
            url_timeout=socket._GLOBAL_DEFAULT_TIMEOUT, # pylint: disable=W0212
            log_timeout=5,
        ):
        threading.Thread.__init__(self)

        self._url = url
        self._index = index
        self._doctype = doctype
        self._time_format = time_format
        self._bulk_size = bulk_size
        self._retries = retries
        self._retries_sleep = retries_sleep
        self._url_timeout = url_timeout
        self._log_timeout = log_timeout

        self._queue = queue.Queue(queue_size)


    ### Public ###

    def send(self, msg):
        self._queue.put(msg)


    ### Override ###

    def run(self):
        while True:
            items = []
            try:
                timeout = self._log_timeout
                while len(items) < self._bulk_size:
                    start = time.time()
                    items.append(self._queue.get(timeout=timeout))
                    timeout -= time.time() - start
            except queue.Empty:
                pass # Send data by timeout

            if len(items) != 0:
                self._send_messages(items)
                items = []

            if not threading._shutdown.__self__.is_alive(): # pylint: disable=W0212
                # After sending a message in the log, we get the main thread object
                # and check if he is alive. If not - stop sending logs.
                break


    ### Private ###

    def _send_messages(self, messages):
        bulk = ""
        for msg in messages:
            bulk += "{}\n{}\n".format(
                self._json_dumps(self._get_to(msg)),
                self._json_dumps(msg),
            )
        request = urllib.request.Request(self._url+"/_bulk", data=bulk.encode())
        self._send_request(request)

    def _send_request(self, request):
        retries = self._retries_sleep
        while True:
            try:
                urllib.request.build_opener().open(request, timeout=self._url_timeout)
                break
            except (socket.timeout, urllib.error.URLError):
                if retries == 0:
                    # FIXME: log
                    break
                retries -= 1
                time.sleep(self._retries_sleep)

    def _json_dumps(self, obj):
        return json.dumps(obj, cls=_DatetimeEncoder, time_format=self._time_format)

    def _get_to(self, msg):
        return {
            "index": {
                "_index": self._index.format(**msg),
                "_type":  self._doctype.format(**msg),
            },
        }

class _DatetimeEncoder(json.JSONEncoder):
    def __init__(self, time_format, *args, **kwargs):
        json.JSONEncoder.__init__(self, *args, **kwargs)
        self._time_format = time_format

    def default(self, obj): # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return format(obj, self._time_format)
        return json.JSONEncoder.default(self, obj)

