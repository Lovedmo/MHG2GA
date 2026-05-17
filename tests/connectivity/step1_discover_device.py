"""
Step 1: 设备发现
扫描 MuMu 12 常见 ADB 端口，发现正在运行的模拟器实例。
无需任何第三方依赖。
"""

import os
import shutil
import subprocess
import sys
import socket
from pathlib import Path


MUMU12_BASE_PORT = 16384
MUMU12_PORT_STEP = 32
MUMU12_MAX_INSTANCES = 8

MUMU12_ADB_CANDIDATES = [
    Path("D:\\MuMu Player 12") / "shell" / "adb.exe",
    Path("C:\\MuMu Player 12") / "shell" / "adb.exe",
    Path("E:\\MuMu Player 12") / "shell" / "adb.exe",
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Netease" / "MuMu Player 12" / "shell" / "adb.exe",
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Netease" / "MuMuPlayerGlobal-12.0" / "shell" / "adb.exe",
    Path("D:\\Program Files") / "Netease" / "MuMu Player 12" / "shell" / "adb.exe",
    Path("D:\\Program Files") / "Netease" / "MuMuPlayerGlobal-12.0" / "shell" / "adb.exe",
    Path("C:\\Program Files") / "Netease" / "MuMu Player 12" / "shell" / "adb.exe",
    Path("D:\\Netease") / "MuMu Player 12" / "shell" / "adb.exe",
    Path("E:\\Netease") / "MuMu Player 12" / "shell" / "adb.exe",
]


def find_adb() -> str:
    """查找可用的 adb 可执行文件路径。"""
    system_adb = shutil.which("adb")
    if system_adb:
        return system_adb

    for path in MUMU12_ADB_CANDIDATES:
        if path.exists():
            return str(path)

    print("[FAIL] 未找到 adb 工具，请先运行 step0_check_env.py 检查环境")
    sys.exit(1)


def run_adb(adb_path: str, args: list[str], timeout: int = 10) -> tuple[bool, str]:
    """执行 adb 命令并返回 (成功?, 输出内容)。"""
    try:
        result = subprocess.run(
            [adb_path] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "命令超时"
    except Exception as e:
        return False, str(e)


def check_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """快速检测端口是否开放。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def list_existing_devices(adb_path: str) -> list[str]:
    """获取当前已连接的设备列表。"""
    ok, output = run_adb(adb_path, ["devices"])
    if not ok:
        return []

    devices = []
    for line in output.split("\n")[1:]:
        line = line.strip()
        if line and "\t" in line:
            device_id, status = line.split("\t", 1)
            if status == "device":
                devices.append(device_id)
    return devices


def scan_mumu12_ports(adb_path: str) -> list[dict]:
    """扫描 MuMu 12 的 ADB 端口，尝试连接。"""
    found = []
    print("  扫描 MuMu 12 端口...")

    for i in range(MUMU12_MAX_INSTANCES):
        port = MUMU12_BASE_PORT + i * MUMU12_PORT_STEP
        address = f"127.0.0.1:{port}"
        instance_label = f"实例 {i} (端口 {port})"

        if not check_port_open("127.0.0.1", port):
            print(f"    端口 {port}: 未开放（跳过）")
            continue

        print(f"    端口 {port}: 已开放，尝试 ADB 连接...", end=" ")
        ok, output = run_adb(adb_path, ["connect", address], timeout=5)

        if ok and ("connected" in output.lower() or "already" in output.lower()):
            print(f"成功! ({output})")
            found.append({
                "instance": i,
                "port": port,
                "address": address,
                "status": "connected",
            })
        else:
            print(f"失败 ({output})")

    return found


def main() -> None:
    print("=" * 60)
    print("  MHG2GA Step 1: 设备发现")
    print("=" * 60)
    print()

    adb_path = find_adb()
    print(f"  [INFO] 使用 ADB: {adb_path}")

    ok, output = run_adb(adb_path, ["start-server"])
    if ok:
        print("  [INFO] ADB Server 已启动")
    else:
        print(f"  [WARN] ADB Server 启动可能失败: {output}")
    print()

    print("--- 已连接设备 ---")
    existing = list_existing_devices(adb_path)
    if existing:
        for dev in existing:
            print(f"  [FOUND] {dev}")
    else:
        print("  （无已连接设备）")
    print()

    print("--- MuMu 12 端口扫描 ---")
    found = scan_mumu12_ports(adb_path)
    print()

    print("--- 最终设备列表 ---")
    final_devices = list_existing_devices(adb_path)
    if final_devices:
        for dev in final_devices:
            print(f"  [DEVICE] {dev}")
    else:
        print("  （无可用设备）")
    print()

    print("=" * 60)
    print("  发现结果总结")
    print("=" * 60)
    if found:
        print(f"  [PASS] 发现 {len(found)} 个 MuMu 12 模拟器实例：")
        for item in found:
            print(f"         - 实例 {item['instance']}: {item['address']}")
        print()
        print(f"  >>> 可以继续运行 Step 2，使用地址: {found[0]['address']} <<<")
    elif final_devices:
        print(f"  [PASS] 发现 {len(final_devices)} 个已连接设备（非 MuMu 12 端口扫描）：")
        for dev in final_devices:
            print(f"         - {dev}")
        print()
        print(f"  >>> 可以继续运行 Step 2，使用地址: {final_devices[0]} <<<")
    else:
        print("  [FAIL] 未发现任何模拟器实例")
        print("         请确认：")
        print("         1. MuMu 12 模拟器正在运行")
        print("         2. 模拟器设置中已开启 ADB 调试")
        print("         3. 防火墙未阻止本地连接")

    print()


if __name__ == "__main__":
    main()
