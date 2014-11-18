import sys
import threading
import traceback
import queue
import logging
import datetime
import os

import elasticsearch
import elasticsearch.helpers


debug = False


def log(message):
    if debug:
        warning(message)


def warning(message):
    print("elog[{pid}]: {msg}".format(pid=os.getpid(), msg=message), file=sys.stderr)


class ElasticHandler(logging.Handler):
    """
        Example config:
            ...
            elastic:
                level: DEBUG
                class: elog.handlers.ElasticHandler
                time_field: "@timestamp"
                hosts:
                    host: example.com
                    port: 9200
                index: log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d}
                doctype: elog
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
            hosts
            index
            doctype

        Optional arguments:
            fields          -- A dictionary with mapping LogRecord fields to ElasticSearch fields (None).
            time_field      -- Timestamp field name ("time").
            queue_size      -- The maximum size of the send queue, after which the caller thread is blocked (2048).
            bulk_size       -- Number of messages per bulk (512).
            blocking        -- Block logging, if the queue is full, (False).

        The class does not use any formatters.
    """
    def __init__(  # pylint: disable=R0913
        self,
        hosts,
        index,
        doctype,
        fields=None,
        time_field="time",
        queue_size=2048,
        bulk_size=512,
        max_retries=sys.maxsize,
        blocking=False
    ):
        logging.Handler.__init__(self)

        self._index = index
        self._doctype = doctype
        self._fields = fields
        self._time_field = time_field
        self._bulk_size = bulk_size
        self._blocking = blocking
        self._elasticsearch = elasticsearch.Elasticsearch(
            hosts=hosts,
            retry_on_timeout=True,
            max_retries=max_retries,
            connection_class=elasticsearch.RequestsHttpConnection,
        )

        self._queue = queue.Queue(queue_size)
        self._thread = None

    def emit(self, record):
        # Formatters are not used.
        # While the application works - we accept the message to send.
        if self._fields is not None:
            message = {
                name: getattr(record, item)
                for (name, item) in self._fields.items()
                if hasattr(record, item)
            }
        else:
            message = vars(record).copy()
        message[self._time_field] = datetime.datetime.utcfromtimestamp(record.created)

        if not self._blocking:
            try:
                self._queue.put(message, block=False)
                if not self._queue.empty() and (self._thread is None or not self._thread.is_alive()):
                    log("send loop starting")
                    self._thread = threading.Thread(target=self._sendloop)
                    self._thread.daemon = True
                    self._thread.start()
            except queue.Full:
                warning("queue is full, dropping message: {}".format(message))
        else:
            self._queue.put(message)

    def close(self):
        log("closing handler")
        self._queue.put(None, block=True)
        self._thread.join()
        super().close()
        log("handler closed")

    def _sendloop(self):
        log("send loop started")
        running = True
        while running:
            # After sending a message in the log, we get the main thread object
            # and check if he is alive. If not - stop sending logs.
            # If the queue still have messages - process them.

            try:
                def convert(message):
                    return {
                        "_index": self._index.format(**message),
                        "_type":  self._doctype.format(**message),
                        "_source": message,
                    }

                def generate_chunks():
                    nonlocal running
                    log("chunk generation starting")
                    # First time block on waiting to avoid busy polling
                    item = self._queue.get()
                    if item is None:
                        running = False
                        return
                    yield convert(item)

                    # Then try to consume as many as possible
                    while not self._queue.empty():
                        item = self._queue.get_nowait()
                        if item is None:
                            running = False
                            return
                        yield convert(item)
                    log("chunk generation stopped")

                log("streaming bulk starting. running={}".format(running))
                successed, errors = elasticsearch.helpers.bulk(
                    client=self._elasticsearch,
                    actions=generate_chunks(),
                    chunk_size=self._bulk_size,
                )
                log("streaming bulk stopped. successed: {}, errors: {}".format(successed, errors))
            except Exception:
                warning("bulk request error")
                traceback.print_exc(file=sys.stderr)
        log("send loop stopped")
