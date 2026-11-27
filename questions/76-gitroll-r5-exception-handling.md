# 76 · GitRoll R5：空 `catch` 与异常吞没治理（202 条）

**Status:** ready-for-agent
**Settling:** 不存在 —— 本工单第一交付物：按文件聚堆清理自研代码中的静默 `catch`（明确失败路径、记日志或显式注释理由）

**Source:** <https://github.com/ArchivalEra/Octave-Full-Wasm/issues/10>

## Scope

- 对应规则：`Handle this exception or don't catch it at all.`（202 条）。
- 优先覆盖 `bridge/assets-loader.js`、`bridge/octave-core.js`、`bridge/octave-embed.js` 与 `build/` 脚本。
- 严禁改变原有容错边界导致页面静默挂死，每批修改后需跑 `build/gates-selftest.sh` 与浏览器回归。
