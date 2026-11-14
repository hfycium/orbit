# 第三方组件声明

本文件记录 Orbit 中**实际引入**的第三方代码（不是「参考过」的）。规则见 `docs/reuse-map.md` 第 4 节。

## 当前状态：尚未引入任何第三方代码

截至 2026-11-14，`src/` 下全部代码为本项目原创。已审查并计划移植的代码见下表，**移植前此表不计入义务**——MIT 的署名义务在「复制并分发」时才产生。

| 上游 | 许可证 | 计划用途 | 状态 |
|---|---|---|---|
| viruztt/ProgressPies | MIT | 拖拽与 4px 判定、点击穿透标志、位置恢复 | 待引入（M1） |
| riboly/Glass-Monitor | MIT | `_foreground_is_fullscreen()` 单函数 | 待引入（M1 之后） |

## 引入时必须补齐的字段

每引入一段，按此模板追加一节。缺任何一项都视为未完成：

```markdown
### <上游 owner/repo>

- 上游地址：https://github.com/owner/repo
- 引入时 commit：<sha>（不要写「最新版」——上游一改就查不到了）
- 原始文件：<path/to/file.py>
- 原始函数 / 行号：<symbol> @ <start>-<end>
- 本地位：<src/orbit/...>
- 许可证：MIT
- 版权行：Copyright (c) <year> <holder>
- 本地修改：
  - <改了什么，为什么>
- 完整许可证文本：见本节末尾

<粘贴上游 LICENSE 全文>
```

## 为什么要求 commit 而不只是仓库名

`DESKTOP_CALENDAR` 这类仓库只有几百 KB、作者随时可能重写。三年后回头看「这段从 ProgressPies 抄的」，没有 commit 就无法确认当时抄的是哪一版、有没有后续的 bug 修复被漏掉。行号同理——上游一改行号就漂，所以本文件与 `reuse-map.md` 都同时记函数名。

## 已核实、暂未使用的许可证文本

以下版权行于 2026-11-14 通过 GitHub API 读取原文核对：

| 仓库 | 版权行 |
|---|---|
| Mamihlapinatapaiooo/desktop_calendar | `Copyright (c) 2025 Mamihlapinatapaiooo` |
| viruztt/ProgressPies | `Copyright (c) 2026 Šarūnas Rimša` |
| riboly/Glass-Monitor | `Copyright (c) 2026 riboly` |
| Leo-Corporation/DayBar | `Copyright (c) 2023-2025 Léo Corporation` |
| victor-zhang-2026/LiteCount | `Copyright (c) 2026 Victor Zhang` |

后两者的代码**不会**进入本项目（C# / Swift），列在此处只为记录审查已经做过。

## 明确不引入

| 仓库 | 原因 |
|---|---|
| tiaod/day-progress | 无 LICENSE |
| ArcaEge/day-progress | GPL-3.0，与 MIT 不兼容 |
| Kojjyan/Dayring | LICENSE 明文禁止复制、修改、分发、使用 |
