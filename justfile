test:
    coverage run --source=src -m pytest tests
    coverage report --fail-under=100
