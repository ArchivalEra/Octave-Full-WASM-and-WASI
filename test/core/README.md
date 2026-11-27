# Unified Core Test Suite (`test/core/`)

Shared functional test suite for all three Octave runtime lines:
1. **Browser WASM** (`base` / `w64` via `OctaveEmbed` / Playwright)
2. **WASI** (`wasm32-wasip1` via `wasmtime --dir ...`)
3. **Native C-ABI** (`liboctave_embed.a` via minimal C host)

## Rules
- Cases in `cases/*.m` must have **zero** browser, DOM, WebWorker, or Emscripten-specific assumptions.
- Every case prints `CORE_PASS:<id>` on success and calls `error(...)` on assertion failure.
- Runners execute each case in `manifest.json` and verify `CORE_PASS:<id>` appears in `stdout` with zero unhandled errors.
