"""模板匹配参数公共构建逻辑。

用于统一模板工作台测试与任务工作流的匹配入参，避免两端实现漂移。
"""

from typing import Any

import numpy as np


def build_template_match_args(
    template_meta: dict | None,
    mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """根据模板元数据构建 DeviceManager.match_template 入参。

    策略约束：
    - 严格遵循模板中的 ``match_mode``，不做隐式模式切换。
    - 仅当 ``match_mode == "mask"`` 时才传递蒙版，其余模式强制忽略蒙版。
    """
    threshold = template_meta.get("threshold", 0.80) if template_meta else 0.80
    rgb = template_meta.get("rgb", True) if template_meta else True
    roi = template_meta.get("roi") if template_meta else None
    click_offset = template_meta.get("click_offset") if template_meta else None
    match_mode = template_meta.get("match_mode", "normal") if template_meta else "normal"

    if match_mode != "mask":
        mask = None

    return {
        "threshold": threshold,
        "rgb": rgb,
        "roi": roi,
        "click_offset": click_offset,
        "mask": mask,
        "match_mode": match_mode,
    }
