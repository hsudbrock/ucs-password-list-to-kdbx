# ucs-password-list-to-kdbx

Convert a UCS-generated password CSV file into a KeePassXC `.kdbx` database.

This project imports each CSV row as a KeePass entry, creates the database if it
does not exist yet, and updates existing entries by username when you run the
import again.

## What it does

- Reads a CSV file with the expected UCS column layout
- Creates a new KeePassXC database if the target `.kdbx` file does not exist
- Creates a `.bak` copy before modifying an existing database
- Creates the target group if needed
- Adds new entries
- Updates existing entries when the same username already exists in the group

Each KeePass entry uses:

- Title: `Firstname Lastname (username)`
- Username: `username`
- Password: `password`
- Notes:
  - `role: ...`
  - `schools: ...`
  - `classes: ...`
  - `last_imported_at: ...`

## Requirements

- `python3`
- `keepassxc-cli`
- A CSV file exported in the expected format

You can check that `keepassxc-cli` is available with:

```bash
keepassxc-cli --version
```

## Expected CSV format

The CSV header must match this exact column order:

```csv
username,password,role,lastname,firstname,schools,classes
```

Required fields per row:

- `username`
- `password`
- `lastname`
- `firstname`

Empty lines are ignored.

Example:

```csv
username,password,role,lastname,firstname,schools,classes
jsmith,secret1,student,Smith,John,Central High,10A
jdoe,secret2,teacher,Doe,Jane,North Campus,12B
```

## Basic usage

### Interactive password prompt

If you run the script in a terminal, it will prompt for the KeePass database
password:

```bash
python3 csv_to_keepassxc.py users.csv users.kdbx --group Imported
```

### Password from environment variable

This is useful for automation and for the provided `Makefile` target:

```bash
export KEEPASS_DB_PASSWORD='your-database-password'
python3 csv_to_keepassxc.py users.csv users.kdbx --group Imported --password-env KEEPASS_DB_PASSWORD
```

## Using the Makefile

Show the available targets:

```bash
make help
```

Run the importer:

```bash
export KEEPASS_DB_PASSWORD='your-database-password'
make run CSV=users.csv DB=users.kdbx GROUP=Imported
```

By default, the Makefile expects the password in `KEEPASS_DB_PASSWORD`.
You can override that variable name if needed:

```bash
export MY_DB_PASSWORD='your-database-password'
make run CSV=users.csv DB=users.kdbx GROUP=Imported PASSWORD_ENV=MY_DB_PASSWORD
```

## Import behavior

- If `users.kdbx` does not exist, it is created automatically.
- If `users.kdbx` already exists, a backup is written to `users.kdbx.bak`
  before any changes are made.
- If the target group does not exist, it is created automatically.
- If a username does not exist in the group, a new entry is created.
- If a username already exists in the group, that entry is updated.
- If multiple entries with the same username already exist in the target group,
  the import stops with an error.

At the end, the script prints a summary like:

```text
Imported 2 entries into users.kdbx (1 created, 1 updated)
```

## Validation and errors

The script exits with an error when:

- the CSV file does not exist
- the CSV header does not match the expected format exactly
- a required value is missing in a row
- the database password is empty or unavailable
- `keepassxc-cli` returns an error

## Development

Syntax check:

```bash
make check
```

Run tests:

```bash
make test
```

Remove Python cache files:

```bash
make clean
```
