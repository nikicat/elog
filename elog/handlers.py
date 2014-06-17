import sys
import threading
import queue
import socket
import requests
import requests.exceptions
import json
import logging
import traceback
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
                url: http://example.com:9200
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
            session_timeout -- Close the connection if there were no messages during this time (5).
            url_timeout     -- Socket timeout.
            blocking        -- Block logging, if the queue is full, (False).

        The class does not use any formatters.
    """
    def __init__(  # pylint: disable=R0913
            self,
            url,
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

        self._url = url
        self._index = index
        self._doctype = doctype
        self._fields = ( fields or {} )
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
                    _exc_stderr("Can't log the message: '{}'. Queue is full.".format(message))
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
        while self.continue_processing() or not self._queue.empty():
            # After sending a message in the log, we get the main thread object
            # and check if he is alive. If not - stop sending logs.
            # If the queue still have messages - process them.

            if not self._queue.empty():
                thread = threading.Thread(target=self._consume_queue, daemon=True)
                thread.start()
                thread.join()
            else:
                time.sleep(1) # FIXME: peek queue


    ### Private ###

    def _consume_queue(self):
        requests.post(self._url + "/_bulk", data=self._generate_chunks(), timeout=self._url_timeout)

    def _generate_chunks(self):
        for _ in range(self._session_size):
            try:
                message = self._queue.get(self._session_timeout)
            except queue.Empty:
                break
            data = ( "\n".join(map(self._json_dumps, [
                    {  # Data metainfo: index, doctype
                        "index": {
                            "_index": self._index.format(**message),
                            "_type":  self._doctype.format(**message),
                        },
                    },
                    message,  # Log record
                ])) + "\n" ).encode()
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


##### Private methods #####
def _exc_stderr(msg):
    print(msg, file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
