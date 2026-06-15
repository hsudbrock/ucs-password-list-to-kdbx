#!/usr/bin/env python3

import argparse
import csv
from datetime import datetime, timezone
import getpass
import os
import subprocess
import sys
from pathlib import Path


EXPECTED_COLUMNS = [
    "username",
    "password",
    "role",
    "lastname",
    "firstname",
    "schools",
    "classes",
]

REQUIRED_ROW_FIELDS = ["username", "password", "lastname", "firstname"]
EMPTY_GROUP_MARKERS = {"[empty]", "[leer]"}


def run_keepassxc(args, stdin_text):
    result = subprocess.run(
        ["keepassxc-cli", *args],
        input=stdin_text,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or f"keepassxc-cli exited with {result.returncode}"
        raise RuntimeError(detail)
    return result


def create_database(db_path, master_password):
    run_keepassxc(
        ["db-create", "-p", str(db_path)],
        f"{master_password}\n{master_password}\n",
    )


def group_exists(db_path, master_password, group):
    result = subprocess.run(
        ["keepassxc-cli", "ls", str(db_path), group],
        input=f"{master_password}\n",
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def ensure_group(db_path, master_password, group):
    if not group:
        return
    if group_exists(db_path, master_password, group):
        return

    result = subprocess.run(
        ["keepassxc-cli", "mkdir", str(db_path), group],
        input=f"{master_password}\n",
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        if not group_exists(db_path, master_password, group):
            raise RuntimeError(
                result.stderr.strip() or result.stdout.strip() or "Failed to create group"
            )


def validate_columns(fieldnames):
    if fieldnames != EXPECTED_COLUMNS:
        raise ValueError(
            "CSV header mismatch. Expected: " + ",".join(EXPECTED_COLUMNS)
        )


def normalize_row(row, row_number):
    normalized = {key: (value or "").strip() for key, value in row.items()}
    missing = [field for field in REQUIRED_ROW_FIELDS if not normalized[field]]
    if missing:
        raise ValueError(
            f"Row {row_number} is missing required values: {', '.join(missing)}"
        )
    return normalized


def sanitize_title_part(value):
    return value.replace("/", "-")


def build_title(row):
    firstname = sanitize_title_part(row["firstname"])
    lastname = sanitize_title_part(row["lastname"])
    username = sanitize_title_part(row["username"])
    return f"{firstname} {lastname} ({username})"


def build_notes(row):
    imported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return "\n".join([
        f"role: {row['role']}",
        f"schools: {row['schools']}",
        f"classes: {row['classes']}",
        f"last_imported_at: {imported_at}",
    ])


def get_entry_username(db_path, master_password, entry_path):
    result = run_keepassxc(
        ["show", "-a", "UserName", str(db_path), entry_path],
        f"{master_password}\n",
    )
    return result.stdout.strip()


def list_group_entries(db_path, master_password, group):
    args = ["keepassxc-cli", "ls", "-f", str(db_path)]
    if group:
        args.append(group)
    result = subprocess.run(
        args,
        input=f"{master_password}\n",
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Failed to list entries"
        raise RuntimeError(detail)

    entries = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.lower() in EMPTY_GROUP_MARKERS:
            continue
        entries.append(line)
    return entries


def build_entry_index(db_path, master_password, group):
    index = {}
    for title in list_group_entries(db_path, master_password, group):
        entry_path = f"{group}/{title}" if group else title
        username = get_entry_username(db_path, master_password, entry_path)
        if username in index:
            raise ValueError(
                f"Multiple KeePass entries found for username {username!r} in group {group!r}"
            )
        index[username] = entry_path
    return index


def add_entry(db_path, master_password, entry_path, row):
    stdin_text = f"{master_password}\n{row['password']}\n{row['password']}\n"
    run_keepassxc(
        [
            "add",
            "-u",
            row["username"],
            "--notes",
            build_notes(row),
            "-p",
            str(db_path),
            entry_path,
        ],
        stdin_text,
    )


def edit_entry(db_path, master_password, entry_path, row):
    stdin_text = f"{master_password}\n{row['password']}\n{row['password']}\n"
    run_keepassxc(
        [
            "edit",
            "-u",
            row["username"],
            "-t",
            build_title(row),
            "--notes",
            build_notes(row),
            "-p",
            str(db_path),
            entry_path,
        ],
        stdin_text,
    )


def upsert_entry(db_path, master_password, entry_index, group, row):
    entry_path = entry_index.get(row["username"])
    if entry_path:
        edit_entry(db_path, master_password, entry_path, row)
        new_entry_path = f"{group}/{build_title(row)}" if group else build_title(row)
        entry_index[row["username"]] = new_entry_path
        return "updated"

    entry_path = f"{group}/{build_title(row)}" if group else build_title(row)
    add_entry(db_path, master_password, entry_path, row)
    entry_index[row["username"]] = entry_path
    return "created"


def get_master_password(password_env_var):
    if password_env_var:
        value = os.environ.get(password_env_var)
        if not value:
            raise ValueError(
                f"Environment variable {password_env_var} is not set or empty."
            )
        return value

    if not sys.stdin.isatty():
        raise ValueError(
            "No interactive terminal available. Use --password-env with an environment variable name."
        )

    return getpass.getpass("KeePass database password: ")


def main():
    parser = argparse.ArgumentParser(
        description="Create or update a KeePassXC database from a CSV file."
    )
    parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
    parser.add_argument("database_file", type=Path, help="Path to the .kdbx file")
    parser.add_argument(
        "--group",
        default="Imported",
        help="KeePass group to store the imported entries in",
    )
    parser.add_argument(
        "--password-env",
        help="Read the KeePass database password from this environment variable",
    )
    args = parser.parse_args()

    if not args.csv_file.is_file():
        print(f"CSV file not found: {args.csv_file}", file=sys.stderr)
        return 1

    master_password = get_master_password(args.password_env)
    if not master_password:
        print("Database password must not be empty.", file=sys.stderr)
        return 1

    if not args.database_file.exists():
        create_database(args.database_file, master_password)

    ensure_group(args.database_file, master_password, args.group)
    entry_index = build_entry_index(args.database_file, master_password, args.group)

    created = 0
    updated = 0
    with args.csv_file.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        validate_columns(reader.fieldnames)
        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue

            normalized_row = normalize_row(row, row_number)
            action = upsert_entry(
                args.database_file,
                master_password,
                entry_index,
                args.group,
                normalized_row,
            )
            if action == "created":
                created += 1
            else:
                updated += 1

    print(
        f"Imported {created + updated} entries into {args.database_file} "
        f"({created} created, {updated} updated)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
