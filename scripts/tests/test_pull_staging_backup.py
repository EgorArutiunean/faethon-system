"""Windows-only synthetic process tests; no SSH server, keys or Restic install.

Run: python -m unittest discover -s scripts/tests -p test_pull_staging_backup.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "pull_staging_backup.ps1"
FIXTURE_SOURCE = Path(__file__).parent / "fixtures" / "pc_backup_tool.cs"
PWSH = shutil.which("pwsh")
CSC = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
NAME = "buy_modern_20261015-112125.dump"
SECOND_NAME = "buy_modern_20261016-020000.dump"


@unittest.skipUnless(os.name == "nt" and PWSH and CSC.is_file(), "Windows, PowerShell 7 and Framework csc.exe required")
class PullBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler_directory = tempfile.TemporaryDirectory(prefix="buy-pull-tools-")
        cls.binary = Path(cls.compiler_directory.name) / "fixture.exe"
        result = subprocess.run(
            [str(CSC), "/nologo", "/r:System.Web.Extensions.dll", f"/out:{cls.binary}", str(FIXTURE_SOURCE)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            cls.compiler_directory.cleanup()
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.compiler_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="buy-pull-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.remote = self.root / "remote"
        self.remote.mkdir()
        self.backup_root = self.root / "backup root with spaces"
        self.identity = self.root / "synthetic identity"
        self.identity.write_text("Not an SSH private key. Fixture does not read it.")
        self.ssh = self.root / "ssh.exe"
        self.restic = self.root / "restic.exe"
        shutil.copy2(self.binary, self.ssh)
        shutil.copy2(self.binary, self.restic)
        self.create_pair(NAME, b"PGDMP\x00\xff\x80\r\n" + bytes(range(256)))
        (self.remote / "list.txt").write_bytes(f"{NAME}\r\n".encode("ascii"))

    def create_pair(self, name, contents):
        (self.remote / name).write_bytes(contents)
        digest = hashlib.sha256(contents).hexdigest()
        (self.remote / f"{name}.sha256").write_bytes(f"{digest}  {name}\r\n".encode("ascii"))

    def run_pull(self, *, initialize=True, scenario="", driver_prefix="", confirmation="fixture-only-passphrase", password="fixture-only-passphrase", round_trip=False, real_restic=False):
        driver = self.root / "driver.ps1"
        # Values from temp paths enter through child environment, not interpolated
        # shell source. This driver uses only a synthetic password and identity.
        driver.write_text(
            """$ErrorActionPreference = 'Stop'
. $env:BUY_PULL_SCRIPT
$password = ConvertTo-SecureString $env:BUY_PULL_PASSWORD -AsPlainText -Force
$confirmation = ConvertTo-SecureString $env:BUY_PULL_CONFIRM -AsPlainText -Force
"""
            + driver_prefix
            + """
try {
    $result = Invoke-StagingBackupPull -SshTarget 'backup-reader@fixture.invalid' `
      -IdentityFile $env:BUY_PULL_IDENTITY -ResticExecutable $env:BUY_PULL_RESTIC `
      -SshExecutable $env:BUY_PULL_SSH -BackupRoot $env:BUY_PULL_BACKUP_ROOT `
      -InitializeRepository ([bool]::Parse($env:BUY_PULL_INIT)) `
      -VerifyRoundTrip ([bool]::Parse($env:BUY_PULL_ROUNDTRIP)) `
      -Password $password -ConfirmationPassword $confirmation
    if ($env:RESTIC_PASSWORD -ne 'ambient-wrong-secret') { throw 'The parent environment was changed.' }
    $result | ConvertTo-Json -Depth 5 -Compress
} catch {
    [pscustomobject]@{status='error'; message=$_.Exception.Message; stack=$_.ScriptStackTrace} | ConvertTo-Json -Compress
    exit 1
} finally {
    $password.Dispose()
    $confirmation.Dispose()
}
""",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update(
            BUY_PULL_SCRIPT=str(SCRIPT),
            BUY_PULL_FIXTURE_ROOT=str(self.root),
            BUY_PULL_FIXTURE_SCENARIO=scenario,
            BUY_PULL_IDENTITY=str(self.identity),
            BUY_PULL_RESTIC=os.environ["BUY_PULL_REAL_RESTIC"] if real_restic else str(self.restic),
            BUY_PULL_SSH=str(self.ssh),
            BUY_PULL_BACKUP_ROOT=str(self.backup_root),
            BUY_PULL_INIT=str(initialize),
            BUY_PULL_ROUNDTRIP=str(round_trip),
            BUY_PULL_CONFIRM=confirmation,
            BUY_PULL_PASSWORD=password,
            RESTIC_PASSWORD="ambient-wrong-secret",
            RESTIC_PASSWORD_COMMAND="do-not-execute",
            RESTIC_PASSWORD_FILE="not-a-real-file",
            RESTIC_REPOSITORY="wrong-repository",
            RESTIC_REPOSITORY_FILE="also-not-real",
            RESTIC_INSECURE_TLS="true",
        )
        result = subprocess.run(
            [PWSH, "-NoProfile", "-NonInteractive", "-File", str(driver)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertNotIn("fixture-only-passphrase", result.stdout + result.stderr)
        self.assertNotIn("ambient-wrong-secret", result.stdout + result.stderr)
        return result

    def calls(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def assert_no_plaintext(self):
        incoming = self.backup_root / ".incoming"
        self.assertEqual(list(incoming.iterdir()) if incoming.exists() else [], [])

    def test_binary_pair_encrypts_and_second_pull_uses_snapshots(self):
        result = self.run_pull()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual((status["encrypted"], status["skipped"]), (1, 0))
        self.assertEqual(status["snapshots"][0]["backup"], NAME)
        self.assert_no_plaintext()
        result = self.run_pull(initialize=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual((status["encrypted"], status["skipped"]), (0, 1))
        self.assertEqual(sum("backup" in call["args"] for call in self.calls() if call["tool"] == "restic"), 1)
        self.assertEqual(sum("get" in call["args"] for call in self.calls() if call["tool"] == "ssh"), 2)
        self.assert_no_plaintext()

    def test_all_retained_pairs_are_pulled_not_just_latest(self):
        self.create_pair(SECOND_NAME, b"second-binary-dump\x00\xff")
        (self.remote / "list.txt").write_bytes(f"{SECOND_NAME}\n{NAME}\n".encode("ascii"))
        result = self.run_pull()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["encrypted"], 2)
        self.assert_no_plaintext()

    def test_checksum_mismatch_never_reaches_restic_backup(self):
        (self.remote / NAME).write_bytes(b"corrupt bytes")
        result = self.run_pull()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stdout)
        self.assertFalse(any("backup" in call["args"] for call in self.calls() if call["tool"] == "restic"))
        self.assert_no_plaintext()

    def test_empty_dump_is_rejected_even_with_matching_checksum(self):
        self.create_pair(NAME, b"")
        result = self.run_pull()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty", result.stdout)
        self.assertFalse(any("backup" in call["args"] for call in self.calls() if call["tool"] == "restic"))
        self.assert_no_plaintext()

    def test_failed_new_pair_preserves_previously_encrypted_snapshot(self):
        result = self.run_pull()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = self.backup_root / "repository" / "fixture-state.json"
        original = state.read_bytes()
        self.create_pair(SECOND_NAME, b"second-dump")
        (self.remote / SECOND_NAME).write_bytes(b"corrupted-second-dump")
        (self.remote / "list.txt").write_bytes(f"{NAME}\n{SECOND_NAME}\n".encode("ascii"))
        result = self.run_pull(initialize=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state.read_bytes(), original)
        self.assert_no_plaintext()

    def test_malformed_sidecars_are_rejected_before_dump_download(self):
        original = (self.remote / f"{NAME}.sha256").read_bytes()
        invalid = [
            original + b"\n",
            original.replace(NAME.encode(), SECOND_NAME.encode()),
            original.upper(),
            b"\xef\xbb\xbf" + original,
            b"a" * 257,
        ]
        for index, sidecar in enumerate(invalid):
            with self.subTest(index=index):
                (self.remote / f"{NAME}.sha256").write_bytes(sidecar)
                initialize = not (self.backup_root / "repository" / "config").exists()
                call_count = len(self.calls())
                result = self.run_pull(initialize=initialize)
                self.assertNotEqual(result.returncode, 0)
                new_calls = self.calls()[call_count:]
                self.assertFalse(any(call["args"][-2:] == ["get", NAME] for call in new_calls if call["tool"] == "ssh"))
                self.assert_no_plaintext()

    def test_untrusted_or_oversized_lists_do_not_download(self):
        for index, listing in enumerate([b"../stolen.dump\n", b";touch bad\n", f"{NAME}\n{NAME}\n".encode(), b"x" * 65537]):
            with self.subTest(index=index):
                (self.remote / "list.txt").write_bytes(listing)
                initialize = not (self.backup_root / "repository" / "config").exists()
                call_count = len(self.calls())
                result = self.run_pull(initialize=initialize)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any("get" in call["args"] for call in self.calls()[call_count:] if call["tool"] == "ssh"))
                self.assert_no_plaintext()

    def test_failed_download_cleans_own_plaintext(self):
        result = self.run_pull(scenario="get-failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("backup" in call["args"] for call in self.calls() if call["tool"] == "restic"))
        self.assert_no_plaintext()

    def test_failed_encryption_or_unconfirmed_snapshot_is_not_success(self):
        for scenario in ["backup-failure", "missing-snapshot"]:
            with self.subTest(scenario=scenario):
                initialize = not (self.backup_root / "repository" / "config").exists()
                result = self.run_pull(initialize=initialize, scenario=scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["status"], "error")
                self.assert_no_plaintext()

    def test_unknown_existing_repository_is_never_initialized(self):
        repository = self.backup_root / "repository"
        repository.mkdir(parents=True)
        sentinel = repository / "important-file"
        sentinel.write_text("preserve this directory")
        result = self.run_pull()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), "preserve this directory")
        self.assertEqual(self.calls(), [])

    def test_lock_refuses_parallel_pull_before_child_processes(self):
        result = self.run_pull(driver_prefix="""
[void][IO.Directory]::CreateDirectory($env:BUY_PULL_BACKUP_ROOT)
$held = [IO.File]::Open((Join-Path $env:BUY_PULL_BACKUP_ROOT '.pull.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lock", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_incoming_junction_is_rejected_without_touching_target(self):
        external = self.root / "unrelated-directory"
        external.mkdir()
        sentinel = external / "preserve.txt"
        sentinel.write_text("untouched")
        self.backup_root.mkdir()
        incoming = self.backup_root / ".incoming"
        junction = subprocess.run(
            [PWSH, "-NoProfile", "-Command", "New-Item -ItemType Junction -Path $env:BUY_JUNCTION -Target $env:BUY_JUNCTION_TARGET | Out-Null"],
            env={**os.environ, "BUY_JUNCTION": str(incoming), "BUY_JUNCTION_TARGET": str(external)},
            capture_output=True,
            text=True,
            check=False,
        )
        if junction.returncode:
            self.skipTest("This Windows account cannot create directory junctions")
        self.addCleanup(os.rmdir, incoming)
        result = self.run_pull()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reparse", result.stdout)
        self.assertEqual(sentinel.read_text(), "untouched")
        self.assertEqual(list(external.iterdir()), [sentinel])
        self.assertEqual(self.calls(), [])

    def test_roundtrip_checks_restored_snapshot_bytes(self):
        result = self.run_pull(round_trip=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["round_trip_verified"], 1)
        self.assert_no_plaintext()

    def test_corrupt_roundtrip_fails_without_removing_snapshot(self):
        result = self.run_pull(round_trip=True, scenario="corrupt-roundtrip")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("round-trip", result.stdout)
        self.assertEqual(len(json.loads((self.backup_root / "repository" / "fixture-state.json").read_text())), 1)
        self.assert_no_plaintext()

    def test_failed_roundtrip_retry_verifies_the_existing_snapshot(self):
        result = self.run_pull(round_trip=True, scenario="corrupt-roundtrip")
        self.assertNotEqual(result.returncode, 0)
        result = self.run_pull(initialize=False, round_trip=True, scenario="corrupt-roundtrip")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("round-trip", result.stdout)
        result = self.run_pull(initialize=False, round_trip=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual((status["encrypted"], status["skipped"], status["round_trip_verified"]), (0, 1, 1))
        self.assertEqual(status["verified_snapshots"][0]["backup"], NAME)
        self.assertEqual(sum("backup" in call["args"] for call in self.calls() if call["tool"] == "restic"), 1)
        self.assert_no_plaintext()

    @unittest.skipUnless(os.environ.get("BUY_PULL_REAL_RESTIC"), "Set BUY_PULL_REAL_RESTIC to an already installed executable")
    def test_real_restic_encryption_and_roundtrip(self):
        result = self.run_pull(round_trip=True, real_restic=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["round_trip_verified"], 1)
        result = self.run_pull(initialize=False, round_trip=True, real_restic=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual((status["encrypted"], status["skipped"], status["round_trip_verified"]), (0, 1, 1))
        self.assert_no_plaintext()

    def test_missing_repository_requires_explicit_initialize(self):
        result = self.run_pull(initialize=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_password_confirmation_is_required_for_initialization(self):
        result = self.run_pull(confirmation="different-synthetic-password")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("confirmation", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_new_repository_requires_a_strong_recovery_passphrase(self):
        result = self.run_pull(password="short", confirmation="short")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("16 characters", result.stdout)
        self.assertFalse(self.backup_root.exists())
        self.assertEqual(self.calls(), [])

    def test_root_acl_only_grants_current_user_and_system(self):
        result = self.run_pull()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        probe = subprocess.run(
            [PWSH, "-NoProfile", "-Command", "$acl = Get-Acl -LiteralPath $env:BUY_ACL_PATH; @($acl.Access | ForEach-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value }) | ConvertTo-Json -Compress"],
            env={**os.environ, "BUY_ACL_PATH": str(self.backup_root / ".incoming")},
            capture_output=True,
            text=True,
            check=True,
        )
        sids = json.loads(probe.stdout)
        self.assertIn("S-1-5-18", sids)
        self.assertEqual(len(sids), 2)
        self.assertNotIn("S-1-5-32-544", sids)
        self.assertNotIn("S-1-1-0", sids)


if __name__ == "__main__":
    unittest.main()
