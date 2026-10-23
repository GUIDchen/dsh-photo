"""dsh-photo：按文件名把 RAW 照片与同名 JPEG 配对并归档。"""

from .matcher import (
    DEFAULT_JPEG_EXTENSIONS,
    DEFAULT_RAW_EXTENSIONS,
    TRANSFER_MODES,
    FileEntry,
    MatchResult,
    TransferResult,
    match_directories,
    match_entries,
    name_key,
    normalize_extension,
    normalize_extensions,
    scan_directory,
    transfer_matches,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DEFAULT_JPEG_EXTENSIONS",
    "DEFAULT_RAW_EXTENSIONS",
    "TRANSFER_MODES",
    "FileEntry",
    "MatchResult",
    "TransferResult",
    "match_directories",
    "match_entries",
    "name_key",
    "normalize_extension",
    "normalize_extensions",
    "scan_directory",
    "transfer_matches",
]
