---
name: mumu-manager
description: MuMu模拟器12命令行工具 MuMuManager.exe 开发者使用说明。用于通过命令行控制MuMu模拟器：查询信息、创建/删除/克隆模拟器、启动/关闭模拟器、安装/卸载应用、ADB命令、配置修改、窗口管理等。当用户提到 MuMuManager、MuMu模拟器命令行、模拟器控制、批量操作模拟器时使用。
---

# MuMuManager 命令行开发者指南

MuMuManager.exe 是 MuMu模拟器12 的命令行控制工具，位于模拟器安装目录下：
`X:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe`

要求模拟器版本 >= V4.0.0.3179。

## 通用参数

所有命令均支持 `-v, --vmindex` 参数指定模拟器索引：
- 单个：`-v 0`
- 多个：`-v 0,2,4`
- 全部：`-v all`

---

## 一、获取模拟器信息 (info)

```bash
MuMuManager.exe info -v 0          # 单个
MuMuManager.exe info -v 0,2,4      # 多个
MuMuManager.exe info -v all        # 全部
```

返回 JSON 字段说明：

| 字段 | 说明 | 备注 |
|------|------|------|
| `adb_host_ip` | ADB 域名 | 启动后才有 |
| `adb_port` | ADB 端口 | 启动后才有 |
| `index` | 模拟器索引 | |
| `name` | 模拟器名称 | |
| `pid` | 外壳进程 PID | 启动后才有 |
| `headless_pid` | 虚拟机进程 PID | 启动后才有 |
| `is_process_started` | 进程是否启动 | |
| `is_android_started` | 安卓是否启动成功 | |
| `player_state` | 启动阶段状态 | 启动后才有 |
| `main_wnd` | 主窗口句柄 | 启动后才有 |
| `render_wnd` | 渲染窗口句柄 | 启动后才有 |
| `vt_enabled` | VT 虚拟化 | 启动后才有 |
| `hyperv_enabled` | HyperV 状态 | |
| `disk_size_bytes` | 磁盘占用(字节) | |
| `created_timestamp` | 创建时间戳 | |

---

## 二、模拟器生命周期管理

### 创建 (create)

```bash
MuMuManager.exe create                    # 自动分配索引
MuMuManager.exe create -n 10             # 批量创建10个
MuMuManager.exe create -v 10             # 指定索引
MuMuManager.exe create -v 3 -n 10        # 从索引3起创建10个(3-12)
MuMuManager.exe create -v 3,20 -n 10     # 分别从3和20起各创建10个
```

### 复制 (clone)

```bash
MuMuManager.exe clone -v 2               # 复制索引2
MuMuManager.exe clone -v 2,4,6           # 复制多个
MuMuManager.exe clone -v all             # 复制全部
MuMuManager.exe clone -v 2 -n 10         # 复制10次
```

### 删除 (delete)

```bash
MuMuManager.exe delete -v 2
MuMuManager.exe delete -v 2,4,6
MuMuManager.exe delete -v all
```

### 重命名 (rename)

```bash
MuMuManager.exe rename -v 2 -n 测试
MuMuManager.exe rename -v all -n 测试
```

### 导入 (import)

```bash
MuMuManager.exe import -p C:\test.mumudata
MuMuManager.exe import -p C:\test.mumudata -n 10                          # 导入10次
MuMuManager.exe import -p C:\a.mumudata -p D:\b.mumudata -n 10           # 多文件各导入10次
```

### 备份/导出 (export)

```bash
MuMuManager.exe export -v 2 -d C:\backup -n test                         # 非压缩
MuMuManager.exe export -v all -d C:\backup -n test --zip                  # 压缩格式
```

---

## 三、控制模拟器 (control)

### 启动/关闭/重启

```bash
MuMuManager.exe control -v 2 launch                                       # 启动
MuMuManager.exe control -v 2 launch -pkg com.example.app                  # 启动并自动打开应用
MuMuManager.exe control -v 2 shutdown                                      # 关闭
MuMuManager.exe control -v 2 restart                                       # 重启
```

### 窗口控制

```bash
MuMuManager.exe control -v 2 show_window                                  # 显示窗口
MuMuManager.exe control -v 2 hide_window                                  # 隐藏窗口
MuMuManager.exe control -v 2 layout_window -px 100 -py 100               # 移动位置
MuMuManager.exe control -v 2 layout_window -sw 1600 -sh 900              # 修改大小
MuMuManager.exe control -v 2 layout_window -px 100 -py 100 -sw 1600 -sh 900  # 同时修改
```

### 应用管理 (app)

```bash
# 安装（支持 apk/xapk/apks）
MuMuManager.exe control -v 2 app install -apk C:\test.apk

# 卸载
MuMuManager.exe control -v 2 app uninstall -pkg com.example.app

# 启动应用
MuMuManager.exe control -v 2 app launch -pkg com.example.app

# 关闭应用
MuMuManager.exe control -v 2 app close -pkg com.example.app

# 查询应用状态（返回 running/stopped/not_installed）
MuMuManager.exe control -v 2 app info -pkg com.example.app

# 查询已安装应用列表和当前激活应用
MuMuManager.exe control -v 2 app info -i
```

### 工具栏功能 (tool)

```bash
MuMuManager.exe control -v 2 tool func -n rotate          # 屏幕旋转
MuMuManager.exe control -v 2 tool func -n go_home         # 主页
MuMuManager.exe control -v 2 tool func -n go_back         # 返回
MuMuManager.exe control -v 2 tool func -n top_most        # 窗口置顶
MuMuManager.exe control -v 2 tool func -n fullscreen      # 全屏
MuMuManager.exe control -v 2 tool func -n shake           # 摇一摇
MuMuManager.exe control -v 2 tool func -n screenshot      # 截屏
MuMuManager.exe control -v 2 tool func -n volume_up       # 音量+
MuMuManager.exe control -v 2 tool func -n volume_down     # 音量-
MuMuManager.exe control -v 2 tool func -n volume_mute     # 静音切换
```

### 其他工具

```bash
# CPU 限制（1-100%）
MuMuManager.exe control -v 2 tool downcpu -c 50

# 虚拟定位（经度-180~180，纬度-90~90）
MuMuManager.exe control -v 2 tool location -lon 114.1 -lat -23

# 重力感应（角度）
MuMuManager.exe control -v 2 tool gyro -gx 40 -gy 20 -gz 30
```

### 桌面快捷方式 (shortcut)

```bash
# 创建
MuMuManager.exe control -v 2 shortcut create -n test -i C:\test.ico -pkg com.example.app

# 删除
MuMuManager.exe control -v 2 shortcut delete
```

---

## 四、配置模拟器 (setting)

```bash
# 读取配置
MuMuManager.exe setting -v 2 -a                                    # 所有配置
MuMuManager.exe setting -v 2 -aw                                   # 所有可写配置
MuMuManager.exe setting -v 2 -k window_size_fixed                  # 单个配置
MuMuManager.exe setting -v 2 -k key1 -k key2                       # 多个配置
MuMuManager.exe setting -v 2 -k window_size_fixed -i               # 配置属性信息

# 修改配置
MuMuManager.exe setting -v 2 -k window_size_fixed -val true
MuMuManager.exe setting -v 2 -k key1 -val val1 -k key2 -val val2   # 修改多个
MuMuManager.exe setting -v 2 -p C:\config.json                     # JSON文件批量修改

# 全局默认配置（不带 -v，影响新建模拟器）
MuMuManager.exe setting -a                                          # 读取默认
MuMuManager.exe setting -k window_size_fixed -val true              # 修改默认
```

常用可写配置项详见 [settings-reference.md](settings-reference.md)。

---

## 五、ADB 便捷命令 (adb)

```bash
MuMuManager.exe adb -v 2 -c connect                   # 连接
MuMuManager.exe adb -v 2 -c disconnect                # 断开
MuMuManager.exe adb -v 2 -c input_text 哈哈            # 文本输入
MuMuManager.exe adb -v 2 -c go_back                   # 返回键
MuMuManager.exe adb -v 2 -c go_home                   # 主页键
MuMuManager.exe adb -v 2 -c go_task                   # 任务键
MuMuManager.exe adb -v 2 -c volume_up                 # 音量+
MuMuManager.exe adb -v 2 -c volume_down               # 音量-
MuMuManager.exe adb -v 2 -c volume_mute               # 静音
MuMuManager.exe adb -v 2 -c getprop ro.opengles.version       # 获取属性
MuMuManager.exe adb -v 2 -c setprop ro.opengles.version xxx   # 修改属性

# 其他 shell 命令
MuMuManager.exe adb -v 2 -c "shell pm list package | grep onmyoji"
```

---

## 六、机型属性 (simulation)

```bash
MuMuManager.exe simulation -v 2 -sk mac_address -sv "08:fb:5f:84:40:00"
```

可修改属性：`imei`, `imsi`, `android_id`, `model`, `brand`, `solution`, `phone_number`, `mac_address`

注意：安卓12 不允许应用获取 IMEI/IMSI/手机号码/MAC。

---

## 七、其他命令

```bash
MuMuManager.exe sort                          # 排列所有模拟器窗口
MuMuManager.exe driver install -n lwf         # 安装网络桥接驱动（需管理员权限）
MuMuManager.exe driver uninstall -n lwf       # 卸载网络桥接驱动
```

---

## 八、旧版兼容命令（可能废弃，谨慎使用）

```bash
# ADB
MuMuManager.exe adb -v [序号]                          # 查询 ADB 端口
MuMuManager.exe adb -v [序号] connect                  # 连接 ADB
MuMuManager.exe adb -v [序号] shell                    # 进入 ADB shell

# 控制
MuMuManager.exe api -v [序号] launch_player             # 启动
MuMuManager.exe api -v [序号] shutdown_player            # 关闭

# 应用
MuMuManager.exe api -v [序号] install_apk [path]        # 安装
MuMuManager.exe api -v [序号] uninstall_app [package]    # 卸载
MuMuManager.exe api -v [序号] launch_app [package]       # 启动应用
MuMuManager.exe api -v [序号] close_app [package]        # 关闭应用
MuMuManager.exe api -v [序号] app_state [package]        # 应用状态

# 显示
MuMuManager.exe api -v [序号] show_player_window         # 显示窗口
MuMuManager.exe api -v [序号] hide_player_window         # 隐藏窗口
MuMuManager.exe api set_window_pos [序号] [x,y,w,h]     # 窗口位置和大小

# 状态
MuMuManager.exe api -v [序号] vt_enabled                 # VT 状态
MuMuManager.exe api -v [序号] hyperv_enabled             # HyperV 状态
MuMuManager.exe api -v [序号] player_state               # 模拟器状态
MuMuManager.exe api get_player_list                      # 模拟器列表

# 配置（旧语法）
MuMuManager.exe setting -v [序号] get_key [配置]
MuMuManager.exe setting -v [序号] set_key [配置] [值]
MuMuManager.exe setting -v [序号] get_keys [配置1],[配置2]
MuMuManager.exe setting -v [序号] set_keys [配置1]=[值1],[配置2]=[值2]
```
