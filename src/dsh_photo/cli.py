"""dsh-photo 命令行入口。"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import __version__
from .matcher import (
    DEFAULT_JPEG_EXTENSIONS,
    DEFAULT_RAW_EXTENSIONS,
    TRANSFER_MODES,
    MatchResult,
    match_directories,
    transfer_matches,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dsh-photo",
        description="按文件名把 RAW 照片与同名 JPEG 配对，并把命中的 JPEG 单独归档到一个目录。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  dsh-photo raw JPEG -o 匹配JPEG --dry-run\n"
            "  dsh-photo raw JPEG -o 匹配JPEG --report report.csv\n"
            "  dsh-photo raw JPEG -o 匹配JPEG --mode hardlink\n"
        ),
    )
    parser.add_argument("raw_dir", type=Path, help="RAW 照片目录（配对基准）")
    parser.add_argument("jpeg_dir", type=Path, help="JPEG 照片目录（被筛选对象）")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出目录；默认 <JPEG 目录的父目录>/matched",
    )
    parser.add_argument(
        "--source-ext",
        action="append",
        metavar="EXT",
        help=f"RAW 扩展名，可重复；默认 {', '.join(DEFAULT_RAW_EXTENSIONS)}",
    )
    parser.add_argument(
        "--target-ext",
        action="append",
        metavar="EXT",
        help=f"JPEG 扩展名，可重复；默认 {', '.join(DEFAULT_JPEG_EXTENSIONS)}",
    )
    parser.add_argument(
        "--mode",
        choices=TRANSFER_MODES,
        default="copy",
        help="传输方式：copy（默认）、move、hardlink、symlink",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="目标同名但大小不同时覆盖；默认跳过并记为冲突",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只计算并打印结果，不写磁盘",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        metavar="CSV",
        help="把命中与未命中明细写入 CSV（UTF-8 BOM，方便 Excel 打开）",
    )
    parser.add_argument(
        "--show",
        type=int,
        default=0,
        metavar="N",
        help="额外打印前 N 条命中记录（0 表示不打印）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只输出最终摘要",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _print_match_summary(match: MatchResult, raw_dir: Path, jpeg_dir: Path, quiet: bool) -> None:
    if not quiet:
        print(f"RAW 基准目录 : {raw_dir}  （{match.source_count} 个文件）")
        print(f"JPEG 候选目录: {jpeg_dir}  （{match.target_count} 个文件）")
    print(f"同名匹配     : {match.matched}")
    print(f"仅 RAW 有    : {len(match.source_without_target)}（无同名 JPEG）")
    print(f"仅 JPEG 有   : {len(match.target_without_source)}（无同名 RAW）")
    if match.ambiguous_targets:
        print(
            f"同名多候选   : {len(match.ambiguous_targets)}（每组取排序最前的一个）"
        )


def _write_report(path: Path, match: MatchResult, output_dir: Path) -> Path:
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["status", "stem", "raw_path", "jpeg_path", "output_path"])
        for raw_path, jpeg_path in match.pairs:
            writer.writerow(
                [
                    "matched",
                    jpeg_path.stem,
                    str(raw_path),
                    str(jpeg_path),
                    str(output_dir / jpeg_path.name),
                ]
            )
        for raw_path in match.source_without_target:
            writer.writerow(["raw_only", raw_path.stem, str(raw_path), "", ""])
        for jpeg_path in match.target_without_source:
            writer.writerow(["jpeg_only", jpeg_path.stem, "", str(jpeg_path), ""])
    return path


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    source_extensions = args.source_ext or DEFAULT_RAW_EXTENSIONS
    target_extensions = args.target_ext or DEFAULT_JPEG_EXTENSIONS
    output_dir: Path = args.output or (args.jpeg_dir.parent / "matched")

    try:
        match = match_directories(
            args.raw_dir, args.jpeg_dir, source_extensions, target_extensions
        )
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"错误: 没有权限读取目录（{exc.filename}）", file=sys.stderr)
        return 2

    _print_match_summary(match, args.raw_dir, args.jpeg_dir, args.quiet)

    for raw_path, jpeg_path in match.pairs[: max(0, args.show)]:
        print(f"  {raw_path.name}  ->  {jpeg_path.name}")

    mode_label = "预演" if args.dry_run else args.mode
    print(f"[{mode_label}] 输出目录: {output_dir}")

    transfer = transfer_matches(
        match.pairs,
        output_dir,
        mode=args.mode,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    print(
        f"[{mode_label}] 处理: {transfer.transferred}"
        f"  跳过: {transfer.skipped}"
        f"  冲突: {len(transfer.conflicts)}"
        f"  失败: {len(transfer.errors)}"
    )

    if not args.quiet:
        for target_path, destination in transfer.conflicts[:5]:
            print(
                f"  冲突: {destination.name} 已存在且大小不同（可用 --overwrite 覆盖）"
            )
        for target_path, reason in transfer.errors[:5]:
            print(f"  失败: {target_path} -> {reason}")

    if args.report is not None:
        report_path = _write_report(args.report, match, output_dir)
        print(f"报告已写入: {report_path}")

    return 1 if transfer.errors else 0
