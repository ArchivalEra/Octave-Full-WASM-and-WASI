# WASI Build Space (`wasm32-wasip1`)

Isolated build space for the single-threaded headless `wasm32-wasip1` Octave engine.

- **No Emscripten**: does not use `emcc`, `post.js`, `octave.js`, `octave.data`, `dlopen`, or `pthread`.
- **Interface**: implements `build/embed/oct_embed.h` (or WASI CLI entrypoint).
- **Verification**: runs `test/core/` via `wasmtime --dir ...`.
