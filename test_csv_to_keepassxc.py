import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("csv_to_keepassxc.py")
DB_PASSWORD = "test-password-123"


class CsvToKeePassXCIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="keepass-import-test-")
        self.temp_path = Path(self.temp_dir.name)
        self.csv_path = self.temp_path / "users.csv"
        self.db_path = self.temp_path / "users.kdbx"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_csv(self, rows):
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([
                "username",
                "password",
                "role",
                "lastname",
                "firstname",
                "schools",
                "classes",
            ])
            writer.writerows(rows)

    def run_import(self):
        env = os.environ.copy()
        env["KEEPASS_DB_PASSWORD"] = DB_PASSWORD
        return subprocess.run(
            [
                "python3",
                str(SCRIPT_PATH),
                str(self.csv_path),
                str(self.db_path),
                "--password-env",
                "KEEPASS_DB_PASSWORD",
            ],
            text=True,
            capture_output=True,
            env=env,
            check=True,
        )

    def keepass_show(self, entry_path, *attributes, show_protected=False):
        command = ["keepassxc-cli", "show"]
        if show_protected:
            command.append("-s")
        for attribute in attributes:
            command.extend(["-a", attribute])
        command.extend([str(self.db_path), entry_path])
        result = subprocess.run(
            command,
            input=f"{DB_PASSWORD}\n",
            text=True,
            capture_output=True,
            check=True,
        )
        return [line for line in result.stdout.splitlines() if line]

    def test_import_creates_entry_in_new_database(self):
        self.write_csv([
            ["jsmith", "secret1", "student", "Smith", "John", "Central High", "10A"],
        ])

        result = self.run_import()

        self.assertIn("(1 created, 0 updated)", result.stdout)
        lines = self.keepass_show(
            "Imported/John Smith (jsmith)",
            "UserName",
            "Password",
            "Notes",
            show_protected=True,
        )
        self.assertEqual(lines[0], "jsmith")
        self.assertEqual(lines[1], "secret1")
        self.assertIn("role: student", lines[2])
        self.assertIn("schools: Central High", lines[3])
        self.assertIn("classes: 10A", lines[4])
        self.assertRegex(lines[5], r"^last_imported_at: .+")

    def test_import_updates_existing_entry_by_username(self):
        self.write_csv([
            ["jsmith", "secret1", "student", "Smith", "John", "Central High", "10A"],
        ])
        self.run_import()

        self.write_csv([
            ["jsmith", "secret2", "teacher", "Doe", "Jane", "North Campus", "12B"],
        ])
        result = self.run_import()

        self.assertIn("(0 created, 1 updated)", result.stdout)
        updated_lines = self.keepass_show(
            "Imported/Jane Doe (jsmith)",
            "UserName",
            "Password",
            "Notes",
            show_protected=True,
        )
        self.assertEqual(updated_lines[0], "jsmith")
        self.assertEqual(updated_lines[1], "secret2")
        self.assertIn("role: teacher", updated_lines[2])
        self.assertIn("schools: North Campus", updated_lines[3])
        self.assertIn("classes: 12B", updated_lines[4])

        missing_result = subprocess.run(
            ["keepassxc-cli", "show", str(self.db_path), "Imported/John Smith (jsmith)"],
            input=f"{DB_PASSWORD}\n",
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(missing_result.returncode, 0)

    def test_import_handles_empty_group_listing_placeholder(self):
        subprocess.run(
            ["keepassxc-cli", "db-create", "-p", str(self.db_path)],
            input=f"{DB_PASSWORD}\n{DB_PASSWORD}\n",
            text=True,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["keepassxc-cli", "mkdir", str(self.db_path), "Imported"],
            input=f"{DB_PASSWORD}\n",
            text=True,
            capture_output=True,
            check=True,
        )
        self.write_csv([
            ["alice", "secret3", "student", "Example", "Alice", "School A", "1A"],
        ])

        result = self.run_import()

        self.assertIn("(1 created, 0 updated)", result.stdout)
        lines = self.keepass_show("Imported/Alice Example (alice)", "UserName")
        self.assertEqual(lines, ["alice"])


if __name__ == "__main__":
    unittest.main()
