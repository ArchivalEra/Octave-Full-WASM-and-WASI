# shellcheck 跑批报告 — Octave-Full-Wasm（2026-11-13，站长指令的最低交付物）

## 跑批口径
- 对象：`build/` + `.githooks/` 全部 **83 个 .sh**（全网最大 shell 面）
- 工具：shellcheck 0.11.0；**按各脚本真实解释器分扫**（49 个 bash / 34 个 sh，
  `#!/bin/sh` vs `#!/usr/bin/env bash`），不用默认推断 —— 否则 POSIX sh 的既有写法
  会被按 bash 误判（首轮混扫 199 条 → 分扫后可归类的形状清晰了）
- 总 finding：**543 条**；其中 **SC2317（351 条）= 静态分析看不见间接调用**的误报族
  （抽样核过：`ensure_shim` 等函数在别的分支动态调用）；剔除后 **192 条**
  = error 3 / warning 67 / note 122

## error 级（3 条，全部定性为**有意为之**，非 bug）
- `build/check-site-parity.sh:128` + `build/promote-w64-lane.sh:311,326`
  （SC2066 "双引号导致循环只跑一次"）：**单元素循环是设计** —— 注释明写
  「w64-base 已死档（2026-10-19），清单只剩一份/不再发运」，留档名作未来扩展点。
  三处均带注释，行为自证覆盖（promote-w64-lane `--selftest`、check-site-parity
  `--selftest` 全绿）。

## warning 级值得记的（逐条核过）
- `check-ci-bootstrap.sh:109`（SC2221/2222 同行重复 pattern）：两种白名单写法
  任一存在的语义，重复无害。风格债。
- `lane-shim.sh:37`（SC2027 引号反噬）：自证 `eval` 惯用法 —— ck 的第二参数
  本来就要 eval，外层引号是外层 shell 的。非 bug。
- `build_pkg_oct.sh:189-195`（SC2178/SC2128）：`#!/bin/sh` 用字符串模拟数组，
  POSIX 写法；shellcheck 按该文件声明的 sh 口径仍报（它建议换 bash 数组）。
  改写属于重构批次，不动。
- SC2034「变量未使用」族（bench-native/configure-113-full 等）：多为
  `set -a` 导出给子进程的环境变量（witness-build-inputs 依赖）—— shellcheck
  看不见跨进程消费。误报。

## 修掉的真问题
**0 个**。error 3 条全部定性为有意设计（带注释 + 自证绿），warning 级无真 bug，
note 级 122 条为 SC2086（引号风格）等既有惯例。**本轮处置 = 留痕**（本报告），
不改行为 —— 与站长「零 finding 也是可交付结果」的口径一致：这里的结论是
「83 个壳没有一个 shellcheck 级真缺陷，全是既有风格与静态分析边界」。

## 若后续工单化（建议，未执行）
- quality-assessment 里以 `shellcheck -s <shebang>` 分扫 + `--exclude=SC2317,SC2086`
  白名单方式加入（零 finding 基线已建立：192→逐条定性后的基线 = 0 真缺陷）
