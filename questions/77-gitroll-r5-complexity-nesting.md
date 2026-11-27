# 77 · GitRoll R5：认知复杂度（97 条）与深层嵌套（116 条）重构

**Status:** ready-for-agent
**Settling:** 不存在 —— 本工单第一交付物：按文件聚堆拆分高认知复杂度与深层嵌套函数，每批重构保持现有自证与浏览器验收全绿

**Source:** <https://github.com/ArchivalEra/Octave-Full-Wasm/issues/10>

## Scope

- 对应规则：`Refactor this function to reduce its Cognitive Complexity`（97 条）与 `Refactor this code to not nest functions more than N levels deep`（116 条）。
- 重点文件：`bridge/assets-loader.js`、`bridge/octave-core.js`、`build/forge-catalog.py`、`bridge/octave-embed.js`。
- 遵循单向拆小函数与早返回原则，不引入行为变化。
