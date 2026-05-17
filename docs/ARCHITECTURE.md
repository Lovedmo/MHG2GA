# MHG2GA 技术架构文档

> **Make Houkai Gakuen 2 Great Again**
> 崩坏学园2 Android 模拟器全自动流程辅助工具。

**最后更新**: 2026-05-17 — 任务执行引擎完成，全功能可用

---

## 1. 项目概述

MHG2GA 通过 ADB 协议连接 Android 模拟器（主要针对 MuMu 12），利用 Airtest 框架进行截图与触控操作，通过 OpenCV 模板匹配识别游戏界面，自动执行崩坏学园2中的日常重复任务。提供 PyQt6 GUI 供用户管理多设备、配置参数、编辑工作流、监控运行。

### 1.1 当前进度

| 模块 | 状态 | 说明 |
|------|------|------|
| 设备连接层 | ✅ 完成 | ADB 连接、设备扫描、多设备管理、模拟器自动启停 |
| GUI 框架 | ✅ 完成 | 主窗口、设备列表、配置面板、日志控制台 |
| 截图与触控 | ✅ 完成 | ADBCAP/JAVACAP/MINICAP + ADBTOUCH/MAXTOUCH/MINITOUCH |
| 配置持久化 | ✅ 完成 | YAML 全局/设备独立配置 |
| 日志系统 | ✅ 完成 | 终端 + GUI + 文件三路输出 |
| 数据库 | ✅ 完成 | SQLite 任务历史和截图记录 |
| 模板管理 | ✅ 完成 | 模板截取、分类管理、蒙版编辑、ROI/阈值/偏移配置 |
| 任务配置 | ✅ 完成 | 可视化工作流编辑器，支持树形嵌套步骤 |
| 任务执行 | ✅ 完成 | TaskExecutor 引擎，多设备并行执行 |
| 应用管理 | ✅ 完成 | 包列表获取、应用锁定、自动启动、探活保活 |

---

## 2. 技术选型

| 模块 | 技术 | 实际版本 | 说明 |
|------|------|---------|------|
| 编程语言 | Python | 3.14 | 主开发语言 |
| 自动化框架 | Airtest | 1.4.3 | 封装 ADB 连接 + 截图 + 触控 |
| 图像处理 | OpenCV (cv2) | >= 4.5 | 截图旋转、模板匹配（多模式） |
| GUI 框架 | PyQt6 | >= 6.5 | 桌面 GUI |
| 配置管理 | PyYAML | >= 6.0 | 全局和设备配置持久化 |
| 数据库 | SQLite | 内置 | 任务历史、截图记录 |
| 日志 | logging (标准库) | — | 多 Handler 日志系统 |

### 2.1 已知 Airtest 1.4.3 兼容问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| MINICAP 在 MuMu x86_64 上失败 | Airtest 打包的 `minicap.so` 实际为 32 位 | 使用 JAVACAP 替代 |
| MINITOUCH 在 MuMu 上失败 | `mv` 命令在模拟器 `/data/local/tmp/` 报 `Invalid argument` | 使用 MAXTOUCH 替代 |
| `touch_method` setter 崩溃 | `screen_proxy.teardown()` 未实现 | 直接调用 `TouchProxy.auto_setup()` 绕过 |
| `cap_method` setter 崩溃 | 同上 | 直接调用 `ScreenProxy.auto_setup()` 绕过 |
| URI 参数被忽略 | Airtest >=1.1.2 自动选择方式，忽略 URI 中的指定 | 连接后通过内部 API 强制设置 |

---

## 3. 目录结构

```
MHG2GA/
├── docs/
│   └── ARCHITECTURE.md              # 本文档
├── data/                            # 运行时数据（.gitignore 排除大部分）
│   ├── config.yaml                  # 用户配置（全局 + 设备列表）
│   ├── tasks.yaml                   # 任务索引（名称、描述、启用状态）
│   ├── tasks/                       # 各任务的步骤详情
│   │   └── <task_name>.yaml         # 单个任务的步骤定义
│   ├── mhg2ga.db                    # SQLite 数据库
│   ├── logs/                        # 日志文件（每次启动新建）
│   └── temp/                        # 临时截图文件
├── assets/
│   └── templates/                   # 模板图片库
│       ├── templates.json           # 模板元数据索引
│       ├── mainwindow/              # 分类文件夹
│       │   ├── shouye_on.png        # 模板图片
│       │   └── shouye_mask.png      # 蒙版文件
│       └── ...
├── src/
│   ├── main.py                      # 程序入口
│   ├── config/
│   │   ├── default.yaml             # 内置默认配置
│   │   └── settings.py              # AppConfig — 配置管理器
│   ├── core/
│   │   ├── device_manager.py        # DeviceManager — 设备连接与操控
│   │   ├── template_manager.py      # TemplateManager — 模板元数据管理
│   │   ├── task_model.py            # TaskManager — 任务数据模型与持久化
│   │   ├── task_executor.py         # TaskExecutor — 工作流执行引擎
│   │   ├── workers.py               # QThread 工作线程集合
│   │   ├── logger.py                # 统一日志系统
│   │   └── database.py              # SQLite 数据库管理
│   ├── gui/
│   │   ├── main_window.py           # MainWindow — 主窗口（核心调度中心）
│   │   ├── device_list_panel.py     # DeviceListPanel — 左侧设备列表
│   │   ├── device_overview_tab.py   # DeviceOverviewTab — 设备概览+应用管理
│   │   ├── screenshot_config_tab.py # ScreenshotConfigTab — 截图与识别配置
│   │   ├── touch_config_tab.py      # TouchConfigTab — 触控配置与测试
│   │   ├── task_config_tab.py       # TaskConfigTab — 任务配置与执行
│   │   ├── template_workspace.py    # TemplateWorkspace — 模板工作台
│   │   ├── log_console.py           # LogConsole — 独立日志窗口
│   │   ├── settings_dialog.py       # SettingsDialog — 全局设置对话框
│   │   ├── system_tray.py           # SystemTray — 系统托盘
│   │   └── widgets/
│   │       ├── image_preview.py     # ImagePreview — 截图预览+坐标拾取
│   │       ├── mask_editor.py       # MaskEditor — 蒙版绘制编辑器
│   │       ├── selectable_image_view.py # SelectableImageView — 区域选择
│   │       ├── template_tree.py     # TemplateTreeWidget — 模板树形控件
│   │       └── status_indicator.py  # StatusIndicator — 状态指示灯
│   └── utils/
├── tests/
│   └── connectivity/                # ADB 连接测试脚本集
├── requirements.txt
└── README.md
```

---

## 4. 核心模块详解

### 4.1 DeviceManager (`src/core/device_manager.py`)

设备连接管理器，封装所有 Airtest/ADB 操作。

```python
class DeviceManager:
    # 连接管理
    connect(address, cap_method, touch_method) -> DeviceInfo
    disconnect(address) -> None
    disconnect_all() -> None
    is_connected(address) -> bool
    scan_devices() -> list[DeviceInfo]

    # 截图
    take_screenshot(address, save_path=None, silent=False) -> (ndarray, elapsed_ms)
    screenshot_benchmark(address, rounds=5) -> list[float]
    get_orientation(address) -> int

    # 触控
    tap(address, x, y) -> None
    swipe(address, x1, y1, x2, y2, duration=300) -> None
    key_event(address, key) -> None

    # 模板匹配
    @staticmethod
    match_template(screenshot, template, threshold=0.80, rgb=True,
                   roi=None, click_offset=None, mask=None, match_mode="normal") -> dict | None
    @staticmethod
    match_template_all(...) -> list[dict]

    # 模拟器管理 (MuMuManager)
    get_emulator_state(address) -> str  # "running" / "stopped" / "unknown"
    start_emulator(address) -> bool
    get_emulator_info(address) -> dict
```

**模板匹配模式**:
- `normal` — 标准 TM_CCOEFF_NORMED + HSV 颜色校验
- `mask` — 带蒙版匹配（白色区域参与，黑色忽略）
- `edge` — Canny 边缘检测后匹配

**匹配返回值**:
```python
{"center": (x, y), "click_point": (x, y), "rect": (x, y, w, h), "confidence": float}
```

### 4.2 TemplateManager (`src/core/template_manager.py`)

模板图片元数据管理器。

```python
class TemplateManager:
    templates -> list[dict]                    # 所有模板列表
    get_template(name) -> dict | None
    get_template_path(name) -> Path | None     # 模板图片绝对路径
    add_template(name, category, image, ...) -> dict
    update_template(name, **fields) -> bool
    remove_template(name) -> bool
    save_mask(name, mask_array) -> str         # 保存蒙版
    load_mask(name) -> ndarray | None          # 加载蒙版
    get_categories() -> list[str]
    rename_category(old, new) -> None
```

**模板元数据结构**:
```python
{
    "name": "shouye_on",
    "file": "mainwindow/shouye_on.png",
    "category": "mainwindow",
    "threshold": 0.80,
    "rgb": True,
    "roi": None,              # [x, y, w, h] 或 None
    "click_offset": None,     # [ox, oy] 或 None
    "mask_file": "mainwindow/shouye_on_mask.png",  # 蒙版路径
    "match_mode": "mask",     # normal / mask / edge
    "description": "首页已选中",
    "width": 120, "height": 80,
}
```

### 4.3 TaskManager (`src/core/task_model.py`)

任务数据模型与 YAML 持久化，双文件存储结构。

**存储结构**:
- `data/tasks.yaml` — 任务索引（轻量，仅含 name/description/enabled）
- `data/tasks/<name>.yaml` — 各任务的步骤详情

```python
class TaskManager:
    tasks -> list[dict]                # 完整任务列表（含 steps）
    get_task(name) -> dict | None
    add_task(task) -> None             # 添加/更新任务
    remove_task(name) -> bool
    rename_task(old_name, new_name) -> bool

    @staticmethod
    create_step(step_type) -> dict     # 创建步骤模板
    @staticmethod
    new_task(name, description="") -> dict
```

**步骤类型**:

| 类型 | 标签 | 含义 | 有子步骤 |
|------|------|------|----------|
| `check` | 条件 (if) | 模板存在则执行子步骤，否则跳过/停止 | ✅ |
| `whileif` | 循环 (while) | 模板存在时循环执行子步骤 | ✅ |
| `click` | 点击 | 检测模板并点击匹配位置 | ❌ |
| `delay` | 延时 | 等待指定时长 | ❌ |

**步骤数据结构** (所有时间单位为 ms):

```yaml
# check 步骤
- type: check
  template: "shouye_on"
  description: "检查首页"
  retry_enabled: false        # 是否轮询
  retry_interval_ms: 1000     # 轮询间隔
  timeout_mode: "time"        # time / count
  max_timeout_ms: 30000       # 最大超时
  max_retries: 10             # 最大次数
  on_fail: "stop"             # stop / skip
  children: [...]             # 子步骤列表

# whileif 步骤
- type: whileif
  template: "battle_icon"
  description: "循环战斗"
  check_interval_ms: 1000     # 每轮间隔
  timeout_mode: "time"        # time / count
  max_timeout_ms: 1000        # 最大执行时间
  max_loops: 2                # 最大循环次数
  children: [...]

# click 步骤
- type: click
  template: "renwu"
  description: "点击任务按钮"
  touch_duration_ms: 50       # 触摸时长
  after_delay_ms: 200         # 触摸后等待
  on_fail: "stop"             # stop / skip

# delay 步骤
- type: delay
  duration_ms: 1000
  description: "等待加载"
```

### 4.4 TaskExecutor (`src/core/task_executor.py`)

工作流执行引擎，在 QThread 中运行，支持多设备并行。

```python
class TaskExecutor(QThread):
    # 信号
    step_started(str, tuple)     # (描述, path)
    step_finished(tuple, bool)   # (path, success)
    task_finished(str, bool)     # (task_name, success)
    log_message(str)             # 详细执行日志

    def __init__(self, task, device_addr, device_mgr, template_mgr): ...
    def stop(self): ...          # 安全停止
```

**执行逻辑**:
1. 递归遍历步骤树
2. `check`: 截图→模板匹配→成立执行子步骤，支持轮询重试
3. `whileif`: 循环检测→条件成立执行子步骤→等待间隔→再检测，超时/超轮数退出
4. `click`: 截图→模板匹配→计算点击坐标（含 click_offset）→执行 tap→后延时
5. `delay`: 可中断的等待

**任务生命周期**:
- 开启任务 → 创建 TaskExecutor 线程 → 开始执行
- 任务完成/停止 → 自动关闭卡片开关 → 保存 enabled=false
- 关闭应用 → stop_all_tasks() 停止所有执行器

### 4.5 Workers (`src/core/workers.py`)

QThread 工作线程集合。

| Worker | 信号 | 用途 |
|--------|------|------|
| `ScanWorker` | `finished(list)` | 扫描设备列表 |
| `ConnectWorker` | `finished(dict)`, `error(str, str)` | 连接设备（含模拟器自动启动） |
| `DisconnectWorker` | `finished(str)` | 断开连接 |
| `ScreenshotWorker` | `finished(object, float)`, `error(str)` | 截图操作 |
| `BenchmarkWorker` | `finished(list)`, `progress(int, float)` | 截图性能测试 |
| `TapWorker` | `finished()`, `error(str)` | 点击操作 |
| `SwipeWorker` | `finished()`, `error(str)` | 滑动操作 |
| `KeyEventWorker` | `finished()`, `error(str)` | 按键操作 |
| `DeviceInfoWorker` | `finished(dict)`, `error(str)` | 刷新设备信息 |

### 4.6 Logger (`src/core/logger.py`)

统一日志系统，三路输出：

| Handler | 目标 | 格式 |
|---------|------|------|
| `StreamHandler` | 终端 stdout | `[HH:MM:SS] [LEVEL] [device] message` |
| `FileHandler` | `data/logs/mhg2ga_*.log` | 同上 |
| `_GuiHandler` | GUI 日志控制台回调 | 仅 message 部分 |

### 4.7 AppConfig (`src/config/settings.py`)

YAML 配置管理，支持全局设置和每设备独立配置。

**配置结构**:
```yaml
global:
  adb_path: ""
  mumu_manager_path: "D:\\..."   # MuMuManager.exe 路径
  default_cap_method: "ADBCAP"
  default_touch_method: "ADBTOUCH"
  minimize_to_tray: true
  auto_connect: true

recognition:
  default_threshold: 0.80
  screenshot_interval: 0.5

devices:
  - address: "127.0.0.1:16384"
    alias: "MuMu-1"
    cap_method: "JAVACAP"
    touch_method: "MAXTOUCH"
    locked_app: "com.miHoYo.bh2"   # 锁定应用包名
    keepalive_enabled: true          # 应用探活
    keepalive_interval: 30           # 探活间隔(秒)
```

---

## 5. GUI 架构

### 5.1 窗口层级

```
MainWindow (QMainWindow)
├── QToolBar — 全部启动/停止、全局设置、日志控制台开关、关于
├── QStatusBar — 设备数、ADB 状态、版本号
├── QSplitter (水平)
│   ├── DeviceListPanel (左侧, 240-400px)
│   │   ├── 搜索框 + 刷新/添加按钮
│   │   ├── QListWidget (设备卡片列表)
│   │   └── 右键菜单: 连接/断开/移除
│   └── QStackedWidget (右侧内容区)
│       ├── 占位页 "请选择设备"
│       └── DeviceTabWidget (每设备一个)
│           ├── Tab 0: DeviceOverviewTab — 设备信息+预览+应用管理
│           ├── Tab 1: ScreenshotConfigTab — 截图方式/间隔/阈值+测试
│           ├── Tab 2: TouchConfigTab — 触控方式/延迟+点击/滑动/按键测试
│           └── Tab 3: TaskConfigTab — 任务配置与工作流执行
├── TemplateWorkspace (独立窗口) — 模板截取与参数编辑
├── LogConsole (独立窗口, 可置顶) — 日志查看
└── SystemTray (系统托盘)
```

### 5.2 TaskConfigTab — 任务配置

双层 UI 结构：

**Page 0 — 任务概览**:
- 网格卡片布局（一行三个）
- 每个卡片: 任务名 + 描述 + 步骤数 + 开关滑块 + 编辑按钮
- 新建任务按钮
- 开关控制任务启停（启动 TaskExecutor）

**Page 1 — 步骤编辑器**:
- 左右分栏（QSplitter）
- 左侧: 工作流步骤树（QTreeWidget，支持任意深度嵌套）
  - 工具栏: +条件 / +循环 / +点击 / +延时 / 上移 / 下移 / 缩进 / 移出 / if⇄while / 删除
  - 树节点显示: 类型(if/while/点击/延时) | 目标(模板描述) | 参数摘要
- 右侧: 步骤属性面板（QScrollArea）
  - 基本信息: 目标模板（可搜索下拉+图片预览）、步骤描述
  - 按类型切换不同参数页:
    - check: 轮询开关、失败处理、轮询参数（间隔/超时模式/上限）
    - whileif: 循环间隔、退出模式（时间/次数）、上限
    - click: 触摸时长、触摸后延时、失败处理
    - delay: 等待时长
  - 所有时间单位统一为 ms

### 5.3 TemplateWorkspace — 模板工作台

独立窗口，用于模板的截取、分类和参数编辑。

功能:
- 模板截取: 从设备截图中框选区域保存为模板
- 分类管理: 创建/重命名/删除分类文件夹
- 参数编辑: 阈值、ROI、click_offset、匹配模式
- 蒙版编辑: 画笔绘制蒙版区域
- 模板测试: 在当前截图上实时匹配验证

### 5.4 DeviceOverviewTab — 设备概览

- 设备信息展示: 地址、分辨率、型号、系统版本、方向
- 实时截图预览
- 应用管理:
  - 已安装包列表获取
  - 应用锁定（记忆目标应用）
  - 连接后自动启动锁定应用
  - 应用探活保活（定时检测+自动重启）
- 快捷操作: HOME/BACK 按键

---

## 6. 数据流

### 6.1 设备连接流程

```
用户点击"连接"
  → 检查模拟器状态（MuMuManager info）
  → 未运行? → 启动模拟器（MuMuManager control launch）→ 等待就绪
  → 创建 ConnectWorker → connect() → set_cap/touch_method()
  → 连接成功 → 更新 UI + 设置 TaskConfigTab 活动设备
  → 如有锁定应用 → 自动启动
```

### 6.2 任务执行流程

```
用户开启任务卡片开关
  → _on_toggle_task(name, True)
  → 检查活动设备 → 创建 TaskExecutor
  → TaskExecutor.run():
      → 遍历步骤树
      → check: screenshot → match_template → 成立? → execute_children
      → whileif: loop { screenshot → match → 成立? → execute_children → sleep }
      → click: screenshot → match → tap(click_point) → after_delay
      → delay: sleep(duration_ms)
  → task_finished 信号
  → 关闭卡片开关 + 保存 enabled=false
```

### 6.3 模板匹配流程 (TaskExecutor._find_template)

```
get_template_path(name) → 加载模板图片
take_screenshot(address, silent=True) → 当前截图
load_mask(name) → 蒙版（如有）
get_template(name) → 元数据(threshold, roi, click_offset, match_mode)
DeviceManager.match_template(...) → 匹配结果
```

---

## 7. 已知约束与注意事项

### 7.1 线程安全

- **禁止在 Worker/Executor 线程中操作 GUI 控件**，必须通过信号传递数据
- **numpy 数组不能跨线程传递**给 QPixmap，必须通过临时文件中转
- Worker 实例必须存储在 `self._workers` 列表中防止 GC 回收
- TaskExecutor 多实例可并行（不同设备），GIL 保护共享数据结构

### 7.2 MuMu 12 模拟器特性

- ADB 路径: `D:\MuMu Player 12\shell\adb.exe`（自动检测）
- 多开端口: `127.0.0.1:16384`, `127.0.0.1:16416`, `127.0.0.1:16448`...（间隔 32）
- `/data/local/tmp/` 目录 `mv` 操作受限
- CPU 架构: x86_64, Android API 32
- 推荐方式: **JAVACAP** (截图, ~30ms) + **MAXTOUCH** (触控)

### 7.3 MuMuManager 命令行工具

位于安装目录 `shell\MuMuManager.exe`，版本 >= V4.0.0.3179。
路径通过全局设置 `mumu_manager_path` 配置。

| 命令 | 功能 |
|------|------|
| `info -v <idx>` | 查询 ADB 端口、PID、运行状态 |
| `control -v <idx> launch` | 启动模拟器 |
| `control -v <idx> shutdown` | 关闭模拟器 |
| `control -v <idx> app launch -pkg <pkg>` | 启动应用 |
| `adb -v <idx> -c connect` | ADB 连接 |

### 7.4 Airtest 内部 API 使用

以下代码直接使用了 Airtest 内部 API，升级时需验证：

```python
# set_cap_method
from airtest.core.android.cap_methods.screen_proxy import ScreenProxy
dev._screen_proxy = ScreenProxy.auto_setup(...)

# set_touch_method
from airtest.core.android.touch_methods.touch_proxy import TouchProxy
dev._touch_proxy = TouchProxy.auto_setup(...)
```

---

## 8. 启动与运行

```bash
pip install -r requirements.txt
cd D:\AgentWorking\MHG2GA
python src/main.py
```

**MainWindow 初始化顺序**:
1. 创建 AppConfig / Database / DeviceManager / TaskManager / TemplateManager
2. 构建 UI
3. 创建 LogConsole / SystemTray / TemplateWorkspace
4. 加载样式表 + 注册日志回调
5. 从配置文件加载设备列表
6. 为每个设备 tab 注入 DeviceManager 和活动设备地址

---

## 9. 开发规范

### 9.1 代码风格

- PEP 8, 行宽 120 字符
- 所有公开函数使用类型注解
- 文件头部文档字符串说明模块用途
- 不添加无意义注释

### 9.2 日志规范

```python
from src.core.logger import get_logger
logger = get_logger("module_name")

logger.info("设备已连接", extra={"device": address})
logger.debug("内部细节")
```

任务执行时使用 `silent=True` 抑制高频截图日志。

### 9.3 时间单位规范

**所有时间值统一使用毫秒 (ms)**，包括:
- 步骤参数: `retry_interval_ms`, `max_timeout_ms`, `touch_duration_ms`, `after_delay_ms`, `duration_ms`, `check_interval_ms`
- UI 显示: QSpinBox 后缀 " ms"
- 参数列格式化: `1000ms` → `1s`, `60000ms` → `1min`

### 9.4 任务存储规范

- 索引文件与详情文件分离，避免大文件频繁读写
- 兼容旧格式：`_load_index` 自动检测并迁移内嵌 steps 到独立文件
- 文件名使用任务名（特殊字符替换为 `_`）
