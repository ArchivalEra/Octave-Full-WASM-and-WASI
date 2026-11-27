# Native C-ABI Build Space (`liboctave_embed.a`)

Isolated build space for the native static C-ABI Octave engine.

- **Interface**: implements `build/embed/oct_embed.h`.
- **Output**: `liboctave_embed.a` + `oct_embed.h`.
- **Verification**: links a minimal C host binary and runs `test/core/`.
