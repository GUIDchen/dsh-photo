"""dsh-photo 的核心匹配与归档逻辑。

设计目标是零第三方依赖、可被其他脚本直接 import、行为可预测：

* 配对键 = 文件名去掉扩展名后的 NFC 规范化 + 大小写折叠；
* 同一个键只选一个 JPEG（按扩展名声明顺序、再按文件名排序），避免重复；
* 传输默认复制，支持移动、硬链接、软链接；
* 目标文件已存在且大小相同视为已完成（幂等）。
"""

from __future__ import annotations

import os
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

#: 常见 RAW 扩展名，大小写不敏感。
DEFAULT_RAW_EXTENSIONS: tuple[str, ...] = (
    ".cr3",
    ".cr2",
    ".nef",
    ".arw",
    ".raf",
    ".orf",
    ".rw2",
    ".dng",
    ".pef",
    ".srw",
)

#: 常见 JPEG 扩展名，大小写不敏感。
DEFAULT_JPEG_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg")

#: 支持的传输方式。
TRANSFER_MODES: tuple[str, ...] = ("copy", "move", "hardlink", "symlink")


def normalize_extension(extension: str) -> str:
    """把 CR3、.CR3、 cr3 统一成 .cr3。"""
    extension = str(extension).strip().lower()
    if not extension:
        return ""
    if not extension.startswith("."):
        extension = "." + extension
    return extension


def normalize_extensions(extensions: Iterable[str]) -> tuple[str, ...]:
    """去重并规范化扩展名列表，保持声明顺序。"""
    result: list[str] = []
    for extension in extensions:
        normalized = normalize_extension(extension)
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def name_key(stem: str) -> str:
    """配对键：Unicode NFC 规范化后做大小写折叠。"""
    return unicodedata.normalize("NFC", stem).casefold()


def _is_junk(name: str) -> bool:
    # macOS 的 AppleDouble 资源文件与目录元数据，不应参与配对。
    return name.startswith("._") or name == ".DS_Store"


@dataclass(frozen=True)
class FileEntry:
    """参与配对的一个文件。"""

    path: Path
    key: str


@dataclass
class MatchResult:
    """一次配对的结果。"""

    pairs: list[tuple[Path, Path]] = field(default_factory=list)
    source_without_target: list[Path] = field(default_factory=list)
    target_without_source: list[Path] = field(default_factory=list)
    ambiguous_targets: dict[str, list[Path]] = field(default_factory=dict)
    source_count: int = 0
    target_count: int = 0

    @property
    def matched(self) -> int:
        """命中的对数。"""
        return len(self.pairs)


def scan_directory(
    directory: os.PathLike[str] | str,
    extensions: Sequence[str],
) -> list[FileEntry]:
    """扫描 directory 下指定扩展名的文件（不递归）。"""
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"不是目录: {directory}")

    suffixes = normalize_extensions(extensions)
    # 扩展名声明顺序决定多候选时的优先级，例如默认 .jpg 优先于 .jpeg。
    suffix_priority = {suffix: index for index, suffix in enumerate(suffixes)}
    entries: list[FileEntry] = []
    with os.scandir(directory) as iterator:
        for item in iterator:
            if not item.is_file():
                continue
            if _is_junk(item.name):
                continue
            path = Path(item.path)
            if path.suffix.lower() not in suffix_priority:
                continue
            entries.append(FileEntry(path=path, key=name_key(path.stem)))

    entries.sort(
        key=lambda entry: (
            suffix_priority[entry.path.suffix.lower()],
            entry.path.name.casefold(),
        )
    )
    return entries


def _group(entries: Sequence[FileEntry]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {}
    for entry in entries:
        grouped.setdefault(entry.key, []).append(entry.path)
    return grouped


def match_entries(
    source_entries: Sequence[FileEntry],
    target_entries: Sequence[FileEntry],
) -> MatchResult:
    """对已扫描的条目做同名配对。"""
    source = _group(source_entries)
    target = _group(target_entries)

    pairs: list[tuple[Path, Path]] = []
    ambiguous: dict[str, list[Path]] = {}
    for key in sorted(source):
        targets = target.get(key)
        if not targets:
            continue
        if len(targets) > 1:
            ambiguous[key] = list(targets)
        chosen = targets[0]
        for source_path in source[key]:
            pairs.append((source_path, chosen))

    source_keys = set(source)
    target_keys = set(target)
    return MatchResult(
        pairs=pairs,
        source_without_target=[
            entry.path for entry in source_entries if entry.key not in target_keys
        ],
        target_without_source=[
            entry.path for entry in target_entries if entry.key not in source_keys
        ],
        ambiguous_targets=ambiguous,
        source_count=len(source_entries),
        target_count=len(target_entries),
    )


def match_directories(
    source_dir: os.PathLike[str] | str,
    target_dir: os.PathLike[str] | str,
    source_extensions: Sequence[str] = DEFAULT_RAW_EXTENSIONS,
    target_extensions: Sequence[str] = DEFAULT_JPEG_EXTENSIONS,
) -> MatchResult:
    """扫描两个目录并按同名规则配对。"""
    source_entries = scan_directory(source_dir, source_extensions)
    target_entries = scan_directory(target_dir, target_extensions)
    return match_entries(source_entries, target_entries)


@dataclass
class TransferResult:
    """一次归档操作的结果。"""

    transferred: int = 0
    skipped: int = 0
    conflicts: list[tuple[Path, Path]] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.errors)


def _same_size(first: Path, second: Path) -> bool:
    try:
        return first.stat().st_size == second.stat().st_size
    except OSError:
        return False


def transfer_matches(
    pairs: Iterable[tuple[Path, Path]],
    output_dir: os.PathLike[str] | str,
    mode: str = "copy",
    overwrite: bool = False,
    dry_run: bool = False,
) -> TransferResult:
    """把配对结果中的 JPEG 归档到 output_dir（默认平铺）。"""
    if mode not in TRANSFER_MODES:
        raise ValueError(
            f"未知的传输模式: {mode!r}（可选: {', '.join(TRANSFER_MODES)}）"
        )

    output_dir = Path(output_dir)
    result = TransferResult()
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for _source_path, target_path in pairs:
        destination = output_dir / target_path.name
        try:
            if destination.exists():
                if _same_size(destination, target_path):
                    # 已经归档过同一个文件，视为完成。
                    result.skipped += 1
                    continue
                if not overwrite:
                    result.conflicts.append((target_path, destination))
                    result.skipped += 1
                    continue

            if dry_run:
                result.transferred += 1
                continue

            if mode == "copy":
                shutil.copy2(target_path, destination)
            elif mode == "move":
                shutil.move(str(target_path), str(destination))
            elif mode == "hardlink":
                os.link(target_path, destination)
            elif mode == "symlink":
                os.symlink(target_path.resolve(), destination)
            result.transferred += 1
        except OSError as exc:
            result.errors.append((target_path, str(exc)))

    return result
