all:
	true

pylint:
	python -m tox -e pylint

pypi:
	python setup.py register
	python setup.py sdist upload

clean:
	rm -rf build dist elog.egg-info
	find . -type f -name '*.pyc' -delete
	find . -type d -name __pycache__ -delete

clean-all: clean
	rm -rf .tox
