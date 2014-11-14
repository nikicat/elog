[![Build Status](https://travis-ci.org/yandex-sysmon/elog.svg?branch=master)](https://travis-ci.org/yandex-sysmon/elog)
[![Coverage Status](https://img.shields.io/coveralls/yandex-sysmon/elog.svg)](https://coveralls.io/r/yandex-sysmon/elog)
[![Dependency Status](https://gemnasium.com/yandex-sysmon/elog.svg)](https://gemnasium.com/yandex-sysmon/elog)
[![Downloads](https://pypip.in/download/elog/badge.png)](https://pypi.python.org/pypi/elog/)

Elog
======
ElasticSearch logging handler and tools.

Example
------
```python
import elog.records
import logging
import logging.config

config = {
    "version": 1,
    "handlers": {
        "elastic": {
            "level":       "DEBUG",
            "class":       "elog.handlers.ElasticHandler",
            "time_field":  "@timestamp",
            "hosts":       {"host": "elasticlog.yandex.net", "port": 9200},
            "index":       "log-{@timestamp:%Y}-{@timestamp:%m}-{@timestamp:%d}",
            "doctype":     "example",
            "fields": {
                "logger": "name",
                "level":  "levelname",
                "msg":    "msg",
                "args":   "args",
                "file":   "pathname",
                "line":   "lineno",
                "pid":    "process",
            },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["elastic"],
    },
}

logging.config.dictConfig(config)
logging.setLogRecordFactory(elog.records.LogRecord)
logging.captureWarnings(True)

logger = logging.getLogger(__name__)
logger.debug("test message %s", 12345)
```

To get your log message:

```bash
curl http://example.com:9200/log-2014-05-28/example/_search
```
**Note:** put your *current* `year-month-day` instead of `2014-05-28`.
