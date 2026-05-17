"""
Step 3: Airtest 截图测试
通过 Airtest 连接模拟器，执行截图并测量性能。
需要先安装依赖: pip install -r requirements.txt

用法:
    python step3_screenshot.py                  # 使用默认地址 127.0.0.1:16384
    python step3_screenshot.py 127.0.0.1:7555   # 指定地址
"""

import sys
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
DEFAULT_ADDRESS = "127.0.0.1:16384"
SCREENSHOT_ROUNDS = 5


def check_dependencies() -> bool:
    missing = []
    for mod_name, pip_name in [("airtest", "airtest"), ("cv2", "opencv-python"), ("numpy", "numpy")]:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"  [FAIL] 缺少依赖包: {', '.join(missing)}")
        print(f"         请运行: pip install {' '.join(missing)}")
        return False
    return True


def main() -> None:
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS

    print("=" * 60)
    print("  MHG2GA Step 3: Airtest 截图测试")
    print("=" * 60)
    print()

    if not check_dependencies():
        sys.exit(1)

    import numpy as np
    from airtest.core.api import connect_device, snapshot

    device_uri = f"android://127.0.0.1:5037/{address}?cap_method=ADBCAP&&touch_method=ADBTOUCH"

    print(f"  [INFO] 目标设备: {address}")
    print(f"  [INFO] 连接 URI: {device_uri}")
    print()

    print("--- Airtest 连接 ---")
    try:
        dev = connect_device(device_uri)
        print("  [PASS] Airtest 连接成功")
    except Exception as e:
        print(f"  [FAIL] Airtest 连接失败: {e}")
        print("         请确认：")
        print("         1. 模拟器正在运行")
        print("         2. 已通过 step1/step2 验证 ADB 连通")
        print("         3. 已安装 airtest: pip install airtest")
        sys.exit(1)
    print()

    print("--- 设备信息 (Airtest) ---")
    try:
        display = dev.get_current_resolution()
        print(f"  屏幕分辨率: {display[0]} x {display[1]}")
    except Exception as e:
        print(f"  (获取分辨率失败: {e})")
    print()

    print("--- 单次截图测试 ---")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = OUTPUT_DIR / "screenshot.png"

    try:
        t0 = time.perf_counter()
        screen = snapshot(filename=str(screenshot_path))
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000
        print(f"  [PASS] 截图成功")
        print(f"  保存路径: {screenshot_path}")
        print(f"  耗时: {elapsed_ms:.0f} ms")

        import cv2
        if isinstance(screen, np.ndarray):
            img = screen
        elif screenshot_path.exists():
            img = cv2.imread(str(screenshot_path))
        else:
            img = None

        if img is not None:
            h, w = img.shape[:2]
            channels = img.shape[2] if len(img.shape) == 3 else 1
            print(f"  图片尺寸: {w} x {h} (通道数: {channels})")

            mean_val = np.mean(img)
            is_black = mean_val < 5
            is_white = mean_val > 250
            if is_black:
                print("  [WARN] 截图为全黑，模拟器可能未完全启动或屏幕未点亮")
            elif is_white:
                print("  [WARN] 截图为全白，可能存在截图异常")
            else:
                print(f"  [PASS] 截图内容有效（平均像素值: {mean_val:.1f}）")
        else:
            print("  [WARN] 无法读取截图进行有效性验证")
    except Exception as e:
        print(f"  [FAIL] 截图失败: {e}")
        sys.exit(1)
    print()

    print(f"--- 截图性能测试 ({SCREENSHOT_ROUNDS} 轮) ---")
    times = []
    for i in range(SCREENSHOT_ROUNDS):
        t0 = time.perf_counter()
        snapshot(filename=str(OUTPUT_DIR / f"perf_test_{i}.png"))
        t1 = time.perf_counter()
        elapsed = (t1 - t0) * 1000
        times.append(elapsed)
        print(f"  第 {i + 1} 轮: {elapsed:.0f} ms")

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    fps_estimate = 1000.0 / avg_time if avg_time > 0 else 0

    print()
    print("  性能统计:")
    print(f"    平均耗时: {avg_time:.0f} ms")
    print(f"    最快: {min_time:.0f} ms")
    print(f"    最慢: {max_time:.0f} ms")
    print(f"    估算帧率: {fps_estimate:.1f} FPS")
    print()

    for i in range(SCREENSHOT_ROUNDS):
        perf_file = OUTPUT_DIR / f"perf_test_{i}.png"
        if perf_file.exists():
            perf_file.unlink()

    print("=" * 60)
    print("  截图测试完成")
    print("=" * 60)
    if avg_time < 500:
        print(f"  [PASS] 截图性能良好 (平均 {avg_time:.0f}ms)")
    elif avg_time < 1000:
        print(f"  [PASS] 截图性能一般 (平均 {avg_time:.0f}ms)，可考虑切换 MINICAP")
    else:
        print(f"  [WARN] 截图较慢 (平均 {avg_time:.0f}ms)，建议切换 MINICAP 方式")

    print(f"  截图已保存: {screenshot_path}")
    print("  >>> 可以继续运行 Step 4 进行触控操作测试 <<<")
    print()


if __name__ == "__main__":
    main()
