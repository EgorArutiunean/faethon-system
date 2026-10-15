import hashlib
import os
import shlex
import subprocess
from pathlib import Path

import pytest

FIRST_DUMP = "buy_modern_20261015-040500.dump"
SECOND_DUMP = "buy_modern_20261016-040500.dump"
SOURCE_DECLARATION = "SOURCE_DIR='/var/backups/buy-staging'"


def _export_script(tmp_path: Path, source: Path) -> Path:
    original = Path(__file__).resolve().parents[2] / "scripts" / "export_staging_backup.sh"
    contents = original.read_text(encoding="utf-8")
    assert contents.count(SOURCE_DECLARATION) == 1
    script = tmp_path / "export.sh"
    script.write_text(
        contents.replace(SOURCE_DECLARATION, f"SOURCE_DIR={shlex.quote(str(source))}", 1),
        encoding="utf-8",
    )
    return script


def _run_export(
    script: Path, command: str, *, arguments: tuple[str, ...] = (), **overrides: str
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env.update(SSH_ORIGINAL_COMMAND=command, **overrides)
    return subprocess.run(
        ["sh", str(script), *arguments],
        env=env,
        check=False,
        capture_output=True,
        timeout=10,
    )


def _pair(source: Path, name: str = FIRST_DUMP, data: bytes = b"PGDMP\x00\xff\r\n\x80") -> Path:
    dump = source / name
    dump.write_bytes(data)
    checksum = hashlib.sha256(data).hexdigest()
    dump.with_suffix(".dump.sha256").write_bytes(f"{checksum}  {name}\n".encode("ascii"))
    return dump


@pytest.fixture
def export_source(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "backups"
    source.mkdir()
    return source, _export_script(tmp_path, source)


@pytest.mark.parametrize("ending", [b"", b"\n", b"\r\n"])
def test_get_preserves_binary_dump_and_exact_sidecar(
    export_source: tuple[Path, Path], ending: bytes
) -> None:
    source, script = export_source
    dump = _pair(source)
    sidecar = dump.with_suffix(".dump.sha256")
    sidecar.write_bytes(sidecar.read_bytes().rstrip(b"\n") + ending)

    result = _run_export(script, f"get {dump.name}")
    checksum_result = _run_export(script, f"get {sidecar.name}")

    assert result.returncode == 0, result.stderr
    assert result.stdout == dump.read_bytes()
    assert checksum_result.returncode == 0, checksum_result.stderr
    assert checksum_result.stdout == sidecar.read_bytes()


def test_list_returns_only_completed_valid_pairs(export_source: tuple[Path, Path]) -> None:
    source, script = export_source
    _pair(source, SECOND_DUMP)
    _pair(source)
    corrupt = _pair(source, "buy_modern_20261017-040500.dump")
    corrupt.write_bytes(b"changed after checksum")
    (source / "buy_modern_20261018-040500.dump").write_bytes(b"no checksum yet")
    (source / "buy_modern_20261019-040500.dump.partial").write_bytes(b"in progress")
    (source / "buy_modern_20261020-040500.dump.sha256").write_bytes(b"orphan sidecar")
    _pair(source, "buy_modern_abcdefgh-ijklmn.dump")
    (source / "buy_modern_20261021-040500.dump").mkdir()

    result = _run_export(script, "list")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{FIRST_DUMP}\n{SECOND_DUMP}\n".encode("ascii")


def test_list_of_empty_source_succeeds_without_output(export_source: tuple[Path, Path]) -> None:
    _, script = export_source
    result = _run_export(script, "list")
    assert result.returncode == 0, result.stderr
    assert result.stdout == b""


@pytest.mark.parametrize(
    "command",
    [
        "",
        "sh",
        "list ",
        "list\n",
        "list; id",
        "get",
        "get ",
        "get list",
        f"get  {FIRST_DUMP}",
        f"get {FIRST_DUMP} ",
        f"get {FIRST_DUMP} extra",
        f"get {FIRST_DUMP}\nlist",
        f"get {FIRST_DUMP}\r",
        f"get {FIRST_DUMP}; id",
        f"get ../{FIRST_DUMP}",
        f"get /var/backups/buy-staging/{FIRST_DUMP}",
        f"get ./{FIRST_DUMP}",
        f"get {FIRST_DUMP}.partial",
        f"get {FIRST_DUMP}.sha256.partial",
        f"get {FIRST_DUMP}.sha256.sha256",
        "get buy_modern_????????-??????.dump",
        "get $(id)",
        "get `id`",
        "get ../../etc/shadow",
    ],
)
def test_disallowed_command_never_exports_bytes(
    export_source: tuple[Path, Path], command: str
) -> None:
    source, script = export_source
    _pair(source)
    result = _run_export(script, command)
    assert result.returncode != 0
    assert result.stdout == b""


def test_direct_script_arguments_are_rejected(export_source: tuple[Path, Path]) -> None:
    source, script = export_source
    _pair(source)
    result = _run_export(script, "list", arguments=("get", FIRST_DUMP))
    assert result.returncode != 0
    assert result.stdout == b""


@pytest.mark.parametrize("suffix", ["", ".sha256"])
def test_corrupt_or_unpaired_dump_is_not_exported(
    export_source: tuple[Path, Path], suffix: str
) -> None:
    source, script = export_source
    dump = _pair(source)
    dump.write_bytes(b"corrupted dump")
    result = _run_export(script, f"get {dump.name}{suffix}")
    assert result.returncode != 0
    assert result.stdout == b""
    dump.with_suffix(".dump.sha256").unlink()
    result = _run_export(script, f"get {dump.name}{suffix}")
    assert result.returncode != 0
    assert result.stdout == b""


@pytest.mark.parametrize("member_type", ["empty-dump", "dump-fifo", "checksum-fifo"])
def test_non_regular_or_empty_member_is_rejected_without_blocking(
    export_source: tuple[Path, Path], member_type: str
) -> None:
    source, script = export_source
    dump = _pair(source)
    if member_type == "empty-dump":
        _pair(source, data=b"")
    else:
        member = dump if member_type == "dump-fifo" else dump.with_suffix(".dump.sha256")
        member.unlink()
        os.mkfifo(member)
    result = _run_export(script, f"get {dump.name}")
    assert result.returncode != 0
    assert result.stdout == b""


@pytest.mark.parametrize(
    "malformation",
    ["wrong-name", "single-space", "star", "extra-line", "blank-line", "nul", "extra-cr"],
)
def test_malformed_checksum_is_rejected_even_when_hash_matches(
    export_source: tuple[Path, Path], malformation: str
) -> None:
    source, script = export_source
    dump = _pair(source)
    sidecar = dump.with_suffix(".dump.sha256")
    digest = hashlib.sha256(dump.read_bytes()).hexdigest().encode("ascii")
    name = dump.name.encode("ascii")
    formats = {
        "wrong-name": digest + b"  ../../elsewhere\n",
        "single-space": digest + b" " + name + b"\n",
        "star": digest + b" *" + name + b"\n",
        "extra-line": digest + b"  " + name + b"\nextra\n",
        "blank-line": digest + b"  " + name + b"\n\n",
        "nul": digest + b"  " + name + b"\x00",
        "extra-cr": digest + b"  " + name + b"\r\r\n",
    }
    sidecar.write_bytes(formats[malformation])
    result = _run_export(script, f"get {dump.name}")
    listing = _run_export(script, "list")
    assert result.returncode != 0
    assert result.stdout == b""
    assert listing.returncode == 0, listing.stderr
    assert listing.stdout == b""


@pytest.mark.parametrize("link_part", ["dump", "checksum"])
def test_symlinked_member_is_rejected(export_source: tuple[Path, Path], link_part: str) -> None:
    source, script = export_source
    dump = _pair(source)
    member = dump if link_part == "dump" else dump.with_suffix(".dump.sha256")
    outside = source.parent / f"outside-{link_part}"
    member.rename(outside)
    member.symlink_to(outside)
    result = _run_export(script, f"get {dump.name}")
    listing = _run_export(script, "list")
    assert result.returncode != 0
    assert result.stdout == b""
    assert listing.returncode == 0, listing.stderr
    assert listing.stdout == b""


@pytest.mark.parametrize("parent_symlink", [False, True])
def test_source_symlinks_are_rejected(tmp_path: Path, parent_symlink: bool) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    real_source = real_parent / "backups"
    real_source.mkdir()
    _pair(real_source)
    link = tmp_path / "link"
    link.symlink_to(real_parent if parent_symlink else real_source, target_is_directory=True)
    source = link / "backups" if parent_symlink else link
    script = _export_script(tmp_path, source)
    result = _run_export(script, "list")
    assert result.returncode != 0
    assert result.stdout == b""


def test_source_environment_cannot_redirect_export(export_source: tuple[Path, Path]) -> None:
    source, script = export_source
    outside = source.parent / "outside"
    outside.mkdir()
    _pair(outside)
    result = _run_export(
        script, f"get {FIRST_DUMP}", BACKUP_DIR=str(outside), SOURCE_DIR=str(outside)
    )
    assert result.returncode != 0
    assert result.stdout == b""


def test_export_does_not_modify_source_files(export_source: tuple[Path, Path]) -> None:
    source, script = export_source
    dump = _pair(source)
    before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in source.iterdir()}
    for command in ("list", f"get {dump.name}", f"get {dump.name}.sha256"):
        result = _run_export(script, command)
        assert result.returncode == 0, result.stderr
    after = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in source.iterdir()}
    assert before == after
