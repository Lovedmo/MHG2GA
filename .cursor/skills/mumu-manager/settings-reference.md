# MuMu模拟器可写配置项参考

通过 `MuMuManager.exe setting` 命令可读取/修改以下配置。

## 显示设置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `resolution_mode` | `tablet.1` | 分辨率模式 |
| `resolution_width.custom` | `1600.000000` | 自定义宽度 |
| `resolution_height.custom` | `900.000000` | 自定义高度 |
| `resolution_dpi.custom` | `240.000000` | 自定义 DPI |
| `max_frame_rate` | `60` | 最高帧率限制 |
| `show_frame_rate` | `false` | 是否显示帧率 |
| `dynamic_adjust_frame_rate` | `false` | 动态调整帧率 |
| `dynamic_low_frame_rate_limit` | `15` | 动态降低帧率值 |
| `vertical_sync` | `false` | 垂直同步 |
| `screen_brightness` | `50` | 画面亮度 |
| `window_auto_rotate` | `true` | 自动旋转 |
| `window_save_rect` | `false` | 记住窗口位置和大小 |
| `window_size_fixed` | `false` | 固定窗口大小禁止拉伸 |

## 性能设置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `performance_mode` | `middle` | 性能配置策略 |
| `performance_cpu.custom` | `4` | 自定义 CPU 核数 |
| `performance_mem.custom` | `6.000000` | 自定义内存(GB) |
| `renderer_mode` | `vk` | 显卡渲染模式(vk/dx) |
| `renderer_strategy` | `auto` | 显存使用策略 |
| `force_discrete_graphics` | `true` | 强制使用独立显卡 |

## 机型设置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `phone_brand` | `HUAWEI` | 手机品牌 |
| `phone_model` | `畅享 50 Pro` | 手机型号 |
| `phone_miit` | `NCO-AL00` | 入网型号 |
| `phone_imei` | `352070100579777` | IMEI 编码 |
| `phone_number` | `""` | 手机号码 |
| `gpu_mode` | `middle` | GPU 型号类型 |
| `gpu_model.custom` | `Adreno (TM) 640` | 自定义 GPU 型号 |

## 网络设置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `net_bridge_open` | `false` | 开启桥接模式 |
| `net_bridge_card` | `""` | 桥接网卡名称 |
| `net_bridge_ip_mode` | `dhcp` | 桥接网络模式(dhcp/static) |
| `net_bridge_ip_addr` | `""` | 桥接 IP 地址 |
| `net_bridge_subnet_mask` | `""` | 桥接子网掩码 |
| `net_bridge_gateway` | `""` | 桥接网关 |
| `net_bridge_dns1` | `""` | 桥接 DNS1 |
| `net_bridge_dns2` | `""` | 桥接 DNS2 |

## 其他设置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `player_name` | `MuMu模拟器12` | 模拟器名称 |
| `root_permission` | `false` | ROOT 权限 |
| `app_keptlive` | `false` | 后台挂机保活 |
| `apk_asscciation` | `true` | APK 文件关联 |
| `mouse_style` | `true` | 模拟器定制鼠标 |
| `prevent_sleep` | `true` | 阻止电脑休眠 |
| `quit_confirm` | `true` | 退出弹窗确认 |
| `joystick_auto_connect` | `true` | 手柄自动连接 |
| `system_disk_readonly` | `true` | 只读系统盘 |
| `system_volume_close` | `false` | 关闭系统声音 |

## JSON 批量配置示例

创建 UTF-8 格式的 JSON 文件，通过 `-p` 参数批量修改：

```json
{
    "performance_mode": "high",
    "performance_cpu.custom": "8",
    "performance_mem.custom": "8.000000",
    "max_frame_rate": "120",
    "resolution_mode": "custom",
    "resolution_width.custom": "1920.000000",
    "resolution_height.custom": "1080.000000",
    "root_permission": "true",
    "app_keptlive": "true"
}
```

使用方式：
```bash
MuMuManager.exe setting -v 0 -p C:\config.json
```
