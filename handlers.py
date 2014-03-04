import socket
import urllib.request
import json
import logging
import time

from . import formatters


##### Public classes #####
class ElasticHandler(logging.Handler):
    """
        Example config:
            ...
            elastic:
                level: DEBUG
                class: elog.handlers.ElasticHandler
                formatter: dict
                url: http://example.com:9200/log-%Y-%m-%d/mdevaev-gns-elog2
            ...

        URL components:
            example.com:9200 -- host/port
            log-%Y-%m-%d -- index
            gns-elog -- doctype

        Requires elog.formatters.DictFormatter (or his child class) for working.
    """

    def __init__(self, url, timeout=socket._GLOBAL_DEFAULT_TIMEOUT): # pylint: disable=W0212
        logging.Handler.__init__(self)
        self._url = url
        self._timeout = timeout

    def setFormatter(self, fmt):
        if not isinstance(fmt, formatters.DictFormatter):
            raise RuntimeError("{} requires a DictFormatter".format(self.__class__.__name__))
        self.formatter = fmt

    def emit(self, record):
        msg = self.format(record)
        url = self._url.format(**msg)
        url = time.strftime(url, time.gmtime(record.created))
        request = urllib.request.Request(url, data=json.dumps(msg).encode())
        urllib.request.build_opener().open(request, timeout=self._timeout)

