# Orbit 开源组件复用地图

> 审查日期：2026-11-14。所有 star / 许可证 / 文件行号均为当日通过 GitHub API 与该 commit 的源码核对，不是转述。
> 复现命令见文末。**本文件只增不改结论**：结论变了就追加一节，写明原结论为何失效。

---

## 0. 一句话结论

**能直接复制的只有三块**：拖拽与点击判定（ProgressPies，已是 PySide6）、全屏检测（Glass-Monitor，纯 ctypes）、点击穿透与位置恢复（ProgressPies）。其余要么语言不通（C# / Swift），要么许可证不允许（无 LICENSE、GPL-3.0、明确专有），要么本身就是 Orbit 的差异点（形变、时间语义），必须自己写。

**同时纠正两处此前的错误**：

| 此前的说法 | 事实 |
|---|---|
| 「NeonGauge 读本地凭证」 | **不存在这个项目**。GitHub 搜 `NeonGauge` 只有三个同名 0–1★ 个体项目，与 AI 额度无关。此条作废，AI 额度功能的参考实现待将来单独调研。 |
| 「Dayring 是 NOASSERTION，需人工确认」 | 已确认：其 LICENSE 写着 **"All Rights Reserved … proprietary … may not copy, modify, distribute, or use this code without explicit written permission"**。比「无许可证」更严——无许可证是默认保留权利，这个是**明文禁止**。零接触。 |

---

## 1. 全量对照表

| 仓库 | 许可证 | 语言/栈 | ★ | 最后提交 | 依赖 | 复用等级 |
|---|---|---|---|---|---|---|
| [viruztt/ProgressPies](https://github.com/viruztt/ProgressPies) | MIT | Python / **PySide6** | 0 | 2026-10-14 | 仅 PySide6 | **直接复用** |
| [riboly/Glass-Monitor](https://github.com/riboly/Glass-Monitor) | MIT | Python / tkinter | 1 | 2026-11-13 | psutil 等（**该函数不需要**） | **直接移植单函数** |
| [Mamihlapinatapaiooo/desktop_calendar](https://github.com/Mamihlapinatapaiooo/desktop_calendar) | MIT | Python / PyQt6 | 0 | 2026-05-30 | PyQt6（与 PySide6 互斥） | **改造复用（需移植）** |
| [Leo-Corporation/DayBar](https://github.com/Leo-Corporation/DayBar) | MIT | C# / WPF | 4 | 2025-01-12 | .NET | 只参考 |
| [victor-zhang-2026/LiteCount](https://github.com/victor-zhang-2026/LiteCount) | MIT | Swift / macOS | 1 | 2026-11-13 | 无 | 只参考 |
| [tiaod/day-progress](https://github.com/tiaod/day-progress) | **无** | Vue / 网页 | 49 | 2022-11-10 | — | 禁止接触 |
| [ArcaEge/day-progress](https://github.com/ArcaEge/day-progress) | **GPL-3.0** | JS / GNOME | 49 | 2026-10-18 | — | 禁止接触 |
| [Kojjyan/Dayring](https://github.com/Kojjyan/Dayring) | **专有（明文禁止）** | Electron | 0 | 2026-02-05 | — | 禁止接触 |

三条许可证判断的边界，说明白：

- **MIT**：可以复制、修改、闭源分发，但必须保留版权声明与许可证全文。本项目的 `THIRD_PARTY_NOTICES.md` 就是干这个的。
- **GPL-3.0**：可以复制，但分发时**整个 Orbit 必须也按 GPL-3.0 开源**。我们打算 MIT，所以两者不兼容——这不是「小心一点就行」，是一旦复制就传染。
- **无许可证 / 明文专有**：不可复制。GitHub 上「公开可见」不等于「可以使用」，默认规则是保留所有权利。**读代码学思路没问题，写进项目不行。**

---

## 2. 直接复用清单

> M1 实现时的实际做法：**按这些写法自己写，没有逐行粘贴上游代码**。所以现在 `THIRD_PARTY_NOTICES.md` 里没有署名义务；将来若真要粘贴，按那份文件的模板补齐（含完整许可证全文）。

### 2.1 ProgressPies · 拖拽与点击判定（最高价值，零移植成本）

`pies/widget.py:238–275`，PySide6 原生。

```python
# 按下：记绝对偏移，不做增量累加
self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
self._dragged = False

# 移动：位移不足 4px 时不算拖拽
target = e.globalPosition().toPoint() - self._drag_offset
if not self._dragged and (target - self.pos()).manhattanLength() < 4:
    return
self._dragged = True
self.move(target)
```

为什么用这个而不是 desktop_calendar 的写法：`desktop_calendar/app/ui/floating_ball.py:107–118` 用 `self.x() + delta` 逐帧累加，多显示器不同 DPI 之间移动时会漂移（每帧取整一次，误差累积）；ProgressPies 存的是「按下时鼠标与窗口左上角的固定偏移」，无论移动多少帧、跨几块屏都不漂。而且它的 4px 阈值**正好等于 PLAN 第二节定的规格**，不需要改数字。

**没有时间阈值**——这点很关键，见下面 2.4 的缺陷对照。

### 2.2 ProgressPies · 点击穿透

`pies/widget.py:463–475`，`_apply_flags()`。

```python
self.setWindowFlag(Qt.WindowTransparentForInput, bool(cfg.get("click_through", False)))
```

这一行直接回答了 PLAN 第七节待定问题 5（要不要鼠标穿透）：**Qt 有现成标志，代价不是「做不到」，而是「穿透后自己点不到」**，所以必须同时提供托盘或热键入口。

一个 Windows 上的坑，它的代码里体现了但没写注释：`setWindowFlag` 对**已经显示**的窗口不生效，必须 `show()` 一次。它每次改 flag 之后都跟着 `self.show()`（`:471–487`），这不是多余。我们实现时要照做，否则开关按了没反应。

### 2.3 ProgressPies · 位置恢复与多显示器

`pies/widget.py:183–222`，`_screen()` + `place()`。

```python
# 从保存的坐标反查它当初在哪块屏上，而不是一律用主屏
s = QGuiApplication.screenAt(QPoint(int(pos["x"]) + 5, int(pos["y"]) + 5))
if s is None:
    s = QGuiApplication.primaryScreen()
g = s.availableGeometry()          # 已排除任务栏
x = max(g.left(), min(x, g.right() - w + 1))   # 钳进工作区
```

我们 M1 只需要「记住球在哪、重启回到那」，但**如果只存坐标不存屏幕、且取主屏的 `availableGeometry` 去钳制，副屏上的球重启后会被拽回主屏**。这块逻辑直接照抄。

### 2.4 Glass-Monitor · 全屏检测（纯函数，可直接移植）

`glass_ui.py:180–215`，`_foreground_is_fullscreen()`。这个文件整体是 tkinter，**但这个函数只依赖 ctypes + win32，与 tkinter 无耦合**，可以原样搬进 `services/`。

两处真本事：

1. **排除桌面和任务栏**。`Progman` / `WorkerW` / `Shell_TrayWnd` / `WindowsDashboard` 这几个窗口也「占满整个屏幕」，但那一刻正是我们想显示悬浮球的时候。不排除就会出现「一回到桌面球就消失」。
2. **用窗口所在显示器的尺寸比对，不是主屏**。`MonitorFromWindow(..., MONITOR_DEFAULTTONEAREST)` + `MONITORINFO.rcMonitor`，多屏下副屏全屏才判得对。

它不需要 `psutil` / `Pillow` / `pystray`（那是监控功能要的），所以**引入成本为零**。

### 2.5 Glass-Monitor · 「自动隐藏」与「用户隐藏」必须分开

`glass_ui.py:1426–1440`，注释原文：

> 用独立的 `_auto_hidden` 标记，**不碰** `_visible` —— 否则会把用户在托盘里选的显示/隐藏状态写坏，下次开机就不对了。

这是设计教训，不是代码。Orbit 将来做「全屏时隐藏」时，如果直接复用「显示/隐藏」这一个状态位，用户在托盘里关掉球、然后切一次全屏再切回来，球会自己冒出来。**规格里要写：视觉可见性 = 用户意愿 ∧ ¬(全屏中)**，两个变量。

### 2.6 desktop_calendar · 原子写（已具备，只补一处）

`app/data_manager.py:41–45` 与我们 `src/orbit/config.py:197–205` 是同一套（临时文件 + `os.replace`）。差别：它没有滚动备份。ProgressPies 的 `pies/store.py` 多一份 `.bak`——读失败时回退到上一次的完整文件。**建议照抄这层**：配置文件被手改坏时，`.bak` 能救回上一次的作息，而不是直接掉进兜底。

### 2.7 desktop_calendar · 自绘 toast 作为托盘通知的备选

`app/ui/notifications.py:9` 起，`FocusCompleteNotification(QDialog)`，自己画一个无边框置顶小窗，`:135` 是它的右下角定位逻辑。

为什么值得留一手：`QSystemTrayIcon.showMessage()` 在 Windows 上会被「通知和操作」设置抑制（专注助手、免打扰、关闭 Telegram 的通知都能拦掉），而 **PLAN 第六节已经承认这一点**——我们只能保证「每个归属日最多请求一次」，不能保证「一定显示一次」。如果验收时发现本机根本弹不出来，就直接换成这个自绘 toast，不依赖系统通知通道。这条路比 `winrt` 走原生 Toast 便宜得多。

---

## 3. 只参考清单（学思路，不复制代码）

| 来源 | 学什么 | 为什么不复制 |
|---|---|---|
| ProgressPies `pies/card.py:20–68` `paint_pie` | 环形绘制的**边界处理**：`cap = FlatCap if 满 或 frac<0.02 else RoundCap`；`frac>=0.9995` 时整圈 `drawEllipse` 而不是画 360° 弧 | 我们是按折线画的（形变需要），不是 `drawArc`。但其「100% 用椭圆、小比例用平头」的判据要搬，否则满进度时会看到起点处一个圆头疙瘩 |
| ProgressPies `pies/theme.py` | 皮肤参数怎么组织：一套 `QPalette` + 少量 `setStyleSheet` | 它是深色单一主题，我们要多皮肤；结构参考，值不用 |
| desktop_calendar `app/ui/ball_body.py:300–355` | 环形进度条的**角度约定**：`drawArc(rect, 90*16, -360*16*progress)`（90° = 12 点方向，负跨度 = 顺时针）、`QConicalGradient(center, 90.0)`、端点光点 `x=cx+r·cos θ, y=cy−r·sin θ` | PyQt6，且我们要形变（折线），无法直接用 |
| desktop_calendar `app/ui/floating_ball.py:49–52` | 窗口标志三件套：`FramelessWindowHint \| WindowStaysOnTopHint \| Tool` + `WA_TranslucentBackground` | PyQt6 枚举写法，移植只是机械替换；可直接写成 PySide6 版本 |
| DayBar `Pages/FirstRun/*` | 首启向导**分页**（功能说明 → 定制 → 完成），而我们的引导是单页 | C#/WPF，代码完全用不上。若将来觉得单页太挤，照它的分页顺序重排我们的 `onboarding.py` |
| LiteCount `FloatingPlacement.swift` | 贴边吸附的**判定顺序**：先判水平贴哪边，再判垂直对齐 | Swift/macOS，且我们用不到吸附（球是可自由拖的） |
| tiaod `src/views/Home.vue` | `newDayBegins` 概念的来源 | **无许可证**。概念已实现为我们的 `day_line`，代码一行未取 |
| ArcaEge `day-progress` | 「顶栏细进度条」的视觉克制 | **GPL-3.0**，会传染 |

---

## 4. 禁止接触清单

| 仓库 | 状态 | 处理 |
|---|---|---|
| tiaod/day-progress | 无 LICENSE | 不读不抄。它的两个 bug（`newDayBegins` 未持久化、`settings.backgournd` 拼写错误）此前已记录，作为「别这么写」的反面材料 |
| ArcaEge/day-progress | GPL-3.0 | 不复制任何代码。若将来 Orbit 改 GPL 再重新评估 |
| Kojjyan/Dayring | LICENSE 明文禁止复制/修改/分发/使用 | 零接触 |
| FloatingCountdown | 无 LICENSE | 零接触（此前已核） |

**判断流程（将来引入任何新仓库时照走）：**

1. 读仓库根的 `LICENSE` / `LICENSE.md` / `COPYING` **原文**，不看 GitHub 侧栏的标签（Dayring 就标成了 NOASSERTION）。
2. 无文件 → 视为保留所有权利，禁止。
3. GPL/AGPL → 只在 Orbit 接受同许可证时才允许。
4. MIT/Apache-2.0/BSD → 允许，但 Apache-2.0 要额外保留 `NOTICE`。
5. 抄完必须能在 `THIRD_PARTY_NOTICES.md` 里指出：上游仓库、commit、文件路径、行号、我们改了什么。

---

## 5. 「必须自己写」的部分

这些不是「暂时没找到现成的」，是**现有项目恰恰都栽在这里**，也是 Orbit 存在的理由：

| 模块 | 为什么没人能替 |
|---|---|
| `core/`（日界线、三模式、进度） | 现有项目全是「0–24 硬编码 + 手填起止」。我们的归属日消歧（05:30 算今天）和模式互斥是新的 |
| `ui/morph.py`（形变几何） | 全网没有第二个「环摊平成面板」的实现。断口位置、弧长参数化、`t` 单一变量，只能自己推 |
| `ui/panel.py`（面板内容） | 待办不上圈、提醒条避开时间轴那端——排版规则是本项目独有的 |
| 时间语义的边界处理 | 跨零点、休眠唤醒补算、临时调整跨日失效 |

---

## 6. 与建议工程结构的差异

对照建议目录，我们的现状与差异：

| 建议 | 现状 | 处理 |
|---|---|---|
| `core/day_key.py` | 已合在 `core/clock.py`（日界线 + 归属日 + 窗口） | **不拆**。拆开后 `day_key` 与 `resolve` 要互相调用，反而绕 |
| `core/schedule.py`、`core/progress.py` | 已一致 | — |
| `core/reminder.py` | 无 | M3 加，提醒时刻计算 + 每归属日去重 |
| `ui/ball.py`、`ui/panel.py`、`ui/settings.py` | 无 | M1 加 `ball.py`，M2 加 `panel.py`，M3 加 `settings.py` |
| `ui/morph.py`、`ui/onboarding.py` | 已一致 | — |
| `storage/config.py` | 现在是 `src/orbit/config.py` | **该搬**。M1 第一步 `git mv`，`storage/` 负责全部持久化 |
| `storage/todos.py` | 无 | M3 加 |
| `services/notifications.py` | 无 | M3 加 |
| `app.py` | 无 | M1 加 |
| `assets/`、`docs/` | 无 | 本轮建 `docs/`；`assets/` 等有图标再建 |

**不预建空目录、不写空壳模块。** 一个还不存在的功能留一个空文件，只会在半年后变成「这文件干什么的」的疑问。

另外 `morph_demo.py` 一轮验证完之后，**保留在 `ui/` 里**当作可运行的几何调试工具（`--render` 能出关键帧图），不删。它不参与打包（PyInstaller 会把它当模块一起收，但没人 import 就不会被调用，代价是几百字节）。

---

## 7. 待审查（不阻塞 M1）

| 仓库 | 用途 | 何时审 |
|---|---|---|
| [ACGpp/DayProgress](https://github.com/ACGpp/DayProgress) | macOS Swift，MIT，桌面浮窗今日进度，形态最接近 | 不做：macOS 专属，抄不了 |
| 各类 AI 额度查询工具（`pinkpixel-dev/quota` Rust 37★、`LQUA`-系） | 未来「AI 账号额度」 | 做那个功能时再审，现在审等于提前付利息 |
| 系统托盘 / 通知的实验 | 睡前提醒 | M3 前，在本机实测 `QSystemTrayIcon.showMessage` 会不会被通知设置吃掉 |

---

## 附：复现方式

```bash
# 许可证与元数据（2026-11-14）
gh api repos/<owner>/<repo> --jq '[.license.spdx_id, .language, .stargazers_count, .pushed_at]'

# 文件树
gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1 --jq '.tree[]|select(.type=="blob")|.path'

# 单文件原文
gh api repos/<owner>/<repo>/contents/<path> -H "Accept: application/vnd.github.raw"
```

本文件引用的行号对应 2026-11-14 各仓库 `HEAD` 的源码；上游若更新，行号会漂，用上面的命令按函数名重新定位。
