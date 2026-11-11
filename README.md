# saidc-printer — 公司楼层打印机驱动一键安装

公司各楼层富士胶片（FUJIFILM/Fuji Xerox）ApeosPort C5570 网络打印机驱动包与 WorkBuddy Skill 一键安装工具。

## 楼层映射

| 楼层 | 打印机名 | IP | 驱动包 |
|---|---|---|---|
| 一层 | FF K505p for ApeosPort C5570-1层打印机 | 192.168.16.79 | 一层5570打印安装包16.79.zip |
| 二层生态 | FF K505p for ApeosPort C5570-2层生态打印机 | 192.168.16.103 | 二层生态5570打印安装包16.103.zip |
| 二层研发（2南） | FF K505p for ApeosPort C5570-2南 | 192.168.26.188 | 二层研发打印驱动26.188.rar |
| 四层 | FF K505p for ApeosPort C5570-4 | 192.168.16.16 | 四层打印驱动16.16.rar |
| 五层 | FF K505p for ApeosPort C5570-5 | 192.168.16.31 | 五层打印驱动16.31.rar |

驱动均为 `FF K505p for ApeosPort C5570 PCL 6`，端口 RAW 9100。文件名末尾数字即 IP 末段。

## 目录结构

```
saidc-printer/            # WorkBuddy Skill（SKILL.md + 安装脚本 + 参考资料）
一层5570打印安装包16.79.zip
二层生态5570打印安装包16.103.zip
二层研发打印驱动26.188.rar
四层打印驱动16.16.rar
五层打印驱动16.31.rar
新打印机一键安装方法.doc   # 图文安装说明（Win10）
macos 苹果/                # macOS 驱动 dmg + 视频教程
```

## Windows 一键安装（手动方式）

1. **先删除已有 C5570 打印机**（设置 → 蓝牙和其他设备 → 打印机和扫描仪），否则安装报错。
2. 解压对应楼层驱动包，右键以管理员身份运行根目录 `setup.exe`。
3. 弹窗确认安装；完成后询问是否重启时点"否"。

## WorkBuddy Skill 方式

将 `saidc-printer/` 目录放入 `~/.workbuddy/skills/`，然后：

```bash
python saidc-printer/scripts/install_printer.py list        # 列出映射与状态
python saidc-printer/scripts/install_printer.py status 1    # 连通性检查
python saidc-printer/scripts/install_printer.py install 1 --force   # 一键安装
python saidc-printer/scripts/install_printer.py uninstall 1 --yes   # 卸载
```

楼层标识：`1` / `2eco` / `2rd` / `4` / `5`，也可直接用 IP。rar 解压需要本机安装 WinRAR。

**自动下载驱动**：同事电脑上无需手动拷贝驱动包 —— skill 会自动从本仓库下载（`raw.githubusercontent.com`）。前提：
1. 同事被加为仓库协作者（Settings → Collaborators）
2. 同事本机有 GitHub 凭据：`gh auth login`，或装 Git 并登录过 github.com，或设置环境变量 `GITHUB_TOKEN`

## macOS 安装

挂载 `macos 苹果/ffmacprnstd2608bm120iml.dmg` 安装驱动，然后在系统设置 → 打印机与扫描仪中通过 IP（LPD/IPP，端口 9100）添加对应楼层打印机，详见同目录视频教程。

## 注意

- 本仓库为私有仓库，包含公司内网信息，请勿公开。
- 技术支持：18515555522
