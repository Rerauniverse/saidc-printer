#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
saidc-printer: 楼层 ApeosPort C5570 打印机驱动一键安装工具

驱动以解压后的目录形式存放（本地根目录或 GitHub 仓库），本地缺失时
自动从 GitHub 仓库 archive 下载并解出对应目录。

用法:
  python install_printer.py list                 # 列出楼层打印机与安装状态
  python install_printer.py status <楼层|IP>     # 连通性与本机现有打印机检查
  python install_printer.py install <楼层> [--force] [--silent]
  python install_printer.py uninstall <楼层> [--yes]
  python install_printer.py read-ini <楼层>      # 显示包内 setup.ini 配置

环境变量 PRN_DRIVER_ROOT 或 --root 指定驱动根目录；
PRN_DRIVER_GITHUB_REPO / PRN_DRIVER_GITHUB_BRANCH 覆盖云端仓库。
"""
import argparse
import configparser
import io
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PRINTERS = [
    {"key": "1",    "label": "一层",            "ip": "192.168.16.79",
     "name": "FF K505p for ApeosPort C5570-1层打印机",
     "dir": "一层"},
    {"key": "2eco", "label": "二层生态",        "ip": "192.168.16.103",
     "name": "FF K505p for ApeosPort C5570-2层生态打印机",
     "dir": "二层生态"},
    {"key": "2rd",  "label": "二层研发(2南)",   "ip": "192.168.26.188",
     "name": "FF K505p for ApeosPort C5570-2南",
     "dir": "二层研发"},
    {"key": "4",    "label": "四层",            "ip": "192.168.16.16",
     "name": "FF K505p for ApeosPort C5570-4",
     "dir": "四层"},
    {"key": "5",    "label": "五层",            "ip": "192.168.16.31",
     "name": "FF K505p for ApeosPort C5570-5",
     "dir": "五层"},
]

DEFAULT_ROOT = r"C:\Users\a3861\Desktop\超智算\打印机驱动"
# 本地缺驱动目录时，从该 GitHub 仓库自动下载（公开仓库无需凭据）
GITHUB_REPO = os.environ.get("PRN_DRIVER_GITHUB_REPO",
                             "Rerauniverse/saidc-printer")
GITHUB_BRANCH = os.environ.get("PRN_DRIVER_GITHUB_BRANCH", "main")
UNRAR_CANDIDATES = [
    r"C:\Program Files\WinRAR\UnRAR.exe",
    r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
]

# 安装前完整性校验：防止仓库内容被篡改注入恶意程序。
# 更新驱动版本后，运行 `hash <楼层>` 重新获取并更新这里的值。
KNOWN_HASHES = {
    "setup.exe":         "2cea7c422bcb62937d12bbf38878e513eef869c3a81d02e9c697e88995a8ac0e",
    "EzInst/setup.exe":  "5be837eca063bd5b27486a8ddd2ec42b2374f1f90d0d2a9d130558c6bba27180",
    "EzInst/verup.exe":  "26166b31966f7ad580a1d5b713153b1652e780bc75a74f0a856cf860fc9e87cc",
}


def sha256_of(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hashes(driver_dir: Path):
    """安装前校验执行体哈希，被篡改则拒绝运行。"""
    bad = []
    for rel, want in KNOWN_HASHES.items():
        f = driver_dir / rel
        if not f.exists():
            continue  # 旧版本包可能没有该文件，由安装器自行处理
        got = sha256_of(f)
        if got != want:
            bad.append(f"  {rel}\n    期望 {want}\n    实际 {got}")
    if bad:
        raise SystemExit(
            "[!] 安全校验失败：安装程序与已知可信版本不符，已拒绝安装。\n"
            + "\n".join(bad)
            + "\n    若确认是官方新版驱动，请运行 hash <楼层> 核对新哈希后更新脚本中的 KNOWN_HASHES。")


def find_printer(token: str):
    """按楼层号/IP/关键字查找映射条目。"""
    t = token.strip().lower()
    for p in PRINTERS:
        if t in (p["key"].lower(), p["ip"], p["label"]) or t in p["label"]:
            return p
    raise SystemExit(f"[!] 无法识别的打印机标识: {token}。可用: "
                     + ", ".join(f"{p['key']}({p['label']}, {p['ip']})" for p in PRINTERS))


def github_token():
    """按优先级获取 GitHub 凭据: GITHUB_TOKEN 环境变量 > gh CLI > git 凭据管理器。
    公开仓库可无凭据；私有仓库则需要凭据且为协作者。"""
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t.strip()
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except FileNotFoundError:
        pass
    try:
        out = subprocess.run(["git", "credential", "fill"],
                             input="protocol=https\nhost=github.com\n\n",
                             capture_output=True, text=True, timeout=15).stdout
        d = dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)
        if d.get("password"):
            return d["password"]
    except Exception:
        pass
    return None


def github_headers():
    tok = github_token()
    h = {"User-Agent": "saidc-printer"}
    if tok:
        h["Authorization"] = f"token {tok}"
    return h


def ensure_dir(root: Path, p: dict) -> Path:
    """确保驱动目录可用：本地存在直接返回，否则从 GitHub 仓库 archive 下载。"""
    dest = root / p["dir"]
    if (dest / "EzInst" / "setup.ini").exists():
        return dest
    root.mkdir(parents=True, exist_ok=True)
    url = f"https://codeload.github.com/{GITHUB_REPO}/zip/refs/heads/{GITHUB_BRANCH}"
    auth = "（已认证）" if github_token() else ""
    print(f"[*] 本地无驱动目录，从 GitHub 下载仓库{auth}: {GITHUB_REPO} ...")
    req = urllib.request.Request(url, headers=github_headers())
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[!] 仓库下载失败 HTTP {e.code}: {url}")
    print(f"[*] 下载完成 {len(data)/1e6:.1f} MB，解压中 ...")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(root)
    repo_name = GITHUB_REPO.split("/")[-1] + "-" + GITHUB_BRANCH
    src = root / repo_name / p["dir"]
    if not src.exists():
        raise SystemExit(f"[!] 仓库中未找到目录 {p['dir']}，请确认仓库已更新。")
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(src), str(dest))
    # 清理 archive 解出的仓库根目录残留
    repo_root = root / repo_name
    if repo_root.exists():
        shutil.rmtree(repo_root, ignore_errors=True)
    print(f"[*] 驱动目录就绪 -> {dest}")
    return dest


def setup_ini_text(driver_dir: Path) -> str:
    raw = (driver_dir / "EzInst" / "setup.ini").read_bytes()
    return raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")


def parse_ini(text: str) -> dict:
    cp = configparser.ConfigParser(strict=False, inline_comment_prefixes=(";",))
    cp.optionxform = str  # 保留键名大小写（PrinterName 等）
    cp.read_string(text)
    d = dict(cp["DriverInfo"]) if cp.has_section("DriverInfo") else {}
    d.update(dict(cp["TCP/IP"]) if cp.has_section("TCP/IP") else {})
    return d


def tcp_probe(ip: str, port: int = 9100, timeout: float = 2.5) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def ps(cmd: str) -> str:
    # 中文 Windows 控制台 PowerShell 默认输出编码为 GBK
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, text=True,
                       encoding="gbk", errors="replace")
    return (r.stdout or "").strip()


def get_local_printers() -> str:
    return ps("Get-Printer | Select-Object Name,PortName,DriverName "
              "| Format-Table -AutoSize | Out-String -Width 200")


def remove_printer_and_port(name: str, ip: str):
    ps(f'Remove-Printer -Name "{name}" -ErrorAction SilentlyContinue')
    ps(f'Get-PrinterPort | Where-Object {{$_.Name -like "*{ip}*" -or $_.Name -eq "IP_{ip}"}} '
       f'| Remove-PrinterPort -ErrorAction SilentlyContinue')


def cmd_list(args):
    root = Path(args.root)
    installed = get_local_printers()
    print(f"驱动根目录: {root}")
    print(f"{'标识':<5}{'楼层':<10}{'IP':<18}{'驱动目录':<30}{'网络':<6}已安装")
    for p in PRINTERS:
        d = root / p["dir"]
        net = "通" if tcp_probe(p["ip"]) else "不通"
        has = "是" if p["name"] in installed else "否"
        if (d / "EzInst" / "setup.ini").exists():
            d_ok = "√本地"
        else:
            d_ok = "↧云端可下载"
        print(f"{p['key']:<5}{p['label']:<10}{p['ip']:<18}{d_ok+' '+p['dir']:<30}{net:<6}{has}")
    print("\n本机现有打印机:")
    print(installed or "  （无）")


def cmd_status(args):
    p = find_printer(args.token)
    print(f"[{p['label']}] {p['name']}")
    print(f"IP: {p['ip']}  端口: TCP 9100 (RAW)  -> ", end="")
    print("打印机在线" if tcp_probe(p["ip"]) else "打印机不可达（检查网段/开关机/IP 变更）")
    print("\n本机现有打印机:")
    print(get_local_printers() or "  （无）")


def cmd_read_ini(args):
    p = find_printer(args.token)
    d = ensure_dir(Path(args.root), p)
    ini = parse_ini(setup_ini_text(d))
    for k, v in ini.items():
        print(f"{k} = {v}")
    if p["name"] != ini.get("PrinterName"):
        print(f"\n[!] 注意: 映射表打印机名与 setup.ini 不一致，以 INI 为准: "
              f"{ini.get('PrinterName')!r}。请更新 references/printer-map.md 与脚本映射。")


def cmd_install(args):
    p = find_printer(args.token)
    pkgdir = ensure_dir(Path(args.root), p)

    ini = parse_ini(setup_ini_text(pkgdir))
    name = ini.get("PrinterName", p["name"])
    ip = ini.get("HostName", p["ip"])
    print(f"目标: [{p['label']}] {name} @ {ip} (TCP {ini.get('PortNumber','9100')})")

    if not tcp_probe(ip):
        print(f"[!] 打印机 {ip} 当前不可达，继续安装仍会建立端口，打印时可能脱机。")

    # 安装文档要求: 先删除原有打印机，否则报错
    local = get_local_printers()
    if name in local:
        if args.force:
            print(f"[*] --force: 删除已存在的同名打印机 {name}")
            remove_printer_and_port(name, ip)
        else:
            print(f"[!] 本机已存在同名打印机 {name}。原安装文档要求先删除旧打印机再安装。")
            print("    使用 --force 自动删除后安装，或运行 uninstall <楼层> --yes。")
            return 1

    ini_path = pkgdir / "EzInst" / "setup.ini"
    if args.silent and ini_path.exists():
        text = ini_path.read_bytes().decode("utf-16-le").lstrip("\ufeff")
        text = text.replace("Silent=0", "Silent=1")
        ini_path.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
        print("[*] 已尝试将 setup.ini 的 Silent 置 1（静默模式，实验性）")

    setup_exe = pkgdir / "setup.exe"
    if not setup_exe.exists():
        raise SystemExit(f"[!] 未找到安装入口: {setup_exe}")

    verify_hashes(pkgdir)

    print("[*] 启动安装器（如弹出 UAC 请确认；安装窗口中点确认，完成后询问重启时点\"否\"）...")
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{setup_exe}' -WorkingDirectory '{pkgdir}' -Verb RunAs -Wait; $LASTEXITCODE"],
    )
    ok = name in get_local_printers()
    print(f"\n[*] 安装器退出，验证结果: 打印机 {'已安装 √' if ok else '未检测到 ×'}")
    if not ok:
        print(get_local_printers())
    return 0 if ok else 1


def cmd_uninstall(args):
    p = find_printer(args.token)
    d = Path(args.root) / p["dir"]
    ini = parse_ini(setup_ini_text(d)) if (d / "EzInst" / "setup.ini").exists() else {}
    name = ini.get("PrinterName", p["name"])
    ip = ini.get("HostName", p["ip"])
    print(f"目标: 删除打印机 {name!r} 及与 {ip} 相关的端口")
    if not args.yes:
        print("[!] 这是演练(dry-run)，确认无误后加 --yes 执行删除。")
        return 0
    remove_printer_and_port(name, ip)
    ok = name not in get_local_printers()
    print("[*] 删除完成" if ok else "[!] 仍检测到打印机，请检查系统设置")
    return 0 if ok else 1


def cmd_hash(args):
    """打印驱动目录中执行体的 SHA256，用于驱动升级后更新 KNOWN_HASHES。"""
    p = find_printer(args.token)
    d = ensure_dir(Path(args.root), p)
    for rel in KNOWN_HASHES:
        f = d / rel
        if f.exists():
            print(f'    "{rel}": "{sha256_of(f)}",')
        else:
            print(f'    "{rel}": (文件不存在)')
    print("确认可信后，将以上值更新到脚本中的 KNOWN_HASHES。")


def main():
    ap = argparse.ArgumentParser(description="楼层 C5570 打印机驱动安装工具")
    ap.add_argument("--root", default=os.environ.get("PRN_DRIVER_ROOT", DEFAULT_ROOT),
                    help="驱动包根目录")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list", help="列出映射与安装状态")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("status", help="连通性与本机打印机检查")
    s.add_argument("token", help="楼层标识或 IP")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("read-ini", help="读取包内 setup.ini")
    s.add_argument("token")
    s.set_defaults(fn=cmd_read_ini)
    s = sub.add_parser("hash", help="打印执行体 SHA256（用于升级后更新校验值）")
    s.add_argument("token")
    s.set_defaults(fn=cmd_hash)
    s = sub.add_parser("install", help="一键安装")
    s.add_argument("token")
    s.add_argument("--force", action="store_true", help="安装前自动删除同名旧打印机")
    s.add_argument("--silent", action="store_true", help="尝试静默安装（实验性）")
    s.set_defaults(fn=cmd_install)
    s = sub.add_parser("uninstall", help="卸载打印机与端口")
    s.add_argument("token")
    s.add_argument("--yes", action="store_true", help="真正执行删除（默认演练）")
    s.set_defaults(fn=cmd_uninstall)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
