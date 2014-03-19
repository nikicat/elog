all:
	true

pylint:
	pylint --rcfile=pylint.ini \
		elog \
		*.py \
		--output-format=colorized 2>&1 | less -SR

pypi:
	python setup.py register
	python setup.py sdist upload

clean:
	rm -rf build dist elog.egg-info
	find . -type f -name '*.pyc' -delete
	find . -type d -name __pycache__ -delete

