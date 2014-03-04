import logging
import time


##### Public classes #####
class DictFormatter(logging.Formatter):
    """
        Example config:
            ...
            dict:
                (): elog.formatters.DictFormatter
                time_field: "@timestamp"
                time_format: "%Y-%m-%dT%H:%M:%S.{msecs}"
            ...
    """

    def __init__(self, time_field=None, time_format=None):
        logging.Formatter.__init__(self)
        self._time_field = time_field
        self._time_format = time_format

    def format(self, record):
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
                ("extra",     "extra"), # Custom fields
            )
            if hasattr(record, item)
        }
        msg["msecs"] = int(msg["msecs"])
        if record.exc_info is not None:
            msg["traceback"] = self.formatException(record.exc_info)
        else:
            msg["traceback"] = None
        if self._time_field is not None:
            msg[self._time_field] = self._time_format.format(**msg)
            msg[self._time_field] = time.strftime(msg[self._time_field], time.gmtime(record.created))
        return msg

