"""MHG2GA 构建脚本 — 使用 PyInstaller 打包为可执行文件。

用法:
    python build.py              # 默认构建（目录模式）
    python build.py --onefile    # 单文件模式
    python build.py --clean      # 清理构建产物
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "build.spec"


def clean():
    print("[clean] 清理构建产物...")
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            shutil.rmtree(d)
            print(f"  已删除 {d}")
    print("[clean] 完成")


def build(onefile: bool = False):
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[build] PyInstaller 未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    cmd = [sys.executable, "-m", "PyInstaller"]

    if onefile:
        cmd += [
            "--onefile",
            "--windowed",
            "--name", "MHG2GA",
            "--add-data", f"{ROOT / 'src' / 'gui' / 'resources'};src/gui/resources",
            "--add-data", f"{ROOT / 'assets'};assets",
            "--add-data", f"{ROOT / 'data'};data",
            "--icon", str(ROOT / "src" / "gui" / "resources" / "icon.png"),
            "--exclude-module", "tkinter",
            "--exclude-module", "matplotlib",
            "--exclude-module", "scipy",
            str(ROOT / "src" / "main.py"),
        ]
    else:
        cmd += [str(SPEC_FILE)]

    print(f"[build] 执行: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(ROOT))

    output = DIST_DIR / "MHG2GA"
    if onefile:
        output = DIST_DIR / "MHG2GA.exe"

    if output.exists():
        if not onefile:
            _copy_runtime_dirs(output)
        print(f"\n[build] 构建成功！输出位置: {output}")
    else:
        print(f"\n[build] 构建可能已完成，请检查 {DIST_DIR}")


def _copy_runtime_dirs(dist_app_dir: Path):
    """将可写的 assets/ 和 data/ 复制到 exe 同级目录。"""
    for dirname in ("assets", "data"):
        src = ROOT / dirname
        dst = dist_app_dir / dirname
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  [copy] {dirname}/ → {dst}")


def main():
    parser = argparse.ArgumentParser(description="MHG2GA 构建工具")
    parser.add_argument("--onefile", action="store_true", help="打包为单个 exe 文件")
    parser.add_argument("--clean", action="store_true", help="清理构建产物")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    build(onefile=args.onefile)


if __name__ == "__main__":
    main()
