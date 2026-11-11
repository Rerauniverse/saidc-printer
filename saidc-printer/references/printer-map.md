# 楼层打印机映射与安装参考

## 楼层 → 打印机 → 驱动包映射

驱动型号全部为 `FF K505p for ApeosPort C5570 PCL 6`，端口协议均为 RAW 9100（Standard TCP/IP Port，SNMP 关闭），均为默认打印机（DefaultPrinter=1）。

| 楼层标识 | 显示 | 打印机名 (PrinterName) | IP (OutPort/HostName) | 驱动包文件 |
|---|---|---|---|---|
| `1` | 一层 | FF K505p for ApeosPort C5570-1层打印机 | 192.168.16.79 | 一层5570打印安装包16.79.zip |
| `2eco` | 二层生态 | FF K505p for ApeosPort C5570-2层生态打印机 | 192.168.16.103 | 二层生态5570打印安装包16.103.zip |
| `2rd` | 二层研发（2南） | FF K505p for ApeosPort C5570-2南 | 192.168.26.188 | 二层研发打印驱动26.188.rar |
| `4` | 四层 | FF K505p for ApeosPort C5570-4 | 192.168.16.16 | 四层打印驱动16.16.rar |
| `5` | 五层 | FF K505p for ApeosPort C5570-5 | 192.168.16.31 | 五层打印驱动16.31.rar |

> 注：文件名末尾的数字即打印机 IP 的最后一段。若新增打印机，把新包放入根目录、读取包内 `EzInst/setup.ini` 更新本表与脚本中的映射。

## 驱动包结构（zip 与 rar 相同）

```
<包名>/
├── setup.exe        ← 包根目录的一键安装入口（双击或管理员运行）
├── setup.dat        ← 安装器配置（加密）
└── EzInst/
    ├── setup.exe    ← 实际安装引擎（由根目录 setup.exe 调起）
    ├── setup.ini    ← 关键配置（UTF-16LE，含打印机名/IP/端口）
    ├── FF6BSAL.inf  ← 驱动 INF（FF K505p，覆盖 C3070~C7070 系列）
    ├── FF6BSAL.cat
    └── （驱动文件，dl_/xr_/ch_ 等为 LZ 压缩）
```

### setup.ini 关键字段（[DriverInfo] / [TCP/IP]）

- `Driver`：驱动名（INF 中的型号）
- `PrinterName`：安装后显示的打印机名（含楼层标记）
- `OutPort` / `HostName`：打印机 IP
- `PortMonitor`：Standard TCP/IP Port
- `Protocol=1`：RAW；`PortNumber=9100`
- `DefaultPrinter=1`：设为默认打印机
- `Silent=0`：安装器带 UI（确认安装 + 完成后询问是否重启）；改为 1 理论上可静默（实验性）

## 原图文安装文档摘要（Win10 一键安装方法.doc）

文档以截图为主，文字要点：

1. **先删除原有打印机**，否则会报错（原投资办公室打印机）。路径：设置 → 蓝牙和其他设备 → 打印机和扫描仪 → 选中 C5570 → 删除。
2. 进入驱动包目录，**左键双击 `setup`**（包根目录的 setup.exe）。
3. 或者**右键 → 以管理员身份运行**。
4. 弹出"安装驱动程序信任"对话框：**确认安装设置并单击安装**。
5. 安装完成弹出"设置工具：驱动程序已安装成功。请单击[是]重新启动计算机，或单击[否]在以后重新启动"：**点"否"**（不必立即重启）。

文档落款：技术支持 18515555522。

## macOS 安装（macos 苹果/ 目录）

- 驱动包：`ffmacprnstd2608bm120iml.dmg`（富士胶片 macOS 打印驱动）。
- 视频教程：同目录 `安装方法.mp4`。
- 流程：双击挂载 dmg → 运行其中的安装器 → 系统设置 → 打印机与扫描仪 → 添加打印机 → IP 标签页，地址填楼层 IP，协议选 LPD 或 IPP → 选择对应 C5570 驱动 → 添加。
- 也可用命令行（装好驱动后）：
  `lpadmin -p <打印机名> -E -v lpd://192.168.16.79/ -P <驱动ppd路径>`

## 故障排查

- **安装时报错"已有同名打印机"**：先删除旧打印机（`uninstall` 或系统设置手动删），再安装。文档特别提示原"投资办公室打印机"需删除。
- **TCP 9100 连不通**：确认电脑与打印机在同一网段/有线网；楼层 IP 网段不同（二层研发是 192.168.26.x，其余是 192.168.16.x），检查本机 IP（`ipconfig`）。打印机可能关机或 IP 被改动——用 `status` 探测，IP 改动时需到设备面板确认新 IP 并更新 setup.ini/映射表。
- **装完打印机但脱机**：SNMP Enabled=0 时状态可能显示异常，可忽略或直接试打测试页；确认端口 IP 正确（Get-PrinterPort）。
- **驱动文件校验**：各包 FileInfo 段记录了 DEVMODE 等文件大小，可用于判断包是否完整。
- **卸载残留**：`Remove-Printer` 后再用 `Get-PrinterPort | Where Name -like '*192.168*'` 找到 `IP_<IP>` 形式的端口并 `Remove-PrinterPort`。
