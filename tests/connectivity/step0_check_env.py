"""
Step 0: 环境检测
检查 Python 版本、ADB 可用性、MuMu 12 安装路径、第三方包安装状态。
无需任何第三方依赖，纯标准库实现。
"""

import os
import sys
import shutil
import subprocess
import importlib
from pathlib import Path


MUMU12_POSSIBLE_PATHS = [
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

REQUIRED_PACKAGES = [
    ("airtest", "airtest"),
    ("cv2", "opencv-python"),
    ("numpy", "numpy"),
    ("PIL", "Pillow"),
]


def print_header(title: str) -> None:
    width = 60
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_result(label: str, passed: bool, detail: str = "") -> None:
    status = "[PASS]" if passed else "[FAIL]"
    msg = f"  {status} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def check_python_version() -> bool:
    ver = sys.version_info
    version_str = f"{ver.major}.{ver.minor}.{ver.micro}"
    passed = ver >= (3, 9)
    print_result(
        "Python 版本",
        passed,
        f"{version_str} ({'满足要求 >= 3.9' if passed else '需要 >= 3.9'})",
    )
    return passed


def check_adb_in_path() -> str | None:
    adb_path = shutil.which("adb")
    if adb_path:
        try:
            result = subprocess.run(
                [adb_path, "version"],
                capture_output=True, text=True, timeout=10,
            )
            version_line = result.stdout.strip().split("\n")[0] if result.stdout else "未知版本"
            print_result("系统 PATH 中的 ADB", True, f"{adb_path}\n           {version_line}")
        except Exception:
            print_result("系统 PATH 中的 ADB", True, f"{adb_path}（无法获取版本）")
        return adb_path
    else:
        print_result("系统 PATH 中的 ADB", False, "未在 PATH 中找到 adb")
        return None


def check_mumu12_adb() -> str | None:
    for path in MUMU12_POSSIBLE_PATHS:
        if path.exists():
            print_result("MuMu 12 内置 ADB", True, str(path))
            return str(path)

    print_result("MuMu 12 内置 ADB", False, "未在常见安装路径找到，可手动指定")
    print("           已扫描路径：")
    for p in MUMU12_POSSIBLE_PATHS:
        print(f"             - {p}")
    return None


def check_packages() -> dict[str, bool]:
    results = {}
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", getattr(mod, "VERSION", "未知"))
            print_result(f"包 {pip_name}", True, f"已安装 (v{version})")
            results[pip_name] = True
        except ImportError:
            print_result(f"包 {pip_name}", False, f"未安装，运行: pip install {pip_name}")
            results[pip_name] = False
    return results


def main() -> None:
    print_header("MHG2GA Step 0: 环境检测")
    print()

    print("--- Python 环境 ---")
    py_ok = check_python_version()
    print(f"  [INFO] Python 路径: {sys.executable}")
    print()

    print("--- ADB 工具 ---")
    system_adb = check_adb_in_path()
    mumu_adb = check_mumu12_adb()
    adb_ok = system_adb is not None or mumu_adb is not None
    print()

    print("--- 第三方依赖包 ---")
    pkg_results = check_packages()
    pkg_ok = all(pkg_results.values())
    print()

    print("=" * 60)
    print("  环境检测总结")
    print("=" * 60)
    all_pass = py_ok and adb_ok
    print_result("Python 版本", py_ok)
    print_result("ADB 可用", adb_ok)
    print_result("第三方包完整", pkg_ok, "Step 0-2 不需要第三方包" if not pkg_ok else "")
    print()

    if all_pass:
        print("  >>> 基础环境就绪，可以继续运行 Step 1 <<<")
    else:
        print("  >>> 存在环境问题，请先修复上述 [FAIL] 项 <<<")

    if not pkg_ok:
        missing = [name for name, ok in pkg_results.items() if not ok]
        print(f"\n  提示: 安装缺失包: pip install {' '.join(missing)}")
        print("  或一键安装: pip install -r requirements.txt")

    if mumu_adb and not system_adb:
        print(f"\n  提示: 系统 PATH 未配置 ADB，Step 1-2 将使用 MuMu 内置 ADB:")
        print(f"        {mumu_adb}")

    print()


if __name__ == "__main__":
    main()
