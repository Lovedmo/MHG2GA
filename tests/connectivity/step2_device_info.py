"""
Step 2: 设备详细信息
连接到指定模拟器并获取分辨率、DPI、系统版本等详细信息。
无需任何第三方依赖。

用法:
    python step2_device_info.py                  # 使用默认地址 127.0.0.1:16384
    python step2_device_info.py 127.0.0.1:7555   # 指定地址
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_ADDRESS = "127.0.0.1:16384"

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
    system_adb = shutil.which("adb")
    if system_adb:
        return system_adb
    for path in MUMU12_ADB_CANDIDATES:
        if path.exists():
            return str(path)
    print("[FAIL] 未找到 adb 工具")
    sys.exit(1)


def run_adb(adb_path: str, args: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [adb_path] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "命令超时"
    except Exception as e:
        return False, str(e)


def adb_shell(adb_path: str, device: str, cmd: str, timeout: int = 10) -> str:
    """执行 adb -s <device> shell <cmd>，返回输出。"""
    ok, output = run_adb(adb_path, ["-s", device, "shell", cmd], timeout=timeout)
    return output if ok else f"(获取失败: {output})"


def get_prop(adb_path: str, device: str, prop: str) -> str:
    return adb_shell(adb_path, device, f"getprop {prop}")


INFO_ITEMS = [
    ("分辨率", "wm size"),
    ("DPI", "wm density"),
]

PROP_ITEMS = [
    ("Android 版本", "ro.build.version.release"),
    ("SDK 版本", "ro.build.version.sdk"),
    ("设备型号", "ro.product.model"),
    ("设备品牌", "ro.product.brand"),
    ("设备名称", "ro.product.name"),
    ("CPU 架构", "ro.product.cpu.abi"),
    ("CPU 架构列表", "ro.product.cpu.abilist"),
    ("硬件平台", "ro.hardware"),
    ("Build 指纹", "ro.build.fingerprint"),
]


def main() -> None:
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS

    print("=" * 60)
    print("  MHG2GA Step 2: 设备详细信息")
    print("=" * 60)
    print()

    adb_path = find_adb()
    print(f"  [INFO] 使用 ADB: {adb_path}")
    print(f"  [INFO] 目标设备: {address}")
    print()

    print("--- 连接设备 ---")
    ok, output = run_adb(adb_path, ["connect", address])
    if ok and ("connected" in output.lower() or "already" in output.lower()):
        print(f"  [PASS] 连接成功: {output}")
    else:
        print(f"  [FAIL] 连接失败: {output}")
        print("         请确认模拟器正在运行，或尝试指定其他地址")
        sys.exit(1)
    print()

    print("--- 屏幕信息 ---")
    for label, cmd in INFO_ITEMS:
        value = adb_shell(adb_path, address, cmd)
        print(f"  {label}: {value}")
    print()

    print("--- 系统属性 ---")
    for label, prop in PROP_ITEMS:
        value = get_prop(adb_path, address, prop)
        print(f"  {label}: {value}")
    print()

    print("--- 内存信息 ---")
    mem_output = adb_shell(adb_path, address, "cat /proc/meminfo", timeout=5)
    for line in mem_output.split("\n")[:6]:
        print(f"  {line.strip()}")
    print()

    print("--- 磁盘空间 ---")
    df_output = adb_shell(adb_path, address, "df /data", timeout=5)
    for line in df_output.split("\n")[:3]:
        print(f"  {line.strip()}")
    print()

    print("--- 当前前台 Activity ---")
    activity_output = adb_shell(
        adb_path, address,
        "dumpsys activity top",
        timeout=10,
    )
    activity_lines = [
        line.strip() for line in activity_output.split("\n")
        if "ACTIVITY" in line
    ]
    if activity_lines:
        for line in activity_lines[:3]:
            print(f"  {line}")
    else:
        print("  (无法获取前台 Activity)")
    print()

    print("--- 已安装应用（崩坏学园2相关） ---")
    pkg_output = adb_shell(adb_path, address, "pm list packages", timeout=15)
    hg2_packages = [
        line for line in pkg_output.split("\n")
        if "houkai" in line.lower()
        or "mihoyo" in line.lower()
        or "bh2" in line.lower()
        or "gun" in line.lower()
    ]
    if hg2_packages:
        for pkg in hg2_packages:
            print(f"  [FOUND] {pkg}")
    else:
        print("  (未发现崩坏学园2相关包，可手动搜索)")
        print("  提示: 崩坏学园2包名通常为 com.miHoYo.bh2 或类似")
    print()

    print("=" * 60)
    print("  设备信息获取完成")
    print("=" * 60)
    print("  >>> 可以继续运行 Step 3 进行 Airtest 截图测试 <<<")
    print()


if __name__ == "__main__":
    main()
