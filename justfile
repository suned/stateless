test:
    coverage run -m pytest tests
    coverage combine
    coverage report --fail-under=100

lint:
    pre-commit run --all-files
