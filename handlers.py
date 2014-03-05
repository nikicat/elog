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
class ElasticHandler(logging.Handler, threading.Thread):
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
    def __init__(
            self,
            url,
            index,
            doctype,
            time_field="time",
            time_format="%s",
            queue_size=512,
            bulk_size=512,
            retries=5,
            retries_sleep=1,
            url_timeout=socket._GLOBAL_DEFAULT_TIMEOUT, # pylint: disable=W0212
            log_timeout=5,
        ):
        logging.Handler.__init__(self)
        threading.Thread.__init__(self)

        self._url = url
        self._index = index
        self._doctype = doctype
        self._time_field = time_field
        self._time_format = time_format
        self._bulk_size = bulk_size
        self._retries = retries
        self._retries_sleep = retries_sleep
        self._url_timeout = url_timeout
        self._log_timeout = log_timeout

        self._queue = queue.Queue()
        self.start()


    ### Public ###

    def emit(self, record):
        # Formatters are not used
        if self._is_main_thread_alive():
            # While the application works - we accept the message to send
            self._queue.put(self._make_message(record))


    ### Override ###

    def run(self):
        while self._is_main_thread_alive() or not self._queue.empty():
            # After sending a message in the log, we get the main thread object
            # and check if he is alive. If not - stop sending logs.
            # If the queue still have messages - process them.

            last_send = 0
            items = []
            try:
                if self._is_main_thread_alive():
                    # Consider the last sending time
                    timeout = max(self._log_timeout - last_send, 0)
                else:
                    # If application is dead, quickly dismantle the remaining queue and break the cycle.
                    timeout = 0

                while len(items) < self._bulk_size:
                    start = time.time()
                    items.append(self._queue.get(timeout=max(timeout, 0)))
                    self._queue.task_done()
                    timeout -= time.time() - start
            except queue.Empty:
                pass # Send data by timeout

            if len(items) != 0:
                start = time.time()
                self._send_messages(items)
                last_send = time.time() - start


    ### Private ###

    def _is_main_thread_alive(self):
        return threading._shutdown.__self__.is_alive() # pylint: disable=W0212

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

    def _send_messages(self, messages):
        # See for details:
        #   http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/docs-bulk.html
        bulks = []
        for msg in messages:
            bulks.append({ # Data metainfo: index, doctype
                    "index": {
                        "_index": self._index.format(**msg),
                        "_type":  self._doctype.format(**msg),
                    },
                })
            bulks.append(msg) # Log record
        data = ("\n".join(map(self._json_dumps, bulks)) + "\n").encode()
        request = urllib.request.Request(self._url+"/_bulk", data=data)
        self._send_request(request)

    def _send_request(self, request):
        retries = self._retries
        while True:
            try:
                urllib.request.build_opener().open(request, timeout=self._url_timeout)
                break
            except (socket.timeout, urllib.error.URLError):
                if retries == 0:
                    _logger.exception("ElasticHandler could not send %d log records after %d retries", self._bulk_size, self._retries)
                    break
                retries -= 1
                time.sleep(self._retries_sleep)

    def _json_dumps(self, obj):
        return json.dumps(obj, cls=_DatetimeEncoder, time_format=self._time_format)

class _DatetimeEncoder(json.JSONEncoder):
    def __init__(self, time_format, *args, **kwargs):
        json.JSONEncoder.__init__(self, *args, **kwargs)
        self._time_format = time_format

    def default(self, obj): # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return format(obj, self._time_format)
        return repr(obj) # Convert non-encodable objects to string

