# Convenience targets

.PHONY: test

test:
	AT_MOCK=1 DATABASE_URL=sqlite:///:memory: python -m pytest -q backend/tests
