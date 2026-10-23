from pathlib import Path

from dsh_photo.cli import main


def make_file(directory: Path, name: str, content: bytes = b"x") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return path


def test_cli_dry_run_reports_and_writes_nothing(tmp_path, capsys):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    make_file(raw, "A.CR3")
    make_file(jpeg, "A.JPG")
    make_file(jpeg, "B.JPG")

    code = main([str(raw), str(jpeg), "-o", str(output), "--dry-run"])

    captured = capsys.readouterr()
    assert code == 0
    assert "同名匹配" in captured.out
    assert "仅 JPEG 有   : 1" in captured.out
    assert not output.exists()


def test_cli_writes_report(tmp_path):
    raw = tmp_path / "raw"
    jpeg = tmp_path / "JPEG"
    output = tmp_path / "out"
    report = tmp_path / "report.csv"
    make_file(raw, "A.CR3")
    make_file(jpeg, "A.JPG")
    make_file(jpeg, "B.JPG")

    code = main([str(raw), str(jpeg), "-o", str(output), "--report", str(report)])

    assert code == 0
    text = report.read_text(encoding="utf-8-sig")
    assert "matched" in text
    assert "jpeg_only" in text


def test_cli_missing_directory_returns_2(tmp_path, capsys):
    code = main([str(tmp_path / "nope"), str(tmp_path / "JPEG")])

    captured = capsys.readouterr()
    assert code == 2
    assert "错误" in captured.err
