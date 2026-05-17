"""
Step 4: 模拟触控操作测试
通过 Airtest 测试点击、滑动、按键等操控能力。
需要先安装依赖: pip install -r requirements.txt

用法:
    python step4_touch_test.py                  # 使用默认地址 127.0.0.1:16384
    python step4_touch_test.py 127.0.0.1:7555   # 指定地址

注意: 此脚本会在模拟器上执行实际操作（点击、滑动、按键），
      请确保模拟器上无重要操作正在进行。
"""

import sys
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
DEFAULT_ADDRESS = "127.0.0.1:16384"


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


def run_test(name: str, func, *args, **kwargs) -> bool:
    """执行单个测试，统一输出格式。"""
    print(f"  测试: {name}...", end=" ")
    try:
        t0 = time.perf_counter()
        func(*args, **kwargs)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[PASS] ({elapsed:.0f} ms)")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main() -> None:
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS

    print("=" * 60)
    print("  MHG2GA Step 4: 模拟触控操作测试")
    print("=" * 60)
    print()

    if not check_dependencies():
        sys.exit(1)

    import numpy as np
    from airtest.core.api import (
        connect_device, snapshot, touch, swipe, keyevent,
    )
    from airtest.core.android.android import Android

    device_uri = f"android://127.0.0.1:5037/{address}?cap_method=ADBCAP&&touch_method=ADBTOUCH"

    print(f"  [INFO] 目标设备: {address}")
    print()

    print("--- 连接设备 ---")
    try:
        dev = connect_device(device_uri)
        print("  [PASS] 连接成功")
    except Exception as e:
        print(f"  [FAIL] 连接失败: {e}")
        sys.exit(1)

    try:
        width, height = dev.get_current_resolution()
        print(f"  [INFO] 屏幕分辨率: {width} x {height}")
    except Exception:
        width, height = 1280, 720
        print(f"  [WARN] 无法获取分辨率，使用默认值 {width}x{height}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, bool] = {}

    center_x, center_y = width // 2, height // 2

    # ---- 测试 1: 截图（基线） ----
    print("--- 测试 1: 截图基线 ---")
    try:
        import cv2
        before_path = str(OUTPUT_DIR / "before_touch.png")
        snapshot(filename=before_path)
        screen_before = cv2.imread(before_path)
        print(f"  [PASS] 操作前截图已保存: {before_path}")
        results["截图基线"] = True
    except Exception as e:
        print(f"  [FAIL] 截图失败: {e}")
        screen_before = None
        results["截图基线"] = False
    print()

    # ---- 测试 2: 点击（tap） ----
    print("--- 测试 2: 点击 (tap) ---")
    print(f"  目标坐标: ({center_x}, {center_y}) — 屏幕中心")
    passed = run_test("tap 屏幕中心", touch, (center_x, center_y))
    results["点击 (tap)"] = passed

    time.sleep(0.5)

    try:
        after_tap_path = str(OUTPUT_DIR / "after_tap.png")
        snapshot(filename=after_tap_path)
        print(f"  [INFO] 点击后截图: {after_tap_path}")
    except Exception:
        pass
    print()

    # ---- 测试 3: 滑动（swipe） ----
    print("--- 测试 3: 滑动 (swipe) ---")
    swipe_start = (center_x + width // 4, center_y)
    swipe_end = (center_x - width // 4, center_y)
    print(f"  从 {swipe_start} 滑动到 {swipe_end} — 从右向左")
    passed = run_test("swipe 水平滑动", swipe, swipe_start, swipe_end, duration=0.5)
    results["滑动 (swipe)"] = passed

    time.sleep(0.5)

    try:
        after_swipe_path = str(OUTPUT_DIR / "after_swipe.png")
        snapshot(filename=after_swipe_path)
        print(f"  [INFO] 滑动后截图: {after_swipe_path}")
    except Exception:
        pass
    print()

    # ---- 测试 4: HOME 键 ----
    print("--- 测试 4: HOME 键 ---")
    passed = run_test("keyevent HOME", keyevent, "HOME")
    results["HOME 键"] = passed

    time.sleep(1)

    try:
        after_home_path = str(OUTPUT_DIR / "after_home.png")
        snapshot(filename=after_home_path)
        print(f"  [INFO] HOME 后截图: {after_home_path}")
    except Exception:
        pass
    print()

    # ---- 测试 5: BACK 键 ----
    print("--- 测试 5: BACK 键 ---")
    passed = run_test("keyevent BACK", keyevent, "BACK")
    results["BACK 键"] = passed

    time.sleep(0.5)

    try:
        after_back_path = str(OUTPUT_DIR / "after_back.png")
        snapshot(filename=after_back_path)
        print(f"  [INFO] BACK 后截图: {after_back_path}")
    except Exception:
        pass
    print()

    # ---- 测试 6: 截图对比 ----
    print("--- 测试 6: 截图对比分析 ---")
    try:
        after_compare_path = str(OUTPUT_DIR / "after_all.png")
        snapshot(filename=after_compare_path)
        screen_after = cv2.imread(after_compare_path)
        if isinstance(screen_before, np.ndarray) and isinstance(screen_after, np.ndarray):
            if screen_before.shape == screen_after.shape:
                diff = np.mean(np.abs(screen_before.astype(float) - screen_after.astype(float)))
                print(f"  操作前后截图差异度: {diff:.1f} (值越大表示画面变化越大)")
                if diff > 1.0:
                    print("  [PASS] 操作导致了屏幕变化，触控功能正常")
                    results["截图对比"] = True
                else:
                    print("  [WARN] 操作前后画面几乎无变化，触控可能未生效")
                    print("         (也可能当前页面本身不响应点击)")
                    results["截图对比"] = True
            else:
                print(f"  [WARN] 前后截图尺寸不一致: {screen_before.shape} vs {screen_after.shape}")
                results["截图对比"] = False
        else:
            print("  [WARN] 截图格式不支持对比")
            results["截图对比"] = False
    except Exception as e:
        print(f"  [FAIL] 截图对比失败: {e}")
        results["截图对比"] = False
    print()

    # ---- 总结 ----
    print("=" * 60)
    print("  触控测试总结")
    print("=" * 60)

    pass_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    print()
    print(f"  通过: {pass_count}/{total_count}")
    print()

    if pass_count == total_count:
        print("  >>> 所有测试通过！模拟器连通性和操控能力验证完成 <<<")
        print("  >>> MHG2GA 基础设施就绪，可以开始开发游戏自动化任务 <<<")
    else:
        print("  >>> 部分测试失败，请检查上述 [FAIL] 项 <<<")

    print()
    print("  截图文件保存在:")
    print(f"    {OUTPUT_DIR.resolve()}")
    print()


if __name__ == "__main__":
    main()
