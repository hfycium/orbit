"""绘制参数与节奏参数。**所有颜色、尺寸、时长都从这里取，不要写死在 paintEvent 里。**

这是「皮肤」的地基：将来换皮肤只是换一个 `Theme` 实例，绘制代码不动。
现在只有 `DARK` 一套，别提前造占位主题——空主题比没有主题更容易腐烂。

颜色字段用 `default_factory`：QColor 是可变对象，dataclass 不允许直接当默认值。

数值来源分三类，改之前先看是哪一类：
- 几何（半径、环宽、留白）：与 `morph.StripSpec` 必须对齐，改一处就要看展开还接不接得上。
- 节奏（展开/收起/悬浮延时）：参考 Fluent 的「进慢退快」，别随手调成对称。
- 排版（字号、字体族）：球心只有一个百分比，字号跟着球径走会抖，所以写成定值。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QColor, QFont


def _color(*rgba: int) -> QColor:
    return QColor(*rgba)


@dataclass(frozen=True)
class Theme:
    # --- 几何（与 morph.StripSpec 的默认值必须一致，展开时才接得上）---
    ball_radius: float = 28.0
    ring_width: float = 2.5
    # 内缩 3 而不是 2：环外沿与描边之间要留 2px 呼吸，
    # 否则 100% 时整圈像贴着球边发亮。
    ring_inset: float = 3.0
    # 留白不再只给抗锯齿：外阴影要占 9px，加 1px 下偏移，再留 1px 余量。
    window_margin: float = 11.0
    panel_width: int = 320
    panel_height: int = 96
    panel_radius: float = 16.0

    # --- 节奏（毫秒）---
    # 进入比退出慢：收起是「让开」，不该和展开一样抢注意力。
    expand_ms: int = 260
    collapse_ms: int = 200
    hover_open_ms: int = 300
    hover_close_ms: int = 300

    # --- 排版 ---
    font_families: tuple[str, ...] = ("Segoe UI", "Microsoft YaHei")
    percent_px: int = 16
    # Medium 而不是 DemiBold：球小、字又只有三个字符，粗一档就显得吵。
    percent_weight: QFont.Weight = QFont.Weight.Medium

    # --- 颜色（方向 B「单色克制」：不渐变、不抢余光）---
    body_inner: QColor = field(default_factory=lambda: _color(29, 32, 39))
    body_outer: QColor = field(default_factory=lambda: _color(23, 25, 31))
    # 14 在深色壁纸上几乎与球底同色，环看起来像「只剩一段」；18 是能看出轨道、
    # 又不至于在浅色壁纸上发脏灰的折中。
    track: QColor = field(default_factory=lambda: _color(255, 255, 255, 18))
    accent: QColor = field(default_factory=lambda: _color(169, 199, 255))
    text: QColor = field(default_factory=lambda: _color(239, 242, 248))
    text_muted: QColor = field(default_factory=lambda: _color(239, 242, 248, 120))
    # 深色壁纸上球底与桌面只差十来阶亮度，描边是唯一的分离手段，不能太弱。
    outline: QColor = field(default_factory=lambda: _color(255, 255, 255, 34))
    outline_width: float = 1.0
    shadow: QColor = field(default_factory=lambda: _color(0, 0, 0))
    shadow_offset: float = 1.0
    # 三层同心圆近似柔和阴影：Windows 的透明窗口上，QGraphicsDropShadowEffect 会出黑底，
    # DWM 阴影又要求窗口不是 Tool，所以只能自绘。层数与半径够用即可，别再加。
    shadow_layers: tuple[tuple[float, int], ...] = ((2.0, 30), (4.5, 18), (8.0, 10))

    @property
    def neutral_radius(self) -> float:
        """环的中线半径。与 morph.StripSpec.neutral_radius 同一算法。"""
        return max(self.ball_radius - self.ring_inset - self.ring_width / 2, 1.0)

    @property
    def window_size(self) -> int:
        """窗口边长：球直径 + 两侧留白。留白用于抗锯齿边缘，也是拖拽热区。"""
        return int(round((self.ball_radius + self.window_margin) * 2))


DARK = Theme()
