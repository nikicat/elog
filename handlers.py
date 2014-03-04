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

        Requires formatter that returns dict instead of string.
    """

    def __init__(self, url, timeout=socket._GLOBAL_DEFAULT_TIMEOUT): # pylint: disable=W0212
        logging.Handler.__init__(self)
        self._url = url
        self._timeout = timeout

    def emit(self, record):
        msg = self.format(record)
        assert isinstance(msg, dict)
        url = self._url.format(**msg)
        url = time.strftime(url, time.gmtime(record.created))
        request = urllib.request.Request(url, data=json.dumps(msg).encode())
        urllib.request.build_opener().open(request, timeout=self._timeout)

