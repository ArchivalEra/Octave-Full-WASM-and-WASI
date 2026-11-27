# 79 · GitRoll R5：现代 JS 语法与剩余 `var` / 逗号运算符 / `for-of` / 可选链

**Status:** ready-for-agent
**Settling:** 不存在 —— 本工单第一交付物：清理自研 JS 中的剩余 `var`（42）、逗号运算符（38）、`for-of`（37）与可选链（229）

**Source:** <https://github.com/ArchivalEra/Octave-Full-Wasm/issues/10>

## Scope

- 对应规则：`Prefer using an optional chain expression`（229）、`Unexpected var`（42）、`Unexpected use of comma operator`（38）、`Expected a for-of loop`（37）。
- `bridge/` 改动后需同步 `site/` 镜像并跑通 `node build/113/var-audit.mjs` 与浏览器回归。
