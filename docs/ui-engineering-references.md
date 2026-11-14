# Orbit UI 工程参考：高星 Qt / Python 项目怎么做界面

> 收集日期：2026-11-14。★ / 许可证 / 语言 / 最后提交均由 `gh api repos/{owner}/{repo}` 当日核对；
> 源码是默认分支 HEAD 实际下载到 `cache/ui-refs/`（已 gitignore）后读的，行号对应当日 commit（见 §7）。
>
> **与 `docs/design-references.md` 分工**：那份回答「做成什么样」（配色、阴影、HIG、动态岛）；
> 这份回答「代码怎么组织」（分层、token、动画驱动、主题广播、DPI、自绘像素对齐）。
> `PLAN.md` 仍是唯一规格来源，本文不改任何已定结论，也不改界面代码。

---

## 0. 结论先行

1. **高星 Qt 项目 UI 好看/好维护的原因不是特效，是三件事**：参数集中成一个 token 层、动画只驱动一个状态值、平台差异收口到一处。Orbit 现在的架构已经踩在前两条上，缺的是把数值彻底搬出 `paintEvent`。
2. **完全同构的参考不存在**。星数最高的 Qt/Python 项目全是「标准控件 + QSS」的常规窗口；跟 Orbit 同为「透明置顶、QPainter 自绘小窗」的项目，星数只有 0–200，且没有环形进度 + 连续形变。所以能借鉴的是**工程结构**，不是成品外观。
3. **许可证是硬约束，且和星数高度负相关**。星数前 6 的 Qt 项目里 5 个是 GPL/AGPL；Orbit 是 MIT，**读思路可以，复制/改写一行都不行**。真正许可证兼容的只有 Spyder、CustomTkinter、napari、TaoQuick、framelesshelper、win32mica、StockWidget。本轮没有复制任何源码，`THIRD_PARTY_NOTICES.md` 无需更新。
4. **Morph 这一段没有成熟实现可抄**。连 8.2k★ 的 QFluentWidgets，动画也只是位移/缩放/淡入淡出的离散效果，没有路径插值。这印证了 `docs/reuse-map.md` 的结论：形变必须自己写。

---

## 1. 数据核对表

★ 为 2026-11-14 快照；「复制」列指**能否把源码放进 MIT 项目**。

| 项目 | ★ | 许可证 | 栈 | 看它的哪一块 | 复制 |
|---|---:|---|---|---|:---:|
| [ankitects/anki](https://github.com/ankitects/anki) | 32,790 | **AGPL-3.0-or-later**（API 显示 `NOASSERTION`，文件头写明 AGPL） | Rust 核心 + PyQt6 UI | 主题/明暗 token、平台差异、窗口状态 | ❌ |
| [kovidgoyal/calibre](https://github.com/kovidgoyal/calibre) | 26,430 | GPL-3.0 | Python / PyQt | 巨型 Qt 应用的资源与 DPI 处理 | ❌ |
| [TomSchimansky/CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | 13,613 | **MIT** | Python / Tkinter | **自绘引擎的像素对齐**、DPI 追踪、主题 JSON | ✅ |
| [qutebrowser/qutebrowser](https://github.com/qutebrowser/qutebrowser) | 11,759 | GPL-3.0 | Python / PyQt | QSS 模板与配置驱动样式 | ❌ |
| [spyder-ide/spyder](https://github.com/spyder-ide/spyder) | 9,396 | **MIT** | Python / PyQt | 尺寸 token、QSS 对象化 | ✅ |
| [zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) | 8,165 | GPL-3.0 | Python / PyQt·PySide | 主题信号、QSS 模板、动画时长表 | ❌ |
| [TagStudioDev/TagStudio](https://github.com/TagStudioDev/TagStudio) | 7,291 | GPL-3.0-only | Python / **PySide6** | 较新的纯 PySide6 分层与主题测试 | ❌ |
| [metabrainz/picard](https://github.com/metabrainz/picard) | 5,372 | GPL-2.0 | Python / PyQt6 | — | ❌ |
| [napari/napari](https://github.com/napari/napari) | 2,805 | BSD-3-Clause | Python / Qt | — | ✅ |
| [jaredtao/TaoQuick](https://github.com/jaredtao/TaoQuick) | 1,521 | **MIT** | QML / C++ | Qt 自绘方案清单 | ✅ |
| [KhamisiKibet/QT-PyQt-PySide-Custom-Widgets](https://github.com/KhamisiKibet/QT-PyQt-PySide-Custom-Widgets) | 994 | GPL-3.0 | Python / Qt | 环形/仪表类自定义控件 | ❌ |
| [wangwenx190/framelesshelper](https://github.com/wangwenx190/framelesshelper) | 863 | **MIT** | C++ / Qt | 无边框窗口底层 | ✅ |
| [zhiyiYo/PyQt-Frameless-Window](https://github.com/zhiyiYo/PyQt-Frameless-Window) | 769 | GPL-3.0 | Python / Qt | DWM 阴影 / Mica / acrylic | ❌ |
| [sbr0574/StockWidget](https://github.com/sbr0574/StockWidget) | 192 | Apache-2.0 | Python / **PySide6** | 同形态：透明置顶浮窗 + 托盘 + JSON 配置 | ✅ |
| [marticliment/win32mica](https://github.com/marticliment/win32mica) | 122 | **MIT** | Python | Win32 材质效果（当前用不上） | ✅ |

**顺手纠正三条二手资料的错误**（搜索结果里普遍写错，别再引用）：

- `musicbrainz/picard` 已迁到 **`metabrainz/picard`**；★ 是 5,372，不是某些文章写的 1.5k。
- 搜到的「PySide6 桌面宠物」项目 **0★ 且无 LICENSE**，只是个人实验，不能当「优秀大型项目」。
- `PyQt-Frameless-Window` 的一些 fork 仍挂着 MIT LICENSE，那是**旧版本快照**；上游 `zhiyiYo/PyQt-Frameless-Window` 现在是 **GPL-3.0**。判断许可证只能看上游当前 LICENSE，不能看 fork。

---

## 2. 六个可借鉴的工程模式

### 2.1 分层：core 不认识 Qt，是大型项目的共识

| 项目 | 分层 |
|---|---|
| Anki | `anki`（Rust 核心，无 GUI）／ `aqt`（Qt UI）。`qt/aqt/main.py` 里的 `AnkiQt` 只做窗口与状态机 |
| Spyder | `spyder/api/*`（字体、配置、样式接口）／ 各插件。`stylesheet.py:19-23` 只 import `api`，不碰插件内部 |
| TagStudio | `tagstudio/core/*` ／ `tagstudio/qt/views/*`，连 QSS 都放在 `qt/views/styles/` |

Orbit 的 `src/orbit/core/`（纯函数、`now`/`t` 外部传入、不 import Qt）+ `ui/`（不碰文件）**与这三家同构**，这是当初架构选择被验证的地方，不要为了「看起来更像大项目」把时钟或配置读进 `core/`。

### 2.2 设计 token：所有颜色和尺寸只有一个来源

- **Anki**：`qt/aqt/colors.py` 只有一行 `from _aqt.colors import *`（token 由构建脚本 `build/configure/src/aqt.rs` 生成）；每个 token 是 `{"light": ..., "dark": ...}` 字典，`theme.py:193-209` 的 `var()` / `qcolor()` 是**唯一**取值口；`stylesheets.py:45-177` 全程 `tm.var(colors.BORDER_SUBTLE)` 这样拼 QSS，没有一个硬编码色值。
- **Spyder**：`utils/stylesheet.py:32-71` 用 `AppStyle` 类把 `MarginSize=3`、圆角、内边距做成常量，其余尺寸一律 `* MarginSize` 推导。
- **TagStudio**：`stylesheets.py:25-123` 每个函数返回一段 QSS，颜色取自 `ThemePalette` 枚举。

**对 Orbit**：`ui/theme.py` 的 `Theme` dataclass 已经是正确起点，但 `ball.py` 里还有 `260 / 200`（动画时长）、`320 / 96`（面板尺寸）、`QFont("Segoe UI", ...)` 等散落数值。`docs/design-references.md` 建议的「环宽 2.5、底轨 alpha 14、16px 字体」之所以能一步改完，前提就是这些数字全在 `Theme` 里。**这是收益最大、风险最低的一步**。

### 2.3 动画：一个可动画属性 → `update()`，绘制只做纯映射

- QFluentWidgets `common/animation.py:280-388`：把 position / scale / angle / opacity 包成 `pyqtProperty` 对象，`setValue()` 里**只调 `self.parent().update()`**；`:391-470` 的 `FluentAnimation(QPropertyAnimation)` 统一管 easing 与时长。
- 时长表（`:472-535`，微软 Fluent 参数）值得记：进入 `FastInvoke` **187ms**、退出 `SoftDismiss` **167ms**、淡入淡出 **83ms**、强调 `StrongInvoke` 667ms（带 `0.13,1.62,0,0.92` 回弹曲线）。**进慢退快**是通用节奏，印证 `design-references.md` 里「退出 160ms」的建议；我们当前 260/200 偏慢，但回弹曲线与「不催促」规格冲突，不要抄。
- **Orbit 已经更彻底**：`ball.py:191-206` 用 `QVariantAnimation` 推单一 `_morph_t`，`ui/morph.py` 的 `frame_at(t, spec)` 是不 import Qt 的纯函数。`t → 几何 → QPainter` 单向数据流，比「多个属性并行动画、绘制时再读状态」更好测。**M2 不要改成多属性动画。**

### 2.4 主题变更：先比对，再广播

- Anki `theme.py:224-244`：`apply_style()` 先算 `theme_changed` / `style_changed`，**都没变直接 return**；变了才 `setPalette` + `setStyleSheet`，最后 `gui_hooks.theme_did_change()` 广播。
- QFluentWidgets `common/config.py:263-273`：`themeChanged` / `themeChangedFinished` / `themeColorChanged` 三个信号 + `ConfigItem.valueChanged`；`common/style_sheet.py:15-66` 的 `StyleSheetManager.register()` 登记 widget，换主题时统一重刷。
- Anki 的 `reduce_motion` 是**用户可配置项、默认开**（`qt/aqt/profiles.py:542-546`），`theme.py:179` 据此给 body 加 `reduce-motion` class；不是自动读系统。写文档时别写成「自动跟随系统」。

**对 Orbit**：① `OrbitApp.refresh()` 每秒被调一次，但百分比大多数秒不变，应加「值没变就不 `update()`」的短路；② 未来「皮肤」只需 `Theme` 实例 + 一次重绘 + 一个信号，**现在不必建 `ui/stylesheet.py` 或注册机**（我们只有一个自绘 widget，QSS 对它无效）；③ 减弱动效可作为皮肤系统的前置项，按 Anki 的做法做成可配置开关。

### 2.5 平台差异收口到一个文件

- Anki `theme.py:163-181` 的 `body_class()` 把 `isWin/isMac/isLin`、`nightMode`、`reduce-motion` 拼成 class；`:211-222` `_determine_night_mode()` 分平台读系统深色（Windows 走 `winreg`，见 `:343-360`）。
- QFluentWidgets `common/style_sheet.py:158-160`：按主题拼资源路径 `:/qfluentwidgets/qss/{dark|light}/xxx.qss`。
- `PyQt-Frameless-Window` `windows/window_effect.py:19-42, 187-232`：用 ctypes 调 `DwmSetWindowAttribute` / `SetWindowCompositionAttribute` 拿 Mica、acrylic 与**原生窗口阴影**，业务代码完全不碰 `hwnd`。
- TagStudio `views/styles/palette.py:34-46` 留了一条注释：*PySide 6.8.0.1 起 `QPalette.ColorRole.Accent` 在 Windows 上失效，只能用 `Highlight`*。**高星项目也是靠注释记录平台坑，不是靠抽象消灭它**——Orbit 的「透明窗口不能用 `QGraphicsDropShadowEffect`」同类，值得写进代码注释而不只是文档。

**对 Orbit**：Windows 特化（托盘、`WA_TranslucentBackground`、`screenAt`、DPI）应集中在 `ui/` 一处，`core/` 里不该出现 `sys.platform`。目前达标。

### 2.6 自绘的像素对齐（Orbit 目前缺的一环）

CustomTkinter 没有原生圆角，只能自己拼图形，它的经验对 QPainter 同样适用：

- `draw_engine.py:41-63` `__calc_optimal_corner_radius()`：圆角半径**按绘制方式取整或对齐到 0.5 步长**，避免抗锯齿毛边；`:29-30` 还按平台选 `polygon_shapes / font_shapes / circle_shapes` 三种画法。
- `draw_engine.py:97-131`：半径先 clamp 到 `min(width, height)/2`，**内圆角 = 外圆角 − 边框宽**（否则描边和填充的曲率对不上，正是 `design-references.md` 第 6 条指出的「圆角与球半径不连续」）。
- `scaling/scaling_tracker.py:6-110`：`ScalingTracker` 单例维护「每个窗口一个 DPI 倍率」，用户倍率 × 系统倍率，100ms 轮询检测缩放变化并回调所有已注册控件。Qt 内建 High-DPI 缩放，但**跨屏拖动 / 运行中改系统缩放**仍需自己监听。

**对 Orbit**：`window_size` 已用 `round()` 取整，但绘制内部（2.5px 环、随 `t` 变化的圆角、1px 描边）在 125%/150% DPI 下会落到非整数设备像素，出现半透明边或抖动。建议**几何按 `t` 连续计算，落笔前按 `devicePixelRatio` 对齐关键半径/线宽**；并让 `screenChanged` / `logicalDotsPerInchChanged` 复用 `window_state.py` 的 clamp 把球夹回 `availableGeometry()`。

---

## 3. 三种主题实现路线，选一条别混

| 路线 | 代表 | 做法 | 适用场景 |
|---|---|---|---|
| QPalette + 明暗字典 | Anki | token → `var()` → 拼 QSS；QPalette 管原生控件 | 标准控件多的窗口（设置、引导） |
| QSS 模板 + 注册机 | QFluentWidgets / Spyder | `string.Template` 变量替换，或 `qstylizer` 把 QSS 解析成对象再改；`StyleSheetManager` 统一重刷 | 组件库、几十种控件 |
| **纯自绘 token** | **Orbit 现状** | `Theme` dataclass → `QPainter` | **只有一个自绘 widget** |

**判据**：QSS 对 `WA_TranslucentBackground` 窗口里 `paintEvent` 手绘的圆环**完全不起作用**。所以球继续走第三条，不要因为看了高星项目就引入 QSS 层。等 M3 面板里真的出现 `QLabel`/`QPushButton` 等标准控件时，再在那一个窗口局部用第一条。

---

## 4. 高星项目里没有的、别照抄的东西

- **连续形变**：QFluentWidgets 全部动画都是离散的位移/淡入/缩放；没有「同一个元素从圆摊平成条」的路径插值。Morph 无参考可抄。
- **阴影做法**：高星项目用 `QGraphicsDropShadowEffect`（不透明控件）或 DWM 原生阴影（普通无边框窗口）。我们是 56px 的透明 `Tool` 窗口，前者出黑底、后者成本远高于自绘两层半透明圆；按 `design-references.md` 自绘。
- **引入依赖**：不要为了「好看」装 QFluentWidgets 或 Frameless-Window —— GPL-3.0 与 MIT 冲突，且它们解决的是「带标题栏的常规窗口」，与悬浮球不同构。
- **把 `StrongInvoke` 的回弹曲线搬进来**：667ms + overshoot 与 PLAN 的「环境提示、不闪烁、不催促」直接冲突。

---

## 5. 对 Orbit 的落地清单（每条可单独验证，均未实施）

| 优先级 | 动作 | 验证方式 |
|---|---|---|
| 1 · 低风险 | `theme.py` 扩容：动画时长、面板尺寸、字体族与字号、描边色、两层阴影参数全部收进 `Theme`；`ball.py` 绘制代码零裸数字 | 改 `Theme` 单值即可改外观；现有单测全绿 |
| 2 · 低风险 | `refresh()` 加「值未变不 `update()`」短路（Anki `apply_style` 做法） | 用假时钟断言 60 次 refresh 只触发 1 次重绘 |
| 3 · 低风险 | 退出动画 200→160ms（与 Fluent 的 187/167 节奏、`design-references.md` 建议一致） | 目测原型；几何测试不受影响 |
| 4 · 中 | 落笔前按 `devicePixelRatio` 对齐环外径/线宽/圆角；圆角改「固定大值 + 高度 clamp」，内圆角减边框宽 | 125% / 150% DPI 下渲染帧对比，锁单测 |
| 5 · 中 | `reduce_motion` 开关（可配置、默认开）：开启时只留淡入、几何瞬间到位 | 加一条 core 层配置 + UI 分支的单测 |
| 6 · 中 | DPI / 屏幕变化信号触发重新夹回可用区域，与 `window_state.py` 恢复共用同一 clamp | 模拟 `QScreen` 变化，断言球仍在 `availableGeometry()` 内 |
| 7 · M3+ | 面板出现标准控件时，再在该窗口局部引入 QPalette/QSS | 届时单独评估，现在不建空壳文件 |

> 与 `docs/design-references.md` §6 的落地顺序关系：那份的第 1 步（改 `theme.py` 参数）与本表第 1 步是**同一件事**，合并做；那份偏视觉数值，本表偏工程收口。

---

## 6. 许可证边界

- 读代码、学思路、记模式：不受许可证限制，本文做的都是这件事。
- 把 GPL/AGPL 项目的源码复制或改写进 MIT 项目：**不行**，会要求整个 Orbit 转为 GPL/AGPL。上表 ❌ 的项目一律只读。
- 本轮**未复制任何一行**，也没有新增依赖，因此 `THIRD_PARTY_NOTICES.md` 不需要改动。将来若真的粘贴 MIT/BSD/Apache 代码，按该文件的模板补 commit、原始文件、行号与完整许可证文本。
- ★ 是会变的快照；许可证以仓库当前 `LICENSE` 为准，API 返回 `NOASSERTION` 时必须人工确认（Anki 就是这种情况）。

---

## 7. 复现命令与源码快照

```bash
# 元数据（表 1）
gh api repos/ankitects/anki --jq '[.full_name,.stargazers_count,.license.spdx_id,.pushed_at]|@tsv'

# 源码（下载到 cache/ui-refs/，已 gitignore）
gh api -H 'Accept: application/vnd.github.raw' \
  repos/ankitects/anki/contents/qt/aqt/theme.py
```

当日 HEAD（行号以此为准）：

| 仓库 | commit |
|---|---|
| ankitects/anki | `827f4aa` |
| spyder-ide/spyder | `49d6a97` |
| zhiyiYo/PyQt-Fluent-Widgets | `3c8299a` |
| TagStudioDev/TagStudio | `7b39cce` |
| TomSchimansky/CustomTkinter | `33a77cb` |
| qutebrowser/qutebrowser | `a2a9c9d` |
| zhiyiYo/PyQt-Frameless-Window | `e86a074` |
| kovidgoyal/calibre | `6078134` |

本文引用的具体文件均已下载到 `cache/ui-refs/`（不入库），文件名形如
`ankitects_anki__qt_aqt_theme.py`，可离线复核行号。
