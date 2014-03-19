#!/usr/bin/env python


import setuptools
import elog.const


##### Main #####
if __name__ == "__main__":
    setuptools.setup(
        name="elog",
        version=elog.const.VERSION,
        url=elog.const.UPSTREAM_URL,
        license="LGPLv3",
        author="Devaev Maxim",
        author_email="mdevaev@gmail.com",
        description="ElasticSearch logging handler and tools",
        platforms="any",

        packages=(
            "elog",
        ),

        classifiers=( # http://pypi.python.org/pypi?:action=list_classifiers
            "Development Status :: 2 - Pre-Alpha",
            "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: System :: Networking :: Monitoring",
            "Topic :: System :: Logging",
        ),
    )

