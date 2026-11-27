# 80 · WASI / 纯 C-ABI 无头计算引擎产物（剥离浏览器 DOM 与 Emscripten JS 胶水）

**Status:** ready-for-agent
**Settling:** 不存在 —— 本工单第一交付物：产出一份脱离浏览器 DOM 与 Emscripten JS 胶水的单线程 `wasm32` WASI `.wasm` / 纯 C-ABI 静态库产物，并通过纯 C 宿主最小嵌入自证（`init`/`eval`/`eval_json`/`on_stdout`/`interrupt`/VFS/几何导出）

## 4 条硬要求

1. **剥离浏览器与 Emscripten JS 运行时依赖**
   - 不依赖 `octave.js`、`em-pthread` WebWorkers、`SharedArrayBuffer`、`loadDynamicLibrary` 与 DOM 挂点（`#octave-raw-output`、`p5canvas`）。
   - 提供纯 WASI `.wasm` 或纯 C-ABI 静态库目标，由宿主（`wasmtime`/`wasmi` 或原生 C FFI）直接装载驱动。
2. **最小纯值嵌入接口（对应 `OctaveEmbed` 语义，纯 C）**
   - 生命周期：`init()` / `shutdown()`
   - 求值通道：`eval(code)`、`eval_json(expr)`（返回结构化 JSON 结果与错误码）
   - 流与控制：`on_stdout` / `on_stderr` 回调、协作式 `interrupt()`、stdin 注入
   - 工作区与 VFS：`workspace()`（`whos` 结构化）、`pwd()` / `cd()`、宿主可挂载虚拟文件系统回调（用于加载 `octave.data` 标准库、`.m` 脚本与 Forge 包）
3. **图形输出纯数据化（延续 `__oct_geometry_export__` 路线）**
   - 不走 `drawnow`/GL/DOM `<canvas>` 注入；统一导出结构化几何数据（`xlim`、`ylim`、`title`、`line`/`text` 对象树）或纯像素帧。
4. **单线程 `wasm32` / 纯 C-ABI 基线（不依赖 Rust）**
   - 不依赖 `memory64 + pthreads + SharedArrayBuffer`，面向移动端（尤其 iOS）与非浏览器沙盒提供单线程可运行基线。

## 一期收敛决策（2026-11-27）

- **目标**：不做 C-ABI 多端原生分发，统一走单线程 `wasm32-wasip1`。
- **一期裁剪**：砍掉 `dlopen` 与 `pthread`（全静态链接，单线程运行）。
- **一期暴露面**：仅暴露 `eval` / `eval_json` / `stdout` / `interrupt` 与标准 WASI 目录挂载（preopened dirs）。
