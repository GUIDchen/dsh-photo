# dsh-photo

> 按文件名把 RAW 照片与同名 JPEG 配对，并把命中的 JPEG 单独归档到一个目录。

[![CI](https://github.com/GUIDchen/dsh-photo/actions/workflows/ci.yml/badge.svg)](https://github.com/GUIDchen/dsh-photo/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

**English:** A zero-dependency CLI that pairs RAW photos with same-named JPEGs and archives the matched JPEGs into a separate folder.

---

## 为什么需要它

摄影工作流里经常出现两个平行目录：

```
20261003雅惠恒发/
├── raw/       # 相机原始文件，如 HP7A4477.CR3
└── JPEG/      # 相机或后期导出的 JPEG，如 HP7A4477.JPG
```

当你想「只把入选的那批 RAW 对应的 JPEG 挑出来」时，手动比对文件名既慢又容易漏。`dsh-photo` 用一条命令完成这件事：

- 以 RAW 目录为基准，逐个取文件名主干；
- 在 JPEG 目录里找同名文件（大小写不敏感）；
- 把命中的 JPEG 复制到独立目录，原文件保持不动。

## 特性

- **按文件名配对**：忽略大小写，兼容 macOS 与 Windows 的命名差异。
- **多 RAW 格式**：默认支持 CR3、CR2、NEF、ARW、RAF、ORF、RW2、DNG、PEF、SRW，可用参数扩展。
- **四种归档方式**：复制、移动、硬链接、软链接。
- **先预演再动手**：`--dry-run` 只统计不写盘。
- **可核对报告**：`--report` 输出 CSV，列出命中、缺失与多余。
- **幂等且防覆盖**：目标文件大小相同视为已完成；大小不同默认跳过并记为冲突，`--overwrite` 才覆盖。
- **零第三方依赖**：只用 Python 标准库，Python 3.9+ 即可运行。

## 安装

需要 Python 3.9 或更高版本。

从 GitHub 安装（推荐用 pipx 隔离环境）：

```bash
pipx install git+https://github.com/GUIDchen/dsh-photo.git
```

或克隆后以开发模式安装：

```bash
git clone https://github.com/GUIDchen/dsh-photo.git
cd dsh-photo
python3 -m pip install -e ".[dev]"
```

安装后即可使用 `dsh-photo` 命令，也可以用 `python -m dsh_photo` 调用。

## 快速开始

先预演，确认数量无误：

```bash
dsh-photo "/path/to/raw" "/path/to/JPEG" -o "/path/to/匹配JPEG" --dry-run
```

再正式复制：

```bash
dsh-photo "/path/to/raw" "/path/to/JPEG" -o "/path/to/匹配JPEG"
```

同时生成可核对的 CSV：

```bash
dsh-photo "/path/to/raw" "/path/to/JPEG" -o "/path/to/匹配JPEG" \
          --report "/path/to/report.csv"
```

## 真实案例

2026-10-03 的一次人像约拍，目录结构正是本文开头的形式：

| 项目 | 数量 |
| --- | ---: |
| `raw/` 下 `.CR3` 原始照片 | 1832 |
| `JPEG/` 下 `.JPG`（相机导出） | 3402 |
| 同名匹配并归档 | **1823** |
| 仅 RAW 有、JPEG 缺失 | 9 |
| 仅 JPEG 有、RAW 没有 | 1579 |
| 归档体积 | 约 12 GB |

命令：

```bash
dsh-photo "/Volumes/Samsung/约拍/20261003雅惠恒发/raw" \
          "/Volumes/Samsung/约拍/20261003雅惠恒发/JPEG" \
          -o "/Volumes/Samsung/约拍/20261003雅惠恒发/匹配JPEG"
```

输出摘要：

```text
RAW 基准目录 : /Volumes/Samsung/约拍/20261003雅惠恒发/raw  （1832 个文件）
JPEG 候选目录: /Volumes/Samsung/约拍/20261003雅惠恒发/JPEG  （3402 个文件）
同名匹配     : 1823
仅 RAW 有    : 9（无同名 JPEG）
仅 JPEG 有   : 1579（无同名 RAW）
[copy] 输出目录: /Volumes/Samsung/约拍/20261003雅惠恒发/匹配JPEG
[copy] 处理: 1823  跳过: 0  冲突: 0  失败: 0
```

## 工作原理

1. **扫描**：分别读取两个目录下指定扩展名的文件（不递归），跳过 macOS 的 `._*` 资源文件与 `.DS_Store`。
2. **建键**：对文件名去掉扩展名后做 Unicode NFC 规范化与大小写折叠，得到配对键。例如 `HP7A4477.CR3` 与 `hp7a4477.jpg` 都归一到 `hp7a4477`。
3. **配对**：以 RAW 目录的键为准，在 JPEG 目录中查找同名文件。同名的多个 JPEG 只取排序最前的一个，并在摘要中提示「同名多候选」。
4. **归档**：把命中的 JPEG 平铺复制到输出目录；目标已存在且大小相同则跳过。
5. **报告**：可选写出 CSV，包含 `matched`、`raw_only`、`jpeg_only` 三类记录。

## 命令行参考

```text
dsh-photo RAW_DIR JPEG_DIR [选项]
```

| 参数 | 说明 |
| --- | --- |
| `RAW_DIR` | RAW 照片目录，作为配对基准 |
| `JPEG_DIR` | JPEG 照片目录，被筛选对象 |
| `-o, --output` | 输出目录，默认 `<JPEG_DIR 的父目录>/matched` |
| `--source-ext` | RAW 扩展名，可重复，默认 `.cr3 .cr2 .nef .arw .raf .orf .rw2 .dng .pef .srw` |
| `--target-ext` | JPEG 扩展名，可重复，默认 `.jpg .jpeg` |
| `--mode` | `copy`（默认）、`move`、`hardlink`、`symlink` |
| `--overwrite` | 目标同名但大小不同时覆盖 |
| `--dry-run` | 只统计与打印，不写盘 |
| `--report CSV` | 写出明细报告 |
| `--show N` | 额外打印前 N 条命中记录 |
| `-q, --quiet` | 只输出最终摘要 |
| `--version` | 打印版本 |

退出码：`0` 成功；`1` 有文件处理失败；`2` 目录不存在或无权限。

## 报告格式

CSV 使用带 BOM 的 UTF-8 编码，Excel 可直接打开中文路径：

| status | stem | raw_path | jpeg_path | output_path |
| --- | --- | --- | --- | --- |
| matched | HP7A4477 | /raw/HP7A4477.CR3 | /JPEG/HP7A4477.JPG | /匹配JPEG/HP7A4477.JPG |
| raw_only | HP7A4481 | /raw/HP7A4481.CR3 | | |
| jpeg_only | HP7A9999 | | /JPEG/HP7A9999.JPG | |

## 安全与边界

- **只处理平面目录**：当前版本不递归子目录，适合「RAW 一个目录、JPEG 一个目录」的标准结构。
- **默认不覆盖**：目标文件已存在且大小不同时跳过并提示，避免误伤已有成果。
- **复制优先**：`--mode copy` 不动原 JPEG；需要移动时显式使用 `--mode move`。
- **仅按文件名配对**：不读取 EXIF，也不校验图像内容。若两个不同文件恰好同名，会被视为一对。
- **先预演**：面对大批量或重要素材，建议先 `--dry-run` 并核对 `--report`。

## 开发

```bash
git clone https://github.com/GUIDchen/dsh-photo.git
cd dsh-photo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

项目结构：

```text
dsh-photo/
├── src/dsh_photo/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py        # 命令行入口
│   └── matcher.py    # 扫描、配对、归档核心
├── tests/
│   ├── test_cli.py
│   └── test_matcher.py
├── .github/workflows/ci.yml
├── pyproject.toml
└── README.md
```

## 贡献

欢迎提 Issue 与 Pull Request。提交前请确保：

1. `pytest -q` 全部通过；
2. 新增行为有对应测试；
3. 提交信息遵循约定式提交，例如 `feat: 支持递归扫描子目录`。

## 许可证

[MIT](LICENSE) © 2026 GUIDchen
