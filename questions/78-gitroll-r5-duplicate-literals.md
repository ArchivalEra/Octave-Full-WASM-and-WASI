# 78 · GitRoll R5：重复字面量收口（169 条）

**Status:** ready-for-agent
**Settling:** 不存在 —— 本工单第一交付物：将自研代码中的高频重复字符串/数值字面量收口为模块常量并保持自证全绿

**Source:** <https://github.com/ArchivalEra/Octave-Full-Wasm/issues/10>

## Scope

- 对应规则：`Define a constant instead of duplicating this literal N times.`（169 条）。
- 优先处理 `bridge/` 与 `build/` 中同一文件内重复出现的字符串键名、路径前缀与状态常量。
