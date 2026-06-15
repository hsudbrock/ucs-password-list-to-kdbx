PYTHON := python3
SCRIPT := csv_to_keepassxc.py
TESTS := test_csv_to_keepassxc.py

PASSWORD_ENV ?= KEEPASS_DB_PASSWORD

.PHONY: help test check run clean

help:
	@printf '%s\n' \
	  'Useful targets:' \
	  '  make test                      Run integration tests' \
	  '  make check                     Compile-check the Python files' \
	  '  make run CSV=... DB=... GROUP=...  Import a CSV into a KeePassXC database' \
	  '  make clean                     Remove Python cache files' \
	  '' \
	  'Run target variables:' \
	  '  CSV=...            Required CSV input file' \
	  '  DB=...             Required KeePass database file' \
	  '  GROUP=...          Required KeePass target group' \
	  '  PASSWORD_ENV=$(PASSWORD_ENV)' \
	  '' \
	  'Example:' \
	  "  export $(PASSWORD_ENV)='secret123'" \
	  '  make run CSV=passwords_EL.csv DB=passwords_EL.kdbx GROUP=Imported'

test:
	$(PYTHON) -m unittest -v $(TESTS)

check:
	$(PYTHON) -m py_compile $(SCRIPT) $(TESTS)

run:
	@if [ -z "$(CSV)" ]; then \
		printf '%s\n' 'Error: CSV is required, e.g. make run CSV=users.csv DB=users.kdbx GROUP=Imported' >&2; \
		exit 1; \
	fi
	@if [ -z "$(DB)" ]; then \
		printf '%s\n' 'Error: DB is required, e.g. make run CSV=users.csv DB=users.kdbx GROUP=Imported' >&2; \
		exit 1; \
	fi
	@if [ -z "$(GROUP)" ]; then \
		printf '%s\n' 'Error: GROUP is required, e.g. make run CSV=users.csv DB=users.kdbx GROUP=Imported' >&2; \
		exit 1; \
	fi
	@if [ -z "$$$(PASSWORD_ENV)" ]; then \
		printf '%s\n' "Error: environment variable $(PASSWORD_ENV) is not set" >&2; \
		exit 1; \
	fi
	$(PYTHON) $(SCRIPT) "$(CSV)" "$(DB)" --group "$(GROUP)" --password-env "$(PASSWORD_ENV)"

clean:
	rm -rf __pycache__
