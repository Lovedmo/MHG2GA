"""任务执行引擎：按照步骤树执行工作流。

在后台线程中运行，通过信号与 GUI 通信。
"""

import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from src.core.logger import get_logger
from src.core.device_manager import DeviceManager
from src.core.template_matching import build_template_match_args
from src.core.template_manager import TemplateManager
from src.core.task_model import CONTAINER_TYPES, STEP_TYPE_LABELS, TaskManager, count_steps_recursive

logger = get_logger("task_executor")


class TaskExecutor(QThread):
    """执行单个任务的工作流线程。"""

    step_started = pyqtSignal(str, tuple)   # (step_description, path_tuple)
    step_finished = pyqtSignal(tuple, bool)  # (path_tuple, success)
    task_finished = pyqtSignal(str, bool)    # (task_name, success)
    log_message = pyqtSignal(str)            # INFO 级别日志
    log_debug = pyqtSignal(str)              # DEBUG 级别日志
    request_restart = pyqtSignal(str)         # task_name — 任务失败后请求重启应用

    def __init__(self, task: dict, device_addr: str,
                 device_mgr: DeviceManager, template_mgr: TemplateManager,
                 task_mgr: TaskManager | None = None,
                 parent=None):
        super().__init__(parent)
        self._task = task
        self._addr = device_addr
        self._dm = device_mgr
        self._tm = template_mgr
        self._task_mgr = task_mgr
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        name = self._task.get("name", "未命名")
        steps = self._task.get("steps", [])
        total = count_steps_recursive(steps)
        self.log_message.emit(f"{'='*40}")
        self.log_message.emit(f"[任务开始] {name} (共{total}步, 设备={self._addr})")
        self.log_message.emit(f"{'='*40}")
        try:
            success = self._execute_steps(steps, ())
            manually_stopped = not self._running
            self.log_message.emit(f"{'='*40}")
            if manually_stopped:
                self.log_message.emit(f"[任务⏹ 手动停止] {name}")
            else:
                self.log_message.emit(
                    f"[任务{'✓ 完成' if success else '✗ 失败'}] {name}")
            self.log_message.emit(f"{'='*40}")
            self.task_finished.emit(name, success)
            if not success and not manually_stopped and self._task.get("fail_restart", False):
                self.request_restart.emit(name)
        except Exception as e:
            logger.error("任务执行异常: %s", e)
            self.log_message.emit(f"[任务异常] {name}: {e}")
            self.task_finished.emit(name, False)
            if self._running and self._task.get("fail_restart", False):
                self.request_restart.emit(name)

    def _execute_steps(self, steps: list[dict], base_path: tuple) -> bool:
        for i, step in enumerate(steps):
            if not self._running:
                return False
            path = base_path + (i,)
            stype = step.get("type", "")
            desc = step.get("description", "")
            path_str = ".".join(str(p + 1) for p in path)
            label = STEP_TYPE_LABELS.get(stype, stype)
            step_info = f"[步骤 {path_str}] {label}"
            if stype == "ref":
                ref_name = step.get("ref_task", "")
                if ref_name:
                    step_info += f" → {ref_name}"
            else:
                tpl = step.get("template", "")
                if tpl:
                    step_info += f" ({tpl})"
            if desc:
                step_info += f" - {desc}"
            self.log_message.emit(step_info)
            self.step_started.emit(step_info, path)

            if stype == "check":
                ok = self._exec_check(step, path)
            elif stype == "whileif":
                ok = self._exec_whileif(step, path)
            elif stype == "click":
                ok = self._exec_click(step, path)
            elif stype == "delay":
                ok = self._exec_delay(step, path)
            elif stype == "ref":
                ok = self._exec_ref(step, path)
            else:
                self.log_message.emit(f"  ⚠ 未知步骤类型: {stype}")
                ok = True

            status = "✓" if ok else "✗"
            self.log_message.emit(f"  {status} 结束")
            self.step_finished.emit(path, ok)
            if not ok:
                return False
        return True

    def _exec_check(self, step: dict, path: tuple) -> bool:
        """条件步骤：检测模板是否存在，存在则执行子步骤。"""
        templates = self._resolve_templates(step)
        if not templates:
            self.log_message.emit("  条件步骤无模板，跳过")
            return True

        logic = step.get("match_logic", "or")
        tpl_desc = self._templates_desc(templates, logic)
        retry_enabled = step.get("retry_enabled", False)
        on_fail = step.get("on_fail", "stop")

        if retry_enabled:
            intv = step.get("retry_interval_ms", 1000)
            mode = step.get("timeout_mode", "time")
            max_t = step.get("max_timeout_ms", 30000)
            max_r = step.get("max_retries", 10)
            self.log_message.emit(
                f"  轮询检测 {tpl_desc} "
                f"间隔{self._fmt_ms(intv)}, "
                f"{'超时' + self._fmt_ms(max_t) if mode == 'time' else '最多' + str(max_r) + '次'}")
            found = self._poll_templates(templates, logic, intv, mode, max_t, max_r)
        else:
            self.log_message.emit(f"  单次检测 {tpl_desc}")
            found = self._check_templates(templates, logic)

        if found:
            self.log_message.emit(f"  ✓ 条件成立，执行子步骤 ({len(step.get('children', []))}个)")
            children = step.get("children", [])
            if children:
                return self._execute_steps(children, path)
            return True
        else:
            fail_label = "停止任务" if on_fail == "stop" else "跳过"
            self.log_message.emit(f"  ✗ 条件不成立 {tpl_desc} → {fail_label}")
            return on_fail != "stop"

    def _exec_whileif(self, step: dict, path: tuple) -> bool:
        """循环步骤：条件成立时循环执行子步骤。"""
        templates = self._resolve_templates(step)
        if not templates:
            self.log_message.emit("  循环步骤无模板，跳过")
            return True

        logic = step.get("match_logic", "or")
        tpl_desc = self._templates_desc(templates, logic)
        interval_ms = step.get("check_interval_ms", 1000)
        timeout_mode = step.get("timeout_mode", "time")
        max_timeout_ms = step.get("max_timeout_ms", 1000)
        max_loops = step.get("max_loops", 2)

        limit_desc = (f"超时{self._fmt_ms(max_timeout_ms)}" if timeout_mode == "time"
                      else f"最多{max_loops}轮")
        self.log_message.emit(
            f"  while {tpl_desc}, 间隔{self._fmt_ms(interval_ms)}, {limit_desc}")

        start_time = time.time()
        loop_count = 0

        while self._running:
            if timeout_mode == "time":
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= max_timeout_ms:
                    self.log_message.emit(f"  循环超时退出 (已{self._fmt_ms(int(elapsed_ms))})")
                    break
            else:
                if loop_count >= max_loops:
                    self.log_message.emit(f"  循环达上限退出 (已{loop_count}/{max_loops}轮)")
                    break

            matched = self._check_templates(templates, logic)
            if not matched:
                self.log_message.emit(f"  条件不成立，退出循环 (已执行{loop_count}轮)")
                break

            loop_count += 1
            self.log_message.emit(f"  第{loop_count}轮，执行子步骤...")
            children = step.get("children", [])
            if children:
                ok = self._execute_steps(children, path)
                if not ok:
                    return False

            self._sleep_ms(interval_ms)

        return True

    def _exec_click(self, step: dict, path: tuple) -> bool:
        """点击步骤：检测模板并点击。"""
        template_name = step.get("template", "")
        if not template_name:
            self.log_message.emit("  点击步骤无模板，跳过")
            return True

        on_fail = step.get("on_fail", "stop")
        trigger_delay_ms = step.get("trigger_delay_ms", 250)
        touch_duration_ms = step.get("touch_duration_ms", 50)
        after_delay_ms = step.get("after_delay_ms", 200)

        self.log_message.emit(f"  检测模板 [{template_name}]...")
        result = self._find_template(template_name)
        if result is None:
            fail_label = "停止任务" if on_fail == "stop" else "跳过"
            self.log_message.emit(f"  ✗ 未找到模板 [{template_name}] → {fail_label}")
            return on_fail != "stop"

        x, y = result["click_point"]
        conf = result.get("confidence", 0)
        self.log_message.emit(
            f"  ✓ 匹配成功 (置信度{conf:.2f}), 点击({x}, {y})")

        if trigger_delay_ms > 0:
            self.log_message.emit(f"  触发延迟 {self._fmt_ms(trigger_delay_ms)}...")
            self._sleep_ms(trigger_delay_ms)

        try:
            self._dm.tap(self._addr, int(x), int(y))
        except Exception as e:
            self.log_message.emit(f"  ✗ 触摸失败: {e}")
            return on_fail != "stop"

        if after_delay_ms > 0:
            self.log_message.emit(f"  后延 {self._fmt_ms(after_delay_ms)}...")
            self._sleep_ms(after_delay_ms)
        return True

    def _exec_delay(self, step: dict, path: tuple) -> bool:
        """延时步骤。"""
        duration_ms = step.get("duration_ms", 1000)
        self.log_message.emit(f"  延时等待 {self._fmt_ms(duration_ms)}...")
        self._sleep_ms(duration_ms)
        return True

    def _exec_ref(self, step: dict, path: tuple) -> bool:
        """引用步骤：加载并执行另一个任务的最新步骤。"""
        ref_name = step.get("ref_task", "")
        if not ref_name:
            self.log_message.emit("  引用步骤未设置目标任务，跳过")
            return True
        if not self._task_mgr:
            self.log_message.emit("  ✗ 无法加载引用任务（TaskManager 不可用）")
            return False

        ref_task = self._task_mgr.get_task(ref_name)
        if not ref_task:
            self.log_message.emit(f"  ✗ 引用的任务不存在: {ref_name}")
            return False

        ref_steps = ref_task.get("steps", [])
        if not ref_steps:
            self.log_message.emit(f"  引用任务 [{ref_name}] 无步骤，跳过")
            return True

        total = count_steps_recursive(ref_steps)
        self.log_message.emit(f"  执行引用任务 [{ref_name}] ({total}步)...")
        return self._execute_steps(ref_steps, path)

    # ─── 辅助方法 ───

    def _find_template(self, template_name: str) -> dict | None:
        """截图并匹配单个模板，返回匹配结果或 None（click 步骤使用）。"""
        tpl_path = self._tm.get_template_path(template_name)
        if not tpl_path or not tpl_path.is_file():
            self.log_message.emit(f"  模板文件不存在: {template_name}")
            return None

        try:
            screenshot, _ = self._dm.take_screenshot(self._addr, silent=True)
        except Exception as e:
            self.log_message.emit(f"  截图失败: {e}")
            return None

        return self._match_single(screenshot, template_name)

    @staticmethod
    def _resolve_templates(step: dict) -> list[str]:
        """从步骤数据提取模板列表，兼容旧的 template 单字段。"""
        templates = step.get("templates", [])
        if templates:
            return list(templates)
        tpl = step.get("template", "")
        return [tpl] if tpl else []

    @staticmethod
    def _templates_desc(templates: list[str], logic: str) -> str:
        sep = " | " if logic == "or" else " & "
        return "[" + sep.join(templates) + "]"

    def _check_templates(self, templates: list[str], logic: str = "or") -> bool:
        """对多个模板执行一次截图匹配，按 OR/AND 逻辑返回结果。"""
        if not templates:
            return False
        try:
            screenshot, _ = self._dm.take_screenshot(self._addr, silent=True)
        except Exception as e:
            self.log_message.emit(f"  截图失败: {e}")
            return False

        for tpl_name in templates:
            result = self._match_single(screenshot, tpl_name)
            if logic == "or" and result is not None:
                return True
            if logic == "and" and result is None:
                return False
        return logic == "and"

    def _poll_templates(self, templates: list[str], logic: str,
                        interval_ms: int, timeout_mode: str,
                        max_timeout_ms: int, max_retries: int) -> bool:
        """轮询检测多模板条件是否成立。"""
        start = time.time()
        attempts = 0
        while self._running:
            if self._check_templates(templates, logic):
                return True
            attempts += 1
            if timeout_mode == "time":
                if (time.time() - start) * 1000 >= max_timeout_ms:
                    return False
            else:
                if attempts >= max_retries:
                    return False
            self._sleep_ms(interval_ms)
        return False

    def _match_single(self, screenshot, template_name: str) -> dict | None:
        """在已有截图上匹配单个模板，失败时记录真实置信度（含颜色校验）。"""
        tpl_path = self._tm.get_template_path(template_name)
        if not tpl_path or not tpl_path.is_file():
            return None
        tpl_img = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
        if tpl_img is None:
            return None

        tpl_meta = self._tm.get_template(template_name)
        match_mode = tpl_meta.get("match_mode", "normal") if tpl_meta else "normal"
        mask = self._tm.load_mask(template_name) if match_mode == "mask" else None
        match_args = build_template_match_args(tpl_meta, mask=mask)
        threshold = match_args["threshold"]

        result = DeviceManager.match_template(screenshot, tpl_img, **match_args)
        if result is not None:
            return result

        fail_args = dict(match_args)
        fail_args["threshold"] = -1
        fail_result = DeviceManager.match_template(
            screenshot, tpl_img, **fail_args,
        )
        if fail_result:
            conf = fail_result.get("confidence", 0)
            self.log_debug.emit(
                f"    [{template_name}] 未匹配 (置信度{conf:.4f}, 阈值{threshold:.2f})")
        else:
            self.log_debug.emit(
                f"    [{template_name}] 未匹配 (图像尺寸不兼容)")
        return None

    def _sleep_ms(self, ms: int) -> None:
        """可中断的毫秒级等待。"""
        end = time.time() + ms / 1000.0
        while time.time() < end and self._running:
            time.sleep(min(0.05, end - time.time()))

    @staticmethod
    def _fmt_ms(ms: int) -> str:
        if ms >= 60000 and ms % 60000 == 0:
            return f"{ms // 60000}min"
        if ms >= 1000 and ms % 1000 == 0:
            return f"{ms // 1000}s"
        return f"{ms}ms"
