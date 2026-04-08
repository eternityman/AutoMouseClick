# AutoMouseClick

鼠标自动点击器 — 一个可视化桌面应用，支持自定义点击频率、后台模式与全局快捷键。

## 功能特性

- **点击频率设置**：支持内置频率（5次/秒、10次/秒、20次/秒）及自定义频率（1~1000 次/秒）
- **后台模式**：开启后在固定位置点击，不影响用户鼠标操作；可实时切换
- **自动点击开关**：通过按钮或全局快捷键启动/停止自动点击
- **快捷键设置**：默认 `Ctrl+Alt+S`，支持自定义录制新快捷键
- **帮助按钮**：内置使用说明

## 环境要求

- Python 3.8+
- Windows（.exe 打包需要在 Windows 上执行）

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python auto_mouse_click.py
```

## 打包为 .exe

在 **Windows** 系统上执行以下步骤，生成可直接运行的 `.exe` 文件：

### 方式一：使用一键打包脚本

双击运行 `build_exe.bat`，或在命令行中执行：

```cmd
build_exe.bat
```

### 方式二：手动打包

```bash
pip install pyinstaller
pyinstaller AutoMouseClick.spec --noconfirm
```

打包完成后，可执行文件位于 `dist/AutoMouseClick.exe`。

## 使用说明

1. **选择点击频率**：选择内置频率或切换到自定义频率并输入值后点击「应用」
2. **后台模式**：勾选后台模式，点击「设置后台点击位置」，3 秒后记录鼠标位置作为点击目标
3. **启动点击**：点击「开启自动点击」按钮，或按快捷键（默认 Ctrl+Alt+S）
4. **停止点击**：再次按快捷键（默认 Ctrl+Alt+S）即可停止
5. **更改快捷键**：点击「录制快捷键」后按下新组合键

> **提示**：非后台模式下，开始点击时窗口会自动最小化以避免自点击，使用快捷键停止后窗口将自动恢复。

## 项目结构

```
AutoMouseClick/
├── auto_mouse_click.py   # 主应用程序
├── AutoMouseClick.spec   # PyInstaller 打包配置
├── build_exe.bat         # Windows 一键打包脚本
├── requirements.txt      # Python 依赖
└── README.md             # 项目说明
```
