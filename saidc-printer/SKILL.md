---
name: saidc-printer
description: 自动安装公司各楼层富士胶片（FUJIFILM/Fuji Xerox）ApeosPort C5570 网络打印机驱动到 Windows 或 macOS 电脑。当用户要求安装打印机、安装打印机驱动、配置网络打印机，或提到楼层打印机（一层/二层/四层/五层、2南、生态打印机）、C5570、5570、192.168.16.x、192.168.26.188、FF K505p 等场景时使用。支持列出打印机映射、连通性检查、一键运行安装包、卸载旧打印机与端口。
agent_created: true
---

# Printer Driver Install

## Overview

本 skill 用于在公司 Windows（Win10/11）或 macOS 电脑上安装各楼层 ApeosPort C5570 网络打印机。每个楼层的驱动目录内含富士胶片 EzInst 一键安装程序，`EzInst/setup.ini` 已预配置好打印机名、TCP/IP 端口（RAW 9100）和默认打印机标志，运行驱动目录根下的 `setup.exe` 即完成"驱动 + 端口 + 打印机"全部安装。

楼层→打印机→驱动包映射、原始安装文档要点、故障排查见 `references/printer-map.md`。核心工具为 `scripts/install_printer.py`。

## 快速开始

驱动包根目录（默认）：`C:\Users\a3861\Desktop\超智算\打印机驱动`，可用 `--root` 参数或 `PRN_DRIVER_ROOT` 环境变量覆盖。

```bash
# 列出所有楼层打印机及其安装状态
python scripts/install_printer.py list

# 检查某楼层打印机连通性与本机现有打印机（用楼层号或 IP）
python scripts/install_printer.py status 1
python scripts/install_printer.py status 192.168.26.188

# 安装（需要管理员权限，会弹出 UAC 确认）
python scripts/install_printer.py install 1

# 安装前自动删除同名旧打印机（原安装文档要求先删旧打印机）
python scripts/install_printer.py install 1 --force

# 卸载打印机与 TCP/IP 端口（默认 dry-run，--yes 才执行）
python scripts/install_printer.py uninstall 1
python scripts/install_printer.py uninstall 1 --yes
```

楼层标识支持：`1`、`2eco`（二层生态）、`2rd`（二层研发/2南）、`4`、`5`，也可直接用 IP。

## 工作流

1. **确定楼层**：从用户表述推断目标打印机（"二楼研发的"→`2rd`，"2南"→`2rd`，"生态"→`2eco`）。无法确定时，运行 `list` 并向用户展示映射表让其选择。
2. **预检查**：运行 `status <楼层>`，确认打印机网络可达（TCP 9100）、本机是否已存在同名打印机或旧打印机。
3. **删除旧打印机**：原安装文档明确要求先删除已有的 C5570 打印机，否则安装报错。存在同名打印机时用 `install ... --force` 自动删除，或用 `uninstall` 手动处理。
4. **安装**：运行 `install <楼层>`。安装器有图形界面（setup.ini 中 Silent=0），告知用户在弹窗中：确认安装提示；出现"是否重启"时点"否"。`--silent` 参数会尝试将解包后 setup.ini 的 Silent 改为 1 实现静默安装（实验性，失败时回退交互模式）。
5. **验证**：安装完成后再次运行 `status <楼层>`，确认打印机已出现在本机打印机列表。

## 注意事项

- 驱动以解压后的目录形式存放：`一层/`、`二层生态/`、`二层研发/`、`四层/`、`五层/`（各含根级 `setup.exe` 与 `EzInst/setup.ini`）。可放本地根目录，也可存于 GitHub 仓库 `Rerauniverse/saidc-printer`；本地缺失时脚本自动下载仓库 archive 并解出对应目录（可用环境变量 `PRN_DRIVER_GITHUB_REPO` / `PRN_DRIVER_GITHUB_BRANCH` 覆盖）。
- 下载认证按优先级读取：环境变量 `GITHUB_TOKEN` → `gh auth token` → git 凭据管理器。公开仓库无凭据也可直接下载；私有仓库则需要凭据且为协作者。
- **完整性校验**：安装前脚本对 `setup.exe`、`EzInst/setup.exe`、`EzInst/verup.exe` 做 SHA256 校验（KNOWN_HASHES），与可信版本不符即拒绝安装，防止仓库内容被篡改注入恶意程序。更新驱动版本后运行 `hash <楼层>` 获取新哈希并更新脚本。
- 安装需要管理员权限；脚本通过 UAC 弹窗提升，不可在无确认的情况下静默提权。
- `setup.ini` 为 UTF-16LE 编码（带 BOM），读取时必须按 UTF-16LE 解码。
- 仓库维护时才可能需要 WinRAR 的 `UnRAR.exe`（本机位于 `C:\Program Files\WinRAR\UnRAR.exe`）来解压新的 rar 驱动包；同事安装时驱动已是解压目录，无需任何解压工具。目录中 `dl_`/`xr_` 等扩展名文件由安装器自行解包，无需预处理。
- Windows 下添加端口/打印机等操作也可用 PowerShell `Get-Printer` / `Remove-Printer` / `Get-PrinterPort` / `Remove-PrinterPort` 直接操作，脚本内部即采用此方式。
- 打印机名以各包 `setup.ini` 的 `PrinterName` 为准（如 `FF K505p for ApeosPort C5570-1层打印机`）；映射表与 INI 不一致时以 INI 为准并更新 references。

## macOS 安装

macOS 使用 `macos 苹果/ffmacprnstd2608bm120iml.dmg` 驱动包：挂载 dmg → 运行安装器 → 系统设置中添加打印机（选择对应楼层的 C5570，IPP/LPD/LPR 或"通过 IP 添加"，协议 LPD 或 IPP，地址为楼层 IP）。详细步骤参考 `references/printer-map.md` 的 macOS 一节与同目录 `安装方法.mp4` 视频教程。

## Resources

- `scripts/install_printer.py` — 映射表维护、连通性探测、解包、安装、卸载、验证的完整工具。
- `references/printer-map.md` — 楼层映射表、setup.ini 字段说明、原始图文安装文档摘要、故障排查。
