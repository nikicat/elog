import sys
import threading
import itertools
import queue
import socket
import requests
import json
import logging
import datetime
import time


##### Private objects #####
_logger = logging.getLogger(__name__)


##### Public classes #####
class ElasticHandler(logging.Handler, threading.Thread):  # pylint: disable=R0902,R0904
    """
        Example config:
            ...
            elastic:
                level: DEBUG
                class: elog.handlers.ElasticHandler
                time_field: "@timestamp"
                time_format: "%Y-%m-%dT%H:%M:%S.%f"
                urls: [http://example.com:9200]
                index: log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d}
                doctype: gns2
                fields:
                    logger:    name
                    level:     levelname
                    msg:       msg
                    args:      args
                    file:      pathname
                    line:      lineno
                    pid:       process
            ...

        Required arguments:
            url
            index
            doctype

        Optional arguments:
            fields          -- A dictionary with mapping LogRecord fields to ElasticSearch fields (None).
            time_field      -- Timestamp field name ("time").
            time_format     -- Timestamp format ("%s").
            queue_size      -- The maximum size of the send queue, after which the caller thread is blocked (512).
            session_size    -- Number of messages per session (512).
            session_timeout -- Close the connection if there were no messages during this time (5 seconds).
            url_timeout     -- Socket timeout (default socket._GLOBAL_DEFAULT_TIMEOUT, in seconds).
            blocking        -- Block logging, if the queue is full, (False).

        The class does not use any formatters.
    """
    def __init__(  # pylint: disable=R0913
            self,
            urls,
            index,
            doctype,
            fields=None,
            time_field="time",
            time_format="%s",
            queue_size=512,
            session_size=512,
            session_timeout=5,
            url_timeout=socket._GLOBAL_DEFAULT_TIMEOUT,  # pylint: disable=W0212
            blocking=False,
        ):
        logging.Handler.__init__(self)
        threading.Thread.__init__(self)

        self._urls = itertools.cycle(urls)
        self._index = index
        self._doctype = doctype
        self._fields = (fields or {
            key: key for key in ("name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
                                 "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
                                 "relativeCreated", "thread", "threadName", "processName", "process")
        })
        self._time_field = time_field
        self._time_format = time_format
        self._session_size = session_size
        self._session_timeout = session_timeout
        self._url_timeout = url_timeout
        self._blocking = blocking

        self._queue = queue.Queue(queue_size)
        self.start()


    ### Public ###

    def emit(self, record):
        # Formatters are not used.
        # While the application works - we accept the message to send.
        if self.continue_processing():
            message = {
                name: getattr(record, item)
                for (name, item) in self._fields.items()
                if hasattr(record, item)
            }
            message[self._time_field] = datetime.datetime.utcfromtimestamp(record.created)

            if self._blocking:
                try:
                    self._queue.put(message, block=False)
                except queue.Full:
                    print("Dropping message '{}' because queue is full".format(message), file=sys.stderr)
            else:
                self._queue.put(message)

    def continue_processing(self):  # pylint: disable=R0201
        # This thread must be one of the last live threads. Usually, MainThread lives up to the
        # completion of all the rest. We need to determine when it is completed and to stop sending
        # and receiving messages. For our architecture that is enough. In other cases, you can
        # override this method.

        if hasattr(threading, "main_thread"):  # Python >= 3.4
            main_thread = threading.main_thread()  # pylint: disable=E1101
        else:  # Dirty hack for Python <= 3.3
            main_thread = threading._shutdown.__self__  # pylint: disable=W0212,E1101

        return main_thread.is_alive()


    ### Override ###

    def run(self):
        current_url = next(self._urls)
        while self.continue_processing() or not self._queue.empty():
            # After sending a message in the log, we get the main thread object
            # and check if he is alive. If not - stop sending logs.
            # If the queue still have messages - process them.

            if not self._queue.empty():
                try:
                    # http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/docs-bulk.html
                    # http://docs.python-requests.org/en/latest/user/advanced/
                    requests.post(
                        current_url + "/_bulk",
                        data=self._generate_chunks(),
                        timeout=self._url_timeout,
                    )
                except Exception:
                    _logger.exception("Bulk-request error")
                    current_url = next(self._urls)
                    time.sleep(1)
            else:
                time.sleep(1)


    ### Private ###

    def _generate_chunks(self):
        for _ in range(self._session_size):
            try:
                message = self._queue.get(timeout=self._session_timeout)
            except queue.Empty:
                break
            index = {
                # Data metainfo: index, doctype
                "index": {
                    "_index": self._index.format(**message),
                    "_type":  self._doctype.format(**message),
                },
            }
            data = "{index}\n{message}\n".format(
                index=self._json_dumps(index),
                message=self._json_dumps(message),
            ).encode()
            yield data

    def _json_dumps(self, obj):
        return json.dumps(obj, cls=_DatetimeEncoder, time_format=self._time_format)


class _DatetimeEncoder(json.JSONEncoder):
    def __init__(self, time_format, *args, **kwargs):
        json.JSONEncoder.__init__(self, *args, **kwargs)
        self._time_format = time_format

    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return format(obj, self._time_format)
        return repr(obj)  # Convert non-encodable objects to string
