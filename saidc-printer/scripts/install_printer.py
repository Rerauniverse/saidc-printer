#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
printer-driver-install: 楼层 ApeosPort C5570 打印机驱动一键安装工具

用法:
  python install_printer.py list                 # 列出楼层打印机与安装状态
  python install_printer.py status <楼层|IP>     # 连通性与本机现有打印机检查
  python install_printer.py install <楼层> [--force] [--silent]
  python install_printer.py uninstall <楼层> [--yes]
  python install_printer.py read-ini <楼层>      # 显示包内 setup.ini 配置

环境变量 PRN_DRIVER_ROOT 或 --root 指定驱动包根目录。
"""
import argparse
import configparser
import io
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PRINTERS = [
    {"key": "1",    "label": "一层",            "ip": "192.168.16.79",
     "name": "FF K505p for ApeosPort C5570-1层打印机",
     "pkg": "一层5570打印安装包16.79.zip"},
    {"key": "2eco", "label": "二层生态",        "ip": "192.168.16.103",
     "name": "FF K505p for ApeosPort C5570-2层生态打印机",
     "pkg": "二层生态5570打印安装包16.103.zip"},
    {"key": "2rd",  "label": "二层研发(2南)",   "ip": "192.168.26.188",
     "name": "FF K505p for ApeosPort C5570-2南",
     "pkg": "二层研发打印驱动26.188.rar"},
    {"key": "4",    "label": "四层",            "ip": "192.168.16.16",
     "name": "FF K505p for ApeosPort C5570-4",
     "pkg": "四层打印驱动16.16.rar"},
    {"key": "5",    "label": "五层",            "ip": "192.168.16.31",
     "name": "FF K505p for ApeosPort C5570-5",
     "pkg": "五层打印驱动16.31.rar"},
]

DEFAULT_ROOT = r"C:\Users\a3861\Desktop\超智算\打印机驱动"
UNRAR_CANDIDATES = [
    r"C:\Program Files\WinRAR\UnRAR.exe",
    r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
]


def find_printer(token: str):
    """按楼层号/IP/关键字查找映射条目。"""
    t = token.strip().lower()
    for p in PRINTERS:
        if t in (p["key"].lower(), p["ip"], p["label"]) or t in p["label"]:
            return p
    raise SystemExit(f"[!] 无法识别的打印机标识: {token}。可用: "
                     + ", ".join(f"{p['key']}({p['label']}, {p['ip']})" for p in PRINTERS))


def find_unrar():
    for c in UNRAR_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def extract_setup_ini(pkg_path: Path) -> str:
    """从 zip/rar 驱动包中直接读出 EzInst/setup.ini 的文本内容。"""
    ext = pkg_path.suffix.lower()
    if ext == ".zip":
        with zipfile.ZipFile(pkg_path) as z:
            entry = next(n for n in z.namelist()
                         if n.upper().endswith("EZINST/SETUP.INI"))
            raw = z.read(entry)
    elif ext == ".rar":
        unrar = find_unrar()
        if not unrar:
            raise SystemExit("[!] 未找到 UnRAR.exe（WinRAR），无法读取 rar 包")
        lst = subprocess.run([unrar, "lb", "-p-", "--", str(pkg_path)],
                             capture_output=True).stdout.decode("gbk", "replace")
        entry = next(l for l in lst.splitlines() if l.lower().endswith("ezinst/setup.ini"))
        raw = subprocess.run([unrar, "p", "-inul", "-p-", "--", str(pkg_path), entry],
                             capture_output=True).stdout
    else:
        raise SystemExit(f"[!] 不支持的包类型: {pkg_path}")
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


def extract_pkg(pkg_path: Path, dest: Path):
    ext = pkg_path.suffix.lower()
    if ext == ".zip":
        with zipfile.ZipFile(pkg_path) as z:
            z.extractall(dest)
    else:
        unrar = find_unrar()
        if not unrar:
            raise SystemExit("[!] 未找到 UnRAR.exe（WinRAR），请安装 WinRAR 后重试")
        subprocess.run([unrar, "x", "-y", "-p-", "--", str(pkg_path), str(dest) + "\\"],
                       check=True, capture_output=True)


def cmd_list(args):
    root = Path(args.root)
    installed = get_local_printers()
    print(f"驱动包根目录: {root}")
    print(f"{'标识':<5}{'楼层':<10}{'IP':<18}{'包':<34}{'网络':<6}已安装")
    for p in PRINTERS:
        pkg = root / p["pkg"]
        net = "通" if tcp_probe(p["ip"]) else "不通"
        has = "是" if p["name"] in installed else "否"
        pkgok = "√" if pkg.exists() else "×缺包"
        print(f"{p['key']:<5}{p['label']:<10}{p['ip']:<18}{pkgok+' '+p['pkg']:<34}{net:<6}{has}")
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
    root = Path(args.root)
    pkg = root / p["pkg"]
    if not pkg.exists():
        raise SystemExit(f"[!] 找不到驱动包: {pkg}")
    ini = parse_ini(extract_setup_ini(pkg))
    for k, v in ini.items():
        print(f"{k} = {v}")
    if p["name"] != ini.get("PrinterName"):
        print(f"\n[!] 注意: 映射表打印机名与 setup.ini 不一致，以 INI 为准: "
              f"{ini.get('PrinterName')!r}。请更新 references/printer-map.md 与脚本映射。")


def cmd_install(args):
    p = find_printer(args.token)
    root = Path(args.root)
    pkg = root / p["pkg"]
    if not pkg.exists():
        raise SystemExit(f"[!] 找不到驱动包: {pkg}")

    ini = parse_ini(extract_setup_ini(pkg))
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

    workdir = Path(tempfile.mkdtemp(prefix=f"prn_install_{p['key']}_"))
    print(f"[*] 解压驱动包 -> {workdir}")
    extract_pkg(pkg, workdir)
    pkgdir = next(d for d in workdir.iterdir() if d.is_dir())

    ini_path = pkgdir / "EzInst" / "setup.ini"
    if args.silent and ini_path.exists():
        text = ini_path.read_bytes().decode("utf-16-le").lstrip("\ufeff")
        text = text.replace("Silent=0", "Silent=1")
        ini_path.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
        print("[*] 已尝试将 setup.ini 的 Silent 置 1（静默模式，实验性）")

    setup_exe = pkgdir / "setup.exe"
    if not setup_exe.exists():
        raise SystemExit(f"[!] 未找到安装入口: {setup_exe}")

    print("[*] 启动安装器（如弹出 UAC 请确认；安装窗口中点确认，完成后询问重启时点\"否\"）...")
    run = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{setup_exe}' -WorkingDirectory '{pkgdir}' -Verb RunAs -Wait; $LASTEXITCODE"],
    )
    ok = name in get_local_printers()
    print(f"\n[*] 安装器退出，验证结果: 打印机 {'已安装 √' if ok else '未检测到 ×'}")
    if not ok:
        print(get_local_printers())
    if ok:
        print(f"[*] 清理临时目录 {workdir}")
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"[!] 临时目录保留供排查: {workdir}")
    return 0 if ok else 1


def cmd_uninstall(args):
    p = find_printer(args.token)
    ini = parse_ini(extract_setup_ini(Path(args.root) / p["pkg"])) \
        if (Path(args.root) / p["pkg"]).exists() else {}
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
