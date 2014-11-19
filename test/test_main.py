import logging.config
import os
import datetime
import time

# Monkey patch time to make elasticsearch url immutable
time.time = lambda: 1416009275.201996

import pytest
import elasticsearch
from vcr import VCR

import elog.handlers


elog.handlers.debug = True
vcr = VCR(cassette_library_dir='test/fixtures/')
# Monkey patch ElasticHandler to enable VCRPy for it's requests
#elog.handlers.ElasticHandler._sendloop = vcr.use_cassette('elastichandler.yaml')(elog.handlers.ElasticHandler._sendloop)
elasticsearch_host = {'host': 'localhost', 'port': 9200}
index_pattern = ".test-log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d}"

@pytest.fixture
def logger():
    config = {
        "version": 1,
        "handlers": {
            "elastic": {
                 "level": "DEBUG",
                 "class": "elog.handlers.ElasticHandler",
                 "time_field": "@timestamp",
                 "hosts": [elasticsearch_host],
                 "index": index_pattern,
                 "doctype": "test",
                 "queue_size": 10,
             },
        },
        'loggers': {"Test": {
            'level': 'DEBUG',
            'handlers': ['elastic']
        }}
    }

    logging.config.dictConfig(config)
    return logging.getLogger("Test")


@vcr.use_cassette('elastic-fixture.yaml')
@pytest.fixture
def elastic():
    client = elasticsearch.Elasticsearch(hosts=[elasticsearch_host], connection_class=elasticsearch.RequestsHttpConnection)
    client.indices.delete(index=get_index(), ignore=404)
    return client


def get_message():
    return "test_foo_bar_baz"


@vcr.use_cassette('simple.yaml')
def test_simple(elastic, logger):
    msg = get_message()
    logger.debug(msg)
    check(elastic, msg)


def get_index():
    return index_pattern.format(**{'@timestamp': datetime.datetime.utcfromtimestamp(time.time())})


def check(elastic, msg, count=1):
    # Sleep some time while elasticsearch indexes data
    time.sleep(15)
    #elastic.indices.refresh(index=get_index)
    resp = elastic.search(index=get_index(), q='msg:{}'.format(msg), size=count)
    assert len(resp['hits']['hits']) == count
    for found_msg in resp['hits']['hits']:
        assert found_msg['_source']['msg'] == msg


def test_fork(elastic, logger):
    msg = get_message()
    child = os.fork()
    if child:
        # Parent
        with vcr.use_cassette('fork-parent.yaml'):
            os.waitpid(child, 0)
            check(elastic, msg)
    else:
        # Child
        with vcr.use_cassette('fork-child.yaml'):
            logger.debug(msg)
            # Sleep to make sure that all messages are sent
            time.sleep(15)
        # Exit without deallocating objects to avoid conflicts with parent process
        os._exit(0)


@vcr.use_cassette('stress.yaml')
def test_stress(elastic, logger, capsys):
    count = 20
    msg = get_message()
    for _ in range(count):
        logger.debug(msg)
    out, err = capsys.readouterr()
    dropped = err.count("queue is full, dropping message")
    assert dropped > 0
    check(elastic, msg, count - dropped)
