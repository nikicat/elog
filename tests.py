import datetime
import logging.config
import unittest
import requests
import time
from requests.compat import urljoin


ELASTIC_SERVER = "%%_FIX_ME_%%"


class Tests(unittest.TestCase):

    def setUp(self):
        self.config = {
            "version": 1,
            "handlers":
                {"elastic":
                     {
                         "level": "DEBUG",
                         "class": "elog.handlers.ElasticHandler",
                         "time_field": "@timestamp",
                         "time_format": "%Y-%m-%dT%H:%M:%S.%f",
                         "url": ELASTIC_SERVER,
                         "index": "log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d}",
                         "doctype": "test",
                         "fields":
                             {"logger": "name",
                              "level": "levelname",
                              "msg": "msg",
                              "args": "args",
                              "file": "pathname",
                              "line": "lineno",
                              "pid": "process"}
                     },
                },
            'loggers': {"Test": {
                'level': 'DEBUG',
                'handlers': ['elastic']
            }}
        }

        logging.config.dictConfig(self.config)
        self.logger = logging.getLogger("Test")
        self.index_suffix = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d')

    def get_elastic_records(self, msg):
        resp = requests.get(urljoin(ELASTIC_SERVER, 'log-{suffix}/_search'.format(suffix=self.index_suffix)),
                            params={'q': 'msg:{msg}'.format(msg=msg)})
        return resp.json()['hits']

    def test_record_created(self):
        msg = "test_%s" % time.time()
        self.logger.debug(msg)
        time.sleep(10)
        hits = self.get_elastic_records(msg)
        self.assertEqual(hits['total'], 1)
