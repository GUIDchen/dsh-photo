from pathlib import Path

from dsh_photo.matcher import (
    match_directories,
    name_key,
    normalize_extensions,
    scan_directory,
    transfer_matches,
)


def make_file(directory: Path, name: str, content: bytes = b"x") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return path


def test_name_key_ignores_case_and_unicode_form():
    assert name_key("HP7A4477") == name_key("hp7a4477")
    # NFC 与 NFD 表示应落到同一个键
    assert name_key("caf\u00e9") == name_key("cafe\u0301")


def test_normalize_extensions_adds_dot_and_dedupes():
    assert normalize_extensions(["CR3", ".cr3", " JPG ", ""]) == (".cr3", ".jpg")


def test_scan_directory_only_returns_matching_files(tmp_path):
    make_file(tmp_path, "A.CR3")
    make_file(tmp_path, "B.JPG")
    make_file(tmp_path, "._A.CR3")
    make_file(tmp_path, "notes.txt")

    entries = scan_directory(tmp_path, [".cr3"])

    assert [entry.path.name for entry in entries] == ["A.CR3"]


def test_match_directories_pairs_by_case_insensitive_name(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    make_file(raw, "HP7A4477.CR3")
    make_file(raw, "HP7A4481.CR3")
    make_file(jpeg, "HP7A4477.JPG")
    make_file(jpeg, "HP7A9999.JPG")

    result = match_directories(raw, jpeg)

    assert [target.name for _, target in result.pairs] == ["HP7A4477.JPG"]
    assert [path.name for path in result.source_without_target] == ["HP7A4481.CR3"]
    assert [path.name for path in result.target_without_source] == ["HP7A9999.JPG"]
    assert result.source_count == 2
    assert result.target_count == 2


def test_match_directories_handles_duplicate_targets(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    make_file(raw, "A.CR3")
    make_file(jpeg, "A.JPG")
    make_file(jpeg, "A.JPEG")

    result = match_directories(raw, jpeg)

    assert result.matched == 1
    # 扩展名声明顺序中 .jpg 优先
    assert result.pairs[0][1].name == "A.JPG"
    assert "a" in result.ambiguous_targets
    assert len(result.ambiguous_targets["a"]) == 2


def test_transfer_copies_and_flattens(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    make_file(raw, "A.CR3")
    source = make_file(jpeg, "A.JPG", b"jpeg-data")

    result = match_directories(raw, jpeg)
    transfer = transfer_matches(result.pairs, output)

    assert transfer.transferred == 1
    assert transfer.failed == 0
    assert (output / "A.JPG").read_bytes() == b"jpeg-data"
    assert source.exists()


def test_transfer_is_idempotent(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    make_file(raw, "A.CR3")
    make_file(jpeg, "A.JPG", b"jpeg-data")
    result = match_directories(raw, jpeg)

    first = transfer_matches(result.pairs, output)
    second = transfer_matches(result.pairs, output)

    assert first.transferred == 1
    assert second.transferred == 0
    assert second.skipped == 1


def test_transfer_dry_run_writes_nothing(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    make_file(raw, "A.CR3")
    make_file(jpeg, "A.JPG")
    result = match_directories(raw, jpeg)

    transfer = transfer_matches(result.pairs, output, dry_run=True)

    assert transfer.transferred == 1
    assert not output.exists()


def test_transfer_move_removes_source(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    make_file(raw, "A.CR3")
    source = make_file(jpeg, "A.JPG", b"data")
    result = match_directories(raw, jpeg)

    transfer = transfer_matches(result.pairs, output, mode="move")

    assert transfer.transferred == 1
    assert (output / "A.JPG").exists()
    assert not source.exists()


def test_transfer_reports_conflict_without_overwrite(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    make_file(raw, "A.CR3")
    make_file(jpeg, "A.JPG", b"new")
    make_file(output, "A.JPG", b"different-size")
    result = match_directories(raw, jpeg)

    transfer = transfer_matches(result.pairs, output)

    assert transfer.transferred == 0
    assert transfer.skipped == 1
    assert len(transfer.conflicts) == 1
    assert (output / "A.JPG").read_bytes() == b"different-size"


def test_transfer_overwrite_replaces_conflict(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    make_file(raw, "A.CR3")
    make_file(jpeg, "A.JPG", b"new")
    make_file(output, "A.JPG", b"different-size")
    result = match_directories(raw, jpeg)

    transfer = transfer_matches(result.pairs, output, overwrite=True)

    assert transfer.transferred == 1
    assert (output / "A.JPG").read_bytes() == b"new"


def test_custom_extensions(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    make_file(raw, "A.NEF")
    make_file(jpeg, "A.png")

    result = match_directories(
        raw, jpeg, source_extensions=[".nef"], target_extensions=[".png"]
    )

    assert result.matched == 1
