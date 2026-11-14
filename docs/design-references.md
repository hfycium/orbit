# Orbit UI 设计参考

> 收集日期：2026-11-14。链接均为当日实际访问或检索命中；**非官方来源已标注性质**，可核验。
> 本文只回答两件事：现在为什么丑、该照谁的什么改。不改任何规格结论（规格在 `PLAN.md`）。

---

## 0. 先说清楚「丑」在哪

看完 `cache/ball/sheet_real.png`、`cache/repro-after-start-ball.png`、`cache/finding-002-after.png` 与当前 `ui/ball.py` / `ui/theme.py`，问题不是「不够花」，是**层级、配色、排版三处基础没做**。引导窗口其实已经有层级和留白了，最难看的是球本身。

| # | 问题 | 代码位置 | 为什么显得廉价 |
|---|---|---|---|
| 1 | **完全没有阴影 / 描边** | `ball.py:_paint_body` 只画一个径向渐变圆 | 透明窗口里一个纯色圆盘 = 贴在屏幕上的贴纸，不是「悬浮」。Apple 把「depth, layering, hierarchy」列为材质的首要作用 |
| 2 | **蓝紫三段渐变环** | `theme.py` `accent_start/mid/end` + `QConicalGradient` | 高饱和多色渐变是 2018 年 Dribbble 风，抢注意力，与「环境提示而非催促」的定位正面冲突。Apple Widgets HIG：颜色要增强但**不能与内容竞争** |
| 3 | **环偏粗、底轨发灰** | `ring_width=4.0`，`track=白 alpha30` | 4px / 56px ≈ 7%，视觉上厚重；白 alpha 30 在深底上是一圈脏灰，不是「未完成的轨道」 |
| 4 | **数字用比例字形** | `percent_text()` + `QFont("Segoe UI")`，`pixelSize=14` | `8%` 与 `100%` 宽度不同，居中绘制时进度一更新数字就左右抖；14px DemiBold 在 56px 球里偏挤 |
| 5 | **面板是纯黑空壳** | `ball.py:_paint_morph` 用 `body_outer` 填满 + 一根线 | 没有内边距、没有信息层级、球心文字淡出后整块空白。Apple Widgets 给的标准是 **16pt 边距** |
| 6 | **圆角与球半径不连续** | `morph.py` `corner = 2 + 10*grow` → 12px | 球半径 28，展开后 12px 圆角，曲率在终点跳一下。灵动岛的做法是**固定一个大圆角让高度去 clamp**，圆角根本不需要动画 |

第 1、2 条占观感的大头，且**只改 `theme.py` + 加一层自绘阴影就能解决**，不用动几何。

---

## 1. 形态与动效参考（Orbit 独有的部分，最重要）

| 来源 | 性质 | 具体看什么 |
|---|---|---|
| [Apple HIG · Progress indicators](https://developer.apple.com/design/human-interface-guidelines/progress-indicators) | **官方规范** | 圆形进度**顺时针填充**、determinate 优先。有一条反例值得记：*"Don't switch from the circular style to the bar style"* —— 它说的是**两个不同组件**之间切换会打断界面；这恰好反证了 Orbit 必须坚持「同一个元素连续形变」，而不是「球消失、进度条出现」 |
| [Building the Dynamic Island in React: 5 details](https://dev.to/saurra3h/building-the-iphone-dynamic-island-in-react-5-details-that-make-it-feel-real-6e8) | 社区技术文章 | ① **Resize the shell, don't scale it**（缩放会把内容一起拉伸，我们按 `t` 算几何已经做对）② **圆角不用动画**：固定 32px，矮的时候被 clamp 成胶囊，长高后自然变成圆角卡，形态免费变化 ③ 内容**独立淡入**，退出只给 80ms ④ 弹簧而非线性 ⑤ reduced-motion 只留淡入 |
| [Anatomy of the Dynamic Island · GodUI](https://godui.design/docs/lab/overlays/dynamic-island/learn) | 社区拆解 | 五档**固定尺寸预设**（不是按内容算）；外壳 spring `stiffness 520 / damping 32`；内容 crossfade 独立 0.2s、进出并发。可作为 M2 动画节奏的现成参数 |
| [Morph 词条 · Layerwise](https://layerwise.app/vibe-coding-glossary/morph) | 社区词条 | 把 morph 与 shared element transition 分清楚：morph 是**同一元素在原位变形**，所以形状不能消失。这是「球消失但面板就是球」这条规格的理论依据 |

**可直接搬的三条**：固定大圆角交给高度 clamp、内容淡入与几何分开驱动、退出比进入快（现在 260/200ms 差距太小，建议 260/160ms）。

---

## 2. 材质、阴影、排版（解决「像贴纸」）

| 来源 | 性质 | 可落地的数字 |
|---|---|---|
| [Apple HIG · Materials](https://developer.apple.com/design/human-interface-guidelines/materials) | **官方规范** | 材质的作用是「depth, layering, hierarchy」。关键限制：**Liquid Glass 只用于控件层，不要用在内容层**；文字多的浮层用 regular（更不透明）而非 clear；亮背景上必要时加 **35% 暗色 dimming**。→ 我们的面板承载文字，不该做高透玻璃 |
| [Apple HIG · Widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)（2026-10-13 更新） | **官方规范** | 标准边距 **16pt**，紧凑分组 **11pt**；正文一般 **≥11pt**；**内容圆角要与容器圆角协调**；优先系统字体；颜色不能压过内容；小尺寸只放**一条核心信息**，别为填满而放大内容 |
| [macOS Design Skill · 阴影与间距](https://skillselion.com/skills/davepoon/buildwithclaude/macos-design) | 社区整理（非 Apple 官方） | 分层阴影：`0 0 0 0.5px` 边缘阴影是 **"THE macOS look"**；浮窗用「接触阴影 + 环境阴影」两层；8px 间距网格；面板圆角 12px / 卡片 8px。另注明深色模式下阴影不透明度要 ×2 |
| [Glassmorphism · Chris Lemke](https://chrislemke.github.io/website_designs/designs/Glassmorphism.html) | 社区整理（引 NN/g 三要素） | 玻璃拟态必须**同时**具备：降低填充不透明度 + **背景模糊（必需）** + 半透明描边。缺任一条只是「透明」，不是玻璃。→ 我们若不做模糊，就别自称玻璃，老实走实色 + 描边 + 阴影 |

> **本机限制**：Windows 上给 `WA_TranslucentBackground` 窗口加 `QGraphicsDropShadowEffect` 常出黑底。**用 QPainter 自绘两层半透明圆/圆角矩形当阴影**，比套效果稳，也无需 DWM 模糊。

---

## 3. 环形进度的边界（别抄错对象）

| 来源 | 性质 | 结论 |
|---|---|---|
| [Apple HIG · 健身圆环（中文）](https://developer.apple.com/cn/design/human-interface-guidelines/activity-rings) | **官方规范** | **明文禁止**把三环用于非健身数据、禁止改色/加滤镜/改透明度、**避免渐变、阴影或任何视觉效果**、必须黑底、必须留外边距。**所以不能照抄 Apple 三环的配色**——但反过来看，它自己是「纯色 + 黑底 + 无特效」，恰好说明我们那圈蓝紫渐变是画蛇添足 |
| [Material 3 · Progress indicators](https://m3.material.io/components/progress-indicators/overview) | 官方规范 | 页面确认存在；本次抓取只拿到标题，**具体线宽/轨道色规范未取到，标为待核实**，不要据此写参数 |

---

## 4. 桌面小组件实例（只看设计，不抄代码）

| 来源 | 性质 / 许可证 | 看什么 |
|---|---|---|
| [Rainmeter](https://www.rainmeter.net/) | 开源项目，**GPL v2** | Windows 桌面皮肤生态，官方展示的 `mnml UI`、`Cleartext`、`TextClock` 是「信息密度极低但不空洞」的范本。**GPL，只看图不抄码** |
| [jokyme/Deskset](https://github.com/jokyme/Deskset) | 开源项目，**GPL-3.0**（示例皮肤 MIT） | macOS 原生小组件，内置 Stationery 套装有明暗两套外观、时钟/待办/计时器。看它的**明暗两套配色如何共用一套排版**；主程序 GPL-3.0 不兼容 MIT |
| [OpenClip 浮动弹窗拆解](https://blog.gitcode.com/cc146f6ff6e1c91c0508f6e7c04c7743.html) | 社区文章（转述实现） | 四层玻璃表面：毛玻璃底 → 深色 38% 压暗 → 1pt 渐变描边 → **1.5pt 接触阴影 + 12pt 环境阴影**。以及「无边框面板靠头部拖动」，与我们的面板拖动同构 |

---

## 5. 三个可选方向（参数已对齐 `theme.py` 字段）

| | **B · 单色克制（推荐）** | C · 磨砂玻璃 | D · 暖色语义 |
|---|---|---|---|
| 球底 | `#17191F`，径向差 ≤3% | `rgba(24,26,34,.72)` + 模糊 | `#14161C` |
| 环宽 | **2.5px**（现在 4） | 3px | 3px |
| 强调色 | 单色 `#A9C7FF` 或柔白 `#E8ECF5` | 白 85% | 琥珀 `#E8B86D` → 珊瑚 `#E08A6B`（低饱和双色，暗示时间流逝） |
| 底轨 | 白 alpha **14**（现在 30） | 白 alpha 20 | 白 alpha 12 |
| 描边 | 1px 白 alpha 10 | 1px 白 alpha 22 | 无 |
| 阴影 | 0.5px 边缘 + `0 2px 6px/.18` + `0 10px 24px/.16` | 接触 1.5px + 环境 12px | 同 B |
| 数字 | 16px Medium、**等宽数字(tabular)**、`#EFF2F8` | 同 B | 同 B |
| 面板内边距 | **16px** | 16px | 16px |

**推荐 B 的理由**：与 PLAN 里「环境提示、不变色、不闪烁、不催促」完全一致；低饱和单色不抢余光；改动只在 `theme.py` + `_paint_body` 加描边/阴影，不动 `morph.py` 的几何（M2 刚稳定，别同时改两层）。C 需要背景模糊，Windows 上成本高且易出黑底；D 的渐变仍带「催促」情绪，且和「克制度」那条规格有摩擦。

**明确不做**：不抄 Apple 三环配色（HIG 明文禁止用于非健身数据）；不加呼吸/脉动/变色（除非单独拍板）；不用渐变表达剩余时间。

---

## 6. 落地顺序（每步都能单独看效果）

1. **只改 `theme.py`**：环宽 4→2.5、底轨 alpha 30→14、三段渐变收敛为单色、数字字号 14→16、字重 DemiBold→Medium。零几何风险。
2. **`_paint_body` 加 1px 描边 + 自绘双层阴影**：解决「贴纸感」，收益最大。注意阴影要画在 `window_margin` 的 4px 留白里，别被裁。
3. **球心数字改等宽**（tabular figures 或等宽字体）：消除百分比跳动时的横向抖动。
4. **面板定排版骨架**：16px 内边距、内容淡入与几何分离、退出 160ms。内容本身仍是 M3。
5. 之后才考虑皮肤系统（多套 `Theme` 实例）——现在只有一套，别提前造占位主题。

---

## 附：来源性质说明

- **官方规范**：developer.apple.com / m3.material.io 的 HIG 与组件文档，可直接作为判据引用。
- **社区整理**：dev.to、GodUI、Layerwise、skillselion、chrislemke.github.io、GitCode 博客。参数可用，但**是他人实测/总结，不是平台承诺**；尤其 CSS 的 pt/px 与 Qt 的逻辑像素不能 1:1 照搬。
- **开源项目**：Rainmeter（GPL v2）、Deskset（GPL-3.0）。看设计不复制代码；判断流程见 `docs/reuse-map.md` 第 4 节。
- 未核实项已在正文标出，不当作事实使用。
