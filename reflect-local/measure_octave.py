#!/usr/bin/env python3
"""Octave-Full-Wasm repo data layer (`reflect-local/measure_octave.py`).

Mechanism lives in `zreflect/`; this module measures host artifacts, deployment
sites, sweep logs, forge shelf/catalog, wasm64/OpenBLAS/Rust lanes, WebGPU,
and Pyodide/SymPy benchmarks. Every number enters `FACTS.json` via `fact()`.

Self-contained: does not import `build/lib` to avoid `gate.py` name collision.
"""
from __future__ import annotations

import glob
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import tarfile
from typing import Any

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ZREFLECT = os.path.join(REPO, "zreflect")
if _ZREFLECT not in sys.path:
    sys.path.insert(0, _ZREFLECT)

from facts import fact  # noqa: E402
from gate import activate_or_fatal, module_meta  # noqa: E402

MODULE = module_meta(
    "Host data layer",
    "Measure host artifacts, site, sweeps, lanes, and ecosystem benchmarks",
    selftest=False,
)

SITE = os.environ.get("OCTAVE_SITE", "/mnt/hdd/octave-wasm-build/site")
LOGS = os.environ.get("SWEEP_LOGS", "/mnt/hdd/octave-wasm-build/sweep-logs")

_CJK_ZIZHENG = "".join(chr(c) for c in (0x81EA, 0x8BC1, 0xFF1A))
_CJK_MOD_OK = "".join(chr(c) for c in (0x4E2A, 0x6A21, 0x5757, 0xFF1A)) + "OK"
_CJK_ARCH_P1 = "".join(chr(c) for c in (0x67B6, 0x6784, 0x65AD, 0x8A00, 0xFF1A))
_CJK_MEMBERS_ALL_W64 = "".join(chr(c) for c in (0x4E2A, 0x6210, 0x5458, 0x5168, 0x662F))
_CJK_RATIO = "".join(chr(c) for c in (0x6BD4, 0x503C))
_CJK_MATMUL = "".join(chr(c) for c in (0x77E9, 0x9635, 0x4E58))
_CJK_CEILING = "".join(chr(c) for c in (0x4E0A, 0x9650))
_CJK_ONE_MARK = "".join(chr(c) for c in (0x2460,))
_CJK_TOTAL_PREFIX = "".join(chr(c) for c in (0x5408, 0x8BA1, 0xFF1A))
_CJK_SUITE_SUFFIX = "".join(chr(c) for c in (0x5957,))


def sha256sum(path: str, chunk: int = 1 << 20) -> str:
    """Compute hex SHA-256 of `path`."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _read_json(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _read_text(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _selftest_pass_count(script: str) -> int | None:
    """Run `--selftest` and parse PASS count without guessing zero."""
    try:
        r = subprocess.run(
            [sys.executable or "python3", script, "--selftest"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=REPO,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(_CJK_ZIZHENG + r"(\d+) PASS", r.stdout)
    if not m:
        m = re.search(r"(\d+) PASS / 0 fail", r.stdout)
    return int(m.group(1)) if m else None


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=REPO,
            timeout=20,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _py(expr: str) -> str:
    return 'python3 -c "%s"' % expr


def _mo_cmd(expr: str) -> str:
    return _py("import sys;sys.path.insert(0,'reflect-local');import measure_octave as mo;%s" % expr)


def _bench_median(log_dir: str, log: str, label: str) -> float | None:
    """Extract median seconds for `label` from bench-core log formats."""
    text = _read_text(os.path.join(log_dir, log))
    if text is None:
        return None
    for line in text.splitlines():
        if line.startswith("BENCH_JSON"):
            val = _bench_json_lookup(line[len("BENCH_JSON"):], label)
            if val is not None:
                return val
    m = re.search(r"(?m)^[^\n]*?" + re.escape(label) + r"[^\n]*?\s([0-9.]+)s\s*\(", text)
    return float(m.group(1)) if m else None


def _bench_json_lookup(raw: str, label: str) -> float | None:
    try:
        results = json.loads(raw).get("results") or {}
    except ValueError:
        return None
    for k, v in results.items():
        if label in k and isinstance(v, dict) and v.get("median") is not None:
            return float(v["median"])
    return None


def _bench_line(path: str, case: str) -> float | None:
    text = _read_text(path)
    if text is None:
        return None
    m = re.search(r"^\s*%s\s+([0-9.]+)s" % re.escape(case), text, re.M)
    return float(m.group(1)) if m else None


def _bench3_median(log_dir: str, pattern: str, case: str) -> float | None:
    vals: list[float] = []
    for r in (1, 2, 3):
        text = _read_text(os.path.join(log_dir, pattern % r))
        if text is None:
            return None
        m = re.search(r"SPEED_JSON(\{.*\})", text)
        if not m:
            return None
        v = (json.loads(m.group(1)).get("results") or {}).get(case, {}).get("median")
        if v is None:
            return None
        vals.append(float(v))
    return sorted(vals)[1]


def _probe_sum(path: str, pat: str = r"=== (\d+) PASS / 0 FAIL ===") -> int | None:
    text = _read_text(path)
    if text is None:
        return None
    m = re.search(pat, text)
    return int(m.group(1)) if m else None


def _collect_manifest_and_site(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    man_p = os.path.join(SITE, "octave.build.json")
    man = _read_json(man_p)
    if man is not None:
        me = man.get("measured", {})
        if me.get("simd", {}).get("v128") is not None:
            facts["wasm_v128"] = fact(
                me["simd"]["v128"],
                _py("import json;print(json.load(open('%s'))['measured']['simd']['v128'])" % man_p),
                "site/octave.build.json",
                "SIMD 判据；非 SIMD 那版是 0",
            )
        if me.get("exported_functions") is not None:
            facts["exported_functions"] = fact(
                me["exported_functions"],
                _py("import json;print(json.load(open('%s'))['measured']['exported_functions'])" % man_p),
                "site/octave.build.json",
                "M2 保活集大小（M1 约 44987）",
            )
        if me.get("fonts"):
            facts["fonts_count"] = fact(
                len(me["fonts"]),
                _py("import json;print(len(json.load(open('%s'))['measured']['fonts']))" % man_p),
                "site/octave.build.json",
            )
        facts["jspi_entry"] = fact(
            bool(me.get("jspi_entry")),
            _py("import json;print(bool(json.load(open('%s'))['measured'].get('jspi_entry')))" % man_p),
            "site/octave.build.json",
            "B 姿势的可挂起入口在不在",
        )
    elif os.path.exists(man_p):
        print("Warning: failed to read %s" % man_p, file=sys.stderr)


def _collect_site_artifacts(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    for rel, key in (
        ("octave.wasm", "wasm_sha"),
        ("octave.js", "js_sha"),
        ("octave.data", "data_sha"),
        ("octave.build.json", "build_json_sha"),
        ("matrix-android.html", "matrix_page_sha"),
    ):
        p_ = os.path.join(SITE, rel)
        if not os.path.exists(p_):
            continue
        facts[key] = fact(sha256sum(p_), "sha256sum %s | cut -d' ' -f1" % p_, "site/%s" % rel)
        if rel == "octave.wasm":
            facts["wasm_bytes"] = fact(os.path.getsize(p_), "stat -c%%s %s" % p_, "site/octave.wasm")
    for rel, key in (("octave.data", "data_bytes"), ("octave.js", "js_bytes")):
        p_ = os.path.join(SITE, rel)
        if os.path.exists(p_):
            facts[key] = fact(os.path.getsize(p_), "stat -c%%s %s" % p_, "site/%s" % rel)


def _collect_headers_and_env(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    hdr = os.path.join(SITE, "assets", "octinc", "octave-headers.tar.gz")
    if os.path.exists(hdr):
        try:
            with tarfile.open(hdr) as tf:
                n = sum(1 for m in tf.getmembers() if m.name.endswith((".h", ".hh", ".tcc")))
            facts["octave_headers_count"] = fact(
                n,
                "tar -tzf %s | grep -cE '\\.h$|\\.hh$|\\.tcc$'" % hdr,
                "site/assets/octinc/octave-headers.tar.gz",
                "wasm32 安装树里**已 stage** 的头数（compileExtension 的头路径规模）",
            )
        except (OSError, tarfile.TarError) as exc:
            print("Warning: cannot read %s: %s" % (hdr, exc), file=sys.stderr)
    lw = os.path.join(REPO, "build", "113", "link-web.sh")
    txt = _read_text(lw)
    if txt is not None:
        names = set(re.findall(r"\$\{([A-Za-z0-9_]+):[-+]", txt)) - {"1"}
        names -= set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=\(", txt, re.M))
        facts["env_vars"] = fact(
            len(names),
            _mo_cmd("f={};mo._collect_headers_and_env(f);print(f['env_vars']['value'])"),
            "build/113/link-web.sh",
        )


def _scan_sweep_dir(dir_path: str) -> tuple[int, int, int]:
    try:
        logs = [f for f in os.listdir(dir_path) if f.startswith("accept-") and f.endswith(".log")]
    except OSError:
        return 0, 0, 0
    suites = total = fails = 0
    for f in logs:
        txt = _read_text(os.path.join(dir_path, f)) or ""
        m = re.findall(r"=== *(\d+) PASS / (\d+) FAIL *===", txt)
        if m:
            suites += 1
            total += int(m[-1][0])
            fails += int(m[-1][1])
            continue
        m2 = re.findall(r"===.*" + _CJK_MOD_OK + r" *(\d+)", txt)
        if m2:
            suites += 1
            total += int(m2[-1])
            f2 = re.findall(r"TRAP *(\d+)", txt)
            fails += int(f2[-1]) if f2 else 0
    return suites, total, fails


def _collect_sweeps_and_oct(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    try:
        dirs = sorted((d for d in os.listdir(LOGS) if d.startswith("2026")), reverse=True)
    except OSError:
        dirs = []
    for d in dirs:
        dpath = os.path.join(LOGS, d)
        try:
            n = sum(1 for f in os.listdir(dpath) if f.startswith("accept-") and f.endswith(".log"))
        except OSError:
            continue
        if n < 40:
            continue
        suites, total, fails = _scan_sweep_dir(dpath)
        if suites >= 40 and fails == 0:
            facts["accept_suites"] = fact(suites, _mo_cmd("print(mo._scan_sweep_dir(%r)[0])" % dpath), "sweep-logs/%s" % d)
            facts["accept_pass"] = fact(total, _mo_cmd("print(mo._scan_sweep_dir(%r)[1])" % dpath), "sweep-logs/%s" % d, "最近一次**全绿**扫描的 PASS 合计")
            break
    lane_site = os.environ.get("LANE_SITE", SITE)
    for sub, key, why in (
        ("oct-w64", "oct_w64_files", "w64 档 `assets/oct-w64/` 条数"),
        ("octdir-w64", "octdir_w64_files", "w64 档 `assets/octdir-w64/` 条数"),
        ("oct", "oct_base_files", "基础档 `assets/oct/` 条数"),
        ("octdir", "octdir_base_files", "基础档 `assets/octdir/` 条数"),
    ):
        d = os.path.join(lane_site if sub.endswith("-w64") else SITE, "assets", sub)
        if os.path.isdir(d):
            count = sum(1 for _r, _x, fs in os.walk(d) for f in fs if f.endswith(".oct"))
            facts[key] = fact(count, "find %s -name '*.oct' | wc -l" % d, "site/assets/%s" % sub, why)


def _collect_probe_lane_and_e2(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    pl = os.environ.get("PROBE_LANE_LOG", os.path.join(os.path.dirname(SITE), "probe-lane.log"))
    txt = _read_text(pl)
    if txt is not None:
        m = re.search(r"===\s*(\d+) PASS / (\d+) FAIL\s*===", txt)
        if m:
            facts["probe_lane_pass"] = fact(
                int(m.group(1)),
                _py("import re;print(re.search(r'===\\s*(\\d+) PASS / (\\d+) FAIL',open(%r).read()).group(1))" % pl),
                os.path.basename(pl),
                "选档探针的 PASS 数（FAIL 必须 0）；站点四格/双档不同 ⇒ 看 cmd 的 SITE_DIR",
            )
            facts["probe_lane_fail"] = fact(
                int(m.group(2)),
                _py("import re;print(re.search(r'===\\s*(\\d+) PASS / (\\d+) FAIL',open(%r).read()).group(2))" % pl),
                os.path.basename(pl),
            )
    e2a = os.environ.get("E2_ARTIFACTS", os.path.join(os.path.dirname(SITE), "e2-artifacts"))
    e2l = os.environ.get("E2_LOGS", os.path.join(os.path.dirname(SITE), "e2-logs"))
    for tag, variant in (("e2_single", "single"), ("e2_threaded", "threaded")):
        bjp = os.path.join(e2a, variant, "octave.build.json")
        bj = _read_json(bjp)
        if bj is None:
            continue
        files = (bj.get("measured") or {}).get("files") or {}
        w = files.get("octave.wasm") or {}
        facts[tag + "_verdict"] = fact(bj.get("verdict"), _py("import json;print(json.load(open(%r))['verdict'])" % bjp), "octave.build.json")
        facts[tag + "_wasm_sha"] = fact(w.get("sha256"), "sha256sum %s/%s/octave.wasm | cut -d' ' -f1" % (e2a, variant), "octave.wasm")
        facts[tag + "_wasm_bytes"] = fact(w.get("bytes"), "stat -c%%s %s/%s/octave.wasm" % (e2a, variant), "octave.wasm")
    _collect_e2_bench(facts, e2l)


def _collect_e2_threaded_bench(facts: dict[str, Any], e2l: str, lane_mat: float | None) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    t_mat, t_lu = _bench_median(e2l, "e2-bench.log", _CJK_MATMUL), _bench_median(e2l, "e2-bench.log", "lu(")
    if t_mat is not None:
        facts["e2_threaded_matmul500_s"] = fact(t_mat, _mo_cmd("print(mo._bench_median(%r,'e2-bench.log',mo._CJK_MATMUL))" % e2l), "e2-logs/e2-bench.log")
    if t_lu is not None:
        facts["e2_threaded_lu800_s"] = fact(t_lu, _mo_cmd("print(mo._bench_median(%r,'e2-bench.log','lu('))" % e2l), "e2-logs/e2-bench.log")
    if t_mat and lane_mat:
        facts["e2_threaded_matmul500_ratio"] = fact(round(lane_mat / t_mat, 1), _mo_cmd("print(round(mo._bench_median(%r,'lane-bench.log',mo._CJK_MATMUL)/mo._bench_median(%r,'e2-bench.log',mo._CJK_MATMUL),1))" % (e2l, e2l)), "派生")
    rc_path = os.path.join(e2l, "e2-oct-threaded.rc")
    rc_txt = _read_text(rc_path)
    if rc_txt and rc_txt.strip().isdigit():
        facts["e2_threaded_oct_rc"] = fact(int(rc_txt.strip()), _py("print(int(open(%r).read().strip()))" % rc_path), "e2-logs/e2-oct-threaded.rc")


def _collect_e2_bench(facts: dict[str, Any], e2l: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    e2_mat = _bench_median(e2l, "e2-measure-s.log", _CJK_MATMUL)
    lane_mat = _bench_median(e2l, "lane-bench.log", _CJK_MATMUL)
    e2_lu = _bench_median(e2l, "e2-measure-s.log", "lu(")
    lane_lu = _bench_median(e2l, "lane-bench.log", "lu(")
    for k, v, log, lbl in (
        ("e2_matmul500_s", e2_mat, "e2-measure-s.log", "mo._CJK_MATMUL"),
        ("lane_matmul500_s", lane_mat, "lane-bench.log", "mo._CJK_MATMUL"),
        ("e2_lu800_s", e2_lu, "e2-measure-s.log", "'lu('"),
        ("lane_lu800_s", lane_lu, "lane-bench.log", "'lu('"),
    ):
        if v is not None:
            facts[k] = fact(v, _mo_cmd("print(mo._bench_median(%r,%r,%s))" % (e2l, log, lbl)), "e2-logs/%s" % log)
    if e2_mat and lane_mat:
        facts["e2_matmul500_ratio"] = fact(round(lane_mat / e2_mat, 2), _mo_cmd("print(round(mo._bench_median(%r,'lane-bench.log',mo._CJK_MATMUL)/mo._bench_median(%r,'e2-measure-s.log',mo._CJK_MATMUL),2))" % (e2l, e2l)), "派生")
    if e2_lu and lane_lu:
        facts["e2_lu800_ratio"] = fact(round(lane_lu / e2_lu, 2), _mo_cmd("print(round(mo._bench_median(%r,'lane-bench.log','lu(')/mo._bench_median(%r,'e2-measure-s.log','lu('),2))" % (e2l, e2l)), "派生")
    _collect_e2_threaded_bench(facts, e2l, lane_mat)


def _rm_count(path: str) -> int | None:
    rm_py = "import sys;d=open(sys.argv[1],'rb').read();print(d.count(bytes([0xFD,0x87,0x02])))"
    try:
        out = subprocess.run(["python3", "-c", rm_py, path], capture_output=True, text=True, timeout=30).stdout.strip()
        return int(out or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _collect_w64_lane(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    w64a = os.environ.get("W64_ARTIFACTS", os.path.join(os.path.dirname(SITE), "w64-artifacts"))
    bjp = os.path.join(w64a, "octave.build.json")
    bj = _read_json(bjp)
    if bj is not None:
        me = bj.get("measured") or {}
        facts["w64_verdict"] = fact(bj.get("verdict"), _py("import json;print(json.load(open(%r))['verdict'])" % bjp), "w64-artifacts/octave.build.json", "只有 ok 才可部署（fail-closed）")
        facts["w64_wasm64"] = fact(bool(me.get("wasm64")), _py("import json;print(bool(json.load(open(%r))['measured'].get('wasm64')))" % bjp), "w64-artifacts/octave.build.json", "wasm 内存段 limits flags bit2 = 1 ⇒ 真 64 位")
        facts["w64_shared_memory"] = fact(bool((me.get("threads") or {}).get("shared_memory")), _py("import json;print(bool((json.load(open(%r))['measured'].get('threads') or {}).get('shared_memory')))" % bjp), "w64-artifacts/octave.build.json", "目标形态 = memory64 **+ 多线程**（shared 是这个轴的硬身份）")
        facts["w64_malloc"] = fact((bj.get("declared") or {}).get("malloc") or me.get("malloc"), _py("import json;d=json.load(open(%r));print((d.get('declared') or {}).get('malloc') or d['measured'].get('malloc'))" % bjp), "w64-artifacts/octave.build.json", "现役 w64 的分配器（工单 59 起 = mimalloc，由 relink.sh w64 模式表声明）")
        if (me.get("simd") or {}).get("v128") is not None:
            facts["w64_v128"] = fact(me["simd"]["v128"], _py("import json;print(json.load(open(%r))['measured']['simd']['v128'])" % bjp), "w64-artifacts/octave.build.json")
        _collect_w64_exports_and_witness(facts, w64a, bjp, me)
        wf = (me.get("files") or {}).get("octave.wasm") or {}
        facts["w64_wasm_sha"] = fact(wf.get("sha256"), "sha256sum %s/octave.wasm | cut -d' ' -f1" % w64a, "w64-artifacts/octave.wasm")
        facts["w64_wasm_bytes"] = fact(wf.get("bytes"), "stat -c%%s %s/octave.wasm" % w64a, "w64-artifacts/octave.wasm")
    _collect_w64_cand(facts)


def _collect_w64_exports_and_witness(facts: dict[str, Any], w64a: str, bjp: str, me: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    if me.get("exported_functions") is not None:
        w64wasm = os.path.join(w64a, "octave.wasm")
        rmn = _rm_count(w64wasm)
        if rmn is not None:
            facts["w64_relaxed_madd"] = fact(
                rmn,
                cmd="python3 -c \"import sys;d=open(sys.argv[1],'rb').read();print(d.count(bytes([0xFD,0x87,0x02])))\" %s" % w64wasm,
                source="%s 的字节级 f64x2.relaxed_madd 计数（×dd 87 02）" % w64wasm,
                note="relaxed-simd FMA 指令数（工单 52）。⚠ 量法本身有生命周期：`grep relaxed_madd` 是**被证伪的量法**（见 build/instruments.json）——本键的 cmd 已避开它（字节级）。calibrate= 用已知含它的样本自证。",
                calibrate="python3 -c \"import sys;d=open(sys.argv[1],'rb').read();print(d.count(bytes([0xFD,0x87,0x02])))\" test/fixtures/relaxed_madd_min.wasm",
                calibrate_expect="1",
            )
        facts["w64_exported_functions"] = fact(me["exported_functions"], _py("import json;print(json.load(open(%r))['measured']['exported_functions'])" % bjp), "w64-artifacts/octave.build.json")
    facts["w64_build_recipe_ok"] = fact(
        "ok",
        cmd="python3 build/113/witness-build-inputs.py",
        source="build/build-inputs.json 的声明式检查 vs 仓库配方文件",
        note="构建**输入**的不变式（配方层）：link-web.sh 无 -flto / 含 -fwasm-exceptions；w64 车道含 -sMEMORY64=1。",
    )
    facts["w64_build_tool_match"] = fact(
        "match",
        cmd="python3 build/113/witness-build-provenance.py w64",
        source="site/w64/octave.build.json 的 tool.script_sha256 vs build/113/link-web.sh",
        note="贵事实的便宜见证：部署件记录的构建脚本 sha 必须 == 仓库现役脚本。",
    )


def _collect_w64_cand(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    w64c = os.environ.get("W64_CAND_ARTIFACTS", os.path.join(os.path.dirname(SITE), "w64-artifacts-mimalloc"))
    bjp = os.path.join(w64c, "octave.build.json")
    bj = _read_json(bjp)
    if bj is None:
        return
    me = bj.get("measured") or {}
    facts["w64_cand_verdict"] = fact(bj.get("verdict"), _py("import json;print(json.load(open(%r))['verdict'])" % bjp), "w64-artifacts-mimalloc/octave.build.json", "候选产物：verdict=ok + 全量验收全绿 ⇒ 可发运（发运=产品决定）")
    facts["w64_cand_malloc"] = fact(
        (bj.get("declared") or {}).get("malloc") or me.get("malloc"),
        "python3 build/113/write-build-manifest.py --exports %s/octave.wasm" % w64c,
        "w64-artifacts-mimalloc/octave.build.json",
        "分配器（产物探针 = 导出段里的 mi_version；工单 59；mimalloc 工单 57 实测 −27%）。",
    )
    facts["w64_cand_exported_functions"] = fact(me.get("exported_functions"), _py("import json;print(json.load(open(%r))['measured']['exported_functions'])" % bjp), "w64-artifacts-mimalloc/octave.build.json")
    cf = (me.get("files") or {}).get("octave.wasm") or {}
    facts["w64_cand_wasm_sha"] = fact(cf.get("sha256"), "sha256sum %s/octave.wasm | cut -d' ' -f1" % w64c, "w64-artifacts-mimalloc/octave.wasm")
    facts["w64_cand_wasm_bytes"] = fact(cf.get("bytes"), "stat -c%%s %s/octave.wasm" % w64c, "w64-artifacts-mimalloc/octave.wasm")


def _collect_hotpath_and_rust(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    hp_path = os.path.join(REPO, "build", "113", "hotpath.py")
    try:
        spec = importlib.util.spec_from_file_location("hotpath", hp_path)
        if spec and spec.loader:
            hp = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(hp)
            for k, v in (hp.read_facts() or {}).items():
                entry = dict(v)
                entry.pop("replay", None)
                entry.pop("witness", None)
                entry.pop("witness_expect", None)
                if k == "hotpath_top" and entry.get("source"):
                    entry["cmd"] = _py("import json;t=json.load(open(%r))['hotspots'][0];print('%%s %%.1f%%%%'%%(t['name'],t['selfPct']))" % entry["source"])
                facts[k] = entry
    except (OSError, ImportError, RuntimeError) as exc:
        print("Warning: hotpath failed (%s): %s" % (hp_path, exc), file=sys.stderr)
    rf = os.path.join(os.path.dirname(SITE), "w64-logs", "rustfill-spike.log")
    rf_txt = _read_text(rf)
    if rf_txt:
        m7 = re.search(_CJK_RATIO + r"=([0-9.]+)", rf_txt)
        if m7:
            facts["rust_fill_spike_ratio"] = fact(
                float(m7.group(1)),
                _mo_cmd("import re;print(float(re.search(mo._CJK_RATIO+r'=([0-9.]+)',open(%r).read()).group(1)))" % rf),
                "w64-logs/rustfill-spike.log",
                "Rust slice::fill / C++ 标量 fill 的 2^24 填充比值（<1 = Rust 快）；实测 >1 ⇒ 候选②否决——带宽绑定热点换语言无益",
            )
    g5 = subprocess.run([sys.executable, os.path.join(REPO, "build", "113", "check-rust-toolchain.py")], capture_output=True, text=True, encoding="utf-8")
    facts["rust_patch_toolchain_ok"] = fact("ok" if g5.returncode == 0 else "red:%d" % g5.returncode, "python3 build/113/check-rust-toolchain.py", "build/113/rust/{rust-toolchain.toml,Cargo.toml} + build/113/build-rustsort*.sh", "G5（工单 63）：工具链输入钉住了没。ok = 四条全过；red = 逐条点名在 stderr")


def _collect_sort_and_ip(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    wlog = os.path.join(os.path.dirname(SITE), "w64-logs")
    rs_p = os.path.join(wlog, "rustsort-spike.log")
    rs_txt = _read_text(rs_p)
    if rs_txt:
        m8 = re.search(r"sort 2e6: base=([0-9.]+)ms cand=([0-9.]+)ms " + _CJK_RATIO + r"=([0-9.]+)", rs_txt)
        if m8:
            for idx, (k, note) in enumerate(
                (
                    ("rust_sort_spike_base_ms", "octave_sort<double>（timsort）2M 随机 doubles 排序"),
                    ("rust_sort_spike_cand_ms", "Rust driftsort（stable）同负载"),
                    ("rust_sort_spike_ratio", "内核比值（<0.867 = ≥1.15× 加速门槛）；实测 0.247 = 4× ⇒ ADOPT"),
                ),
                1,
            ):
                facts[k] = fact(float(m8.group(idx)), _mo_cmd("import re;print(float(re.search(r'sort 2e6: base=([0-9.]+)ms cand=([0-9.]+)ms '+mo._CJK_RATIO+r'=([0-9.]+)',open(%r).read()).group(%d)))" % (rs_p, idx)), "w64-logs/rustsort-spike.log", note)
    _collect_rust_ab(facts, wlog)
    _collect_ip_vs_next(facts, wlog)


def _ab_medians(ab_p: str) -> dict[tuple[str, str], int]:
    ab_txt = _read_text(ab_p) or ""
    med: dict[tuple[str, str], int] = {}
    for side in ("on", "off"):
        for tag in ("asc", "desc"):
            vals = sorted(int(x) for x in re.findall(r"round\d+ %s %s wall=(\d+)ms" % (side, tag), ab_txt))
            if vals:
                med[(side, tag)] = vals[len(vals) // 2]
    return med


def _collect_rust_ab(facts: dict[str, Any], wlog: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    ab_p = os.path.join(wlog, "rust-sort-ab.log")
    med = _ab_medians(ab_p)
    if not med:
        return
    if ("on", "asc") in med and ("off", "asc") in med and med[("off", "asc")]:
        facts["w64_rustsort_ab_asc_ms"] = fact(med[("on", "asc")], _mo_cmd("print(mo._ab_medians(%r)[('on','asc')])" % ab_p), "w64-logs/rust-sort-ab.log", "候选（rust_sort 开）2M 随机 double 排序墙钟中位（含 rand；w64 槽 COI）")
        facts["w64_rustsort_base_ab_ms"] = fact(med[("off", "asc")], _mo_cmd("print(mo._ab_medians(%r)[('off','asc')])" % ab_p), "w64-logs/rust-sort-ab.log", "对照（同树旋钮关）同负载墙钟中位")
        facts["w64_rustsort_ab_asc_ratio"] = fact(round(med[("on", "asc")] / med[("off", "asc")], 3), _mo_cmd("m=mo._ab_medians(%r);print(round(m[('on','asc')]/m[('off','asc')],3))" % ab_p), "w64-logs/rust-sort-ab.log", "asc 端到端比值（<0.867 = ≥1.15× 门槛）⇒ 实测 2.0× ADOPT")
    if ("on", "desc") in med and ("off", "desc") in med and med[("off", "desc")]:
        facts["w64_rustsort_ab_desc_ratio"] = fact(round(med[("on", "desc")] / med[("off", "desc")], 3), _mo_cmd("m=mo._ab_medians(%r);print(round(m[('on','desc')]/m[('off','desc')],3))" % ab_p), "w64-logs/rust-sort-ab.log", "desc 端到端比值（同门槛）")


def _ip_vs_next_med(vt: str, side: str, case: str) -> float | None:
    vals: list[float] = []
    for b in vt.split("=== round"):
        hm = re.match(r"\d+ (IP|NEXT)", b.strip())
        if hm and hm.group(1) == side:
            m = re.search(r'"%s":\{"median":([0-9.]+)' % case, b)
            if m:
                vals.append(float(m.group(1)))
    vals.sort()
    return vals[len(vals) // 2] if vals else None


def _collect_ip_vs_next(facts: dict[str, Any], wlog: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    vsp = os.path.join(wlog, "bench-IP-vs-NEXT.log")
    vt = _read_text(vsp)
    if not vt:
        return
    sip, snx = _ip_vs_next_med(vt, "IP", "sort 2e6"), _ip_vs_next_med(vt, "NEXT", "sort 2e6")
    if sip and snx:
        facts["ip_vs_next_sort_ip_ms"] = fact(sip, _mo_cmd("print(mo._ip_vs_next_med(open(%r).read(),'IP','sort 2e6'))" % vsp), "w64-logs/bench-IP-vs-NEXT.log", "IllegalPerformance(8761) sort 2e6 中位")
        facts["ip_vs_next_sort_next_ms"] = fact(snx, _mo_cmd("print(mo._ip_vs_next_med(open(%r).read(),'NEXT','sort 2e6'))" % vsp), "w64-logs/bench-IP-vs-NEXT.log", "wasm64-NEXT(8869) sort 2e6 中位")
        facts["ip_vs_next_sort_ratio"] = fact(round(sip / snx, 3), _mo_cmd("t=open(%r).read();print(round(mo._ip_vs_next_med(t,'IP','sort 2e6')/mo._ip_vs_next_med(t,'NEXT','sort 2e6'),3))" % vsp), "派生", "sort 2e6 比值（<1 = IP 快）")


def _top_pct(sect: str, name: str) -> float | None:
    m = re.search(r"([0-9.]+)%.*?\b" + re.escape(name) + r"\b", sect)
    return float(m.group(1)) if m else None


def _hotpath3_vals(hpp: str) -> tuple[float | None, float | None, float | None]:
    hp_txt = _read_text(hpp) or ""
    lm = dv = bt = None
    for sect in hp_txt.split("## snippet:"):
        if "x.^0.7" in sect:
            lm = round(sum(x for x in (_top_pct(sect, "exp_inline"), _top_pct(sect, "pow"), _top_pct(sect, "log_inline")) if x), 1)
            dv = round(sum(x for x in (_top_pct(sect, "do_rc_map"), _top_pct(sect, "elem_xpow")) if x), 1)
        if "fft(x)" in sect:
            bt = _top_pct(sect, "blk_trans")
    return lm, dv, bt


def _collect_locale_xpow_hotpath3(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    wlog = os.path.join(os.path.dirname(SITE), "w64-logs")
    llp = os.path.join(wlog, "locale-all-lanes.log")
    lt = _read_text(llp)
    if lt is not None:
        facts["locale_contract_lanes"] = fact(
            lt.count("8 PASS / 0 FAIL"),
            _py("print(open(%r).read().count('8 PASS / 0 FAIL'))" % llp),
            "w64-logs/locale-all-lanes.log",
            "locale 确定性契约通过的车道数（应=4）。契约 = 报错英文 + 数字 C locale (sprintf('%.3f',3.14159)=='3.142')；机制 = 无 NLS .mo + interpreter.cc 强制 LC_NUMERIC/LC_TIME='C'。issue #4 方案 A 的可测形态",
        )
    xsp = os.path.join(wlog, "xpow-spike.log")
    xt = _read_text(xsp)
    if xt:
        md, mb, mr = re.search(r"driver_only=([0-9.]+)ms", xt), re.search(r"base=([0-9.]+)ms", xt), re.search(r"ratio=([0-9.]+)", xt)
        if md and mb and float(mb.group(1)) > 0:
            facts["xpow_driver_spike_pct"] = fact(round(float(md.group(1)) * 100.0 / float(mb.group(1)), 1), _py("import re;t=open(%r).read();d=float(re.search(r'driver_only=([0-9.]+)ms',t).group(1));b=float(re.search(r'base=([0-9.]+)ms',t).group(1));print(round(d*100/b,1))" % xsp), "w64-logs/xpow-spike.log", "elem_xpow 驱动层（octave_quit + 逐元素索引）占 base 的百分比 = 候选④的绝对天花板；实测 ~2% ≪ 15%（1.15× 门槛）⇒ 候选④排除")
        if mr:
            facts["xpow_driver_spike_ratio"] = fact(float(mr.group(1)), _py("import re;print(float(re.search(r'ratio=([0-9.]+)',open(%r).read()).group(1)))" % xsp), "w64-logs/xpow-spike.log", "Rust 紧循环 vs Octave 形状驱动的比值（含同一 libm pow）")
    hpp = os.path.join(wlog, "hotpath-final3.log")
    if os.path.exists(hpp):
        lm, dv, bt = _hotpath3_vals(hpp)
        if lm is not None and dv is not None:
            facts["hotpath_xpow_libm_pct"] = fact(lm, _mo_cmd("print(mo._hotpath3_vals(%r)[0])" % hpp), "w64-logs/hotpath-final3.log", "x.^y 热点里 libm 超越函数（exp+pow+log）合计自占比——IEEE 钉死不可换")
            facts["hotpath_xpow_driver_pct"] = fact(dv, _mo_cmd("print(mo._hotpath3_vals(%r)[1])" % hpp), "w64-logs/hotpath-final3.log", "x.^y 热点里 Octave C++ 驱动（elem_xpow 逐元素 + do_rc_map 复数重启）合计——唯一残余可缝轴（有界，候选④；需 G6 延迟断言）")
        if bt is not None:
            facts["hotpath_fft_blktrans_pct"] = fact(bt, _mo_cmd("print(mo._hotpath3_vals(%r)[2])" % hpp), "w64-logs/hotpath-final3.log", "fft 热点里 blk_trans（8×8 分块转置）自占比——纯数据置换=带宽绑定")


def _collect_cand_sha_emcc_pins(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    wlog = os.path.join(os.path.dirname(SITE), "w64-logs")
    cand_wasm = "/mnt/hdd/octave-wasm-build/artifacts-w64-rust-on/octave.wasm"
    if os.path.exists(cand_wasm):
        facts["w64_rustsort_cand_sha"] = fact(
            sha256sum(cand_wasm),
            "sha256sum %s | cut -d' ' -f1" % cand_wasm,
            "artifacts-w64-rust-on/octave.wasm（site-illegalperf w64 槽同源）",
            "rust-sort 候选产物 sha；2026-10-07 已发运（用户批准，8761 w64 档同 sha）",
        )
    e6p = os.path.join(wlog, "emcc6-probe.log")
    e6_txt = _read_text(e6p)
    if e6_txt:
        m6 = re.search(r"geomean\(cand6/base\) = ([0-9.]+)", e6_txt)
        if m6:
            facts["emcc6_probe_geomean"] = fact(float(m6.group(1)), _py("import re;print(float(re.search(r'geomean\\(cand6/base\\) = ([0-9.]+)',open(%r).read()).group(1)))" % e6p), "w64-logs/emcc6-probe.log", "emcc 6.0.10/5.0.7 每调用几何均值（<1 = 6 更快）；实测 ≈1.00 ⇒ 工具链升级无编译器红利")
    pins = _git("submodule", "status")
    if pins:
        facts["upstream_submodule_count"] = fact(len(pins.splitlines()), "git submodule status | wc -l", ".gitmodules")
        oct_pin = _git("-C", "upstream/octave", "rev-parse", "--short=12", "HEAD")
        if oct_pin:
            facts["octave_pin"] = fact(oct_pin, "git -C upstream/octave rev-parse --short=12 HEAD", ".gitmodules + upstream/octave", "Octave wasm 分支（tarball 生成件 + 平台补丁）的 pin")


def _collect_forge_shelf_and_catalog(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    shelf_pkgs = os.path.join(REPO, "shelf", "packages")
    if os.path.isdir(shelf_pkgs):
        n = ver = 0
        for f in sorted(os.listdir(shelf_pkgs)):
            if f.endswith(".json"):
                entry = _read_json(os.path.join(shelf_pkgs, f))
                if entry is not None:
                    n += 1
                    ver += 1 if entry.get("verified") else 0
        facts["forge_shelf_packs"] = fact(n, "ls shelf/packages/*.json | wc -l", "shelf/（submodule Octave-Extra-Content）", "货架上的包档案数（每包一文件）")
        facts["forge_shelf_verified"] = fact(ver, "grep -l '\"verified\": {' shelf/packages/*.json | wc -l", "shelf/", "已验证（--probe 实测过）的包数；未验证的默认不上架")
    cat_p = os.path.join(SITE, "assets", "forge-catalog.json")
    cat = _read_json(cat_p)
    if cat is not None:
        _collect_catalog_details(facts, cat_p, cat)
    elif os.path.exists(cat_p):
        print("Warning: failed to read catalog %s" % cat_p, file=sys.stderr)
    _collect_port_selftests(facts)


def _collect_catalog_pack_sizes(facts: dict[str, Any], cat: str, packs: list[dict[str, Any]], rel_cat: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    for nm, k, field, why in (
        ("pyodide", "pyodide_tree_bytes", "size", "pyodide 整树 `assets/pyodide/` 字节预算（form:\"tree\" 的 size）"),
        ("pyodide", "pyodide_wasm_bytes", "url", "pyodide 树里主 wasm 的字节（与整树 size 不是同一个对象，都是有意设计）"),
        ("omc", "omc_tree_bytes", "size", "omc 整目录字节预算（MSL 等资产必须落兄弟目录，不许进此目录）"),
    ):
        p = next((x for x in packs if x.get("name") == nm), None)
        if not p:
            continue
        if field == "size" and p.get("size") is not None:
            facts[k] = fact(p["size"], _py("import json;print([p['size'] for p in json.load(open('%s'))['packs'] if p['name']=='%s'][0])" % (cat, nm)), rel_cat, why)
        elif field == "url" and p.get("url"):
            u = os.path.normpath(os.path.join(os.path.dirname(cat), os.pardir, p["url"]))
            if os.path.exists(u):
                facts[k] = fact(os.path.getsize(u), "stat -c%%s %s" % u, os.path.relpath(u, "/mnt/hdd/octave-wasm-build"), why)
    omc = next((x for x in packs if x.get("name") == "omc"), None)
    if omc and isinstance(omc.get("files"), dict):
        facts["omc_files_bytes"] = fact(sum((f or {}).get("bytes", 0) for f in omc["files"].values()), _py("import json;p=[x for x in json.load(open('%s'))['packs'] if x['name']=='omc'][0];print(sum(f['bytes'] for f in p['files'].values()))" % cat), rel_cat, "omc files[] 下载闭包逐件 bytes 之和（与整目录 size 的差 = 不进闭包的文件）")


def _collect_catalog_details(facts: dict[str, Any], cat: str, c: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    packs = c.get("packs") or []
    rel_cat = os.path.relpath(cat, "/mnt/hdd/octave-wasm-build")
    facts["forge_catalog_packs"] = fact(len(packs), _py("import json;print(len(json.load(open('%s'))['packs']))" % cat), rel_cat, "站点货架上架的包数（客户端 catalog() 读它）")
    plug = [p for p in packs if "oct" in (p.get("kinds") or [])]
    facts["forge_catalog_oct_packs"] = fact(len(plug), _py("import json;print(len([p for p in json.load(open('%s'))['packs'] if 'oct' in (p.get('kinds') or [])]))" % cat), rel_cat, "含**异架构预编译 .oct** 的包数（按需安装拒绝它们；见设计稿 §6A）")
    if c.get("shelf_commit"):
        facts["forge_catalog_shelf_commit"] = fact(str(c["shelf_commit"])[:7], _py("import json;print(json.load(open('%s'))['shelf_commit'][:7])" % cat), rel_cat, "catalog 由哪一版货架（submodule commit）生成")
    msl = next((x for x in packs if x.get("name") == "modelica-standard-library"), None)
    if msl and msl.get("form") == "file" and msl.get("size") is not None:
        facts["msl_zip_bytes"] = fact(msl["size"], _py("import json;print([p['size'] for p in json.load(open('%s'))['packs'] if p['name']=='modelica-standard-library'][0])" % cat), rel_cat, "MSL 单 zip 字节（form:\"file\" ⇒ size == 该文件字节）")
    if c.get("octave"):
        facts["forge_catalog_octave"] = fact(c["octave"], _py("import json;print(json.load(open('%s'))['octave'])" % cat), rel_cat, "货架按哪个 Octave 版本过滤（应从 fork 的 configure.ac 读）")
    _collect_catalog_pack_sizes(facts, cat, packs, rel_cat)


def _collect_port_selftests(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    for key, script, label in (
        ("port_validator_selftest_pass", "build/extra-content/validate-content-list.py", "content-list 端口校验器自证 PASS 数（形状/词表/协商规则/裁决①②/license 类型）"),
        ("port_gate_selftest_pass", "build/extra-content/check-content-port.py", "端口闸门自证 PASS 数（golden 全过 + bad 全红 + 词表单一产地 + pkg/tree 两形态覆盖）"),
        ("forge_gate_selftest_pass", "build/113/check-forge-catalog.py", "站点货架闸门自证 PASS 数（R1–R8：含非货架域 R7 + size sanity R8）"),
        ("forge_catalog_selftest_pass", "build/forge-catalog.py", "货架装配器自证 PASS 数（含上游表 stage 的 fail-closed 用例）"),
    ):
        if os.path.exists(os.path.join(REPO, script)):
            n = _selftest_pass_count(script)
            if n is not None:
                facts[key] = fact(n, _mo_cmd("print(mo._selftest_pass_count(%r))" % script), script, label)


def _collect_w64_mem_probe(facts: dict[str, Any], memlog: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    mtxt = _read_text(memlog)
    if mtxt is None:
        return
    for key, pat, note in (
        ("w64_mem_5g_bytes", r"^mem5g_bytes=(\d+)$", "单线程 memory64 分配 80000 页（非 COI 页，buffer 是 ArrayBuffer）"),
        ("w64_mem_8g_bytes", r"^mem8g_bytes=(\d+)$", "单线程 memory64 分配 131072 页"),
        ("w64_mem_coi_5g_bytes", r"^mem[s]hared5g_bytes=(\d+)$", "COI 页 shared memory64 分配 80000 页（buffer 是 SharedArrayBuffer）"),
    ):
        m = re.search(pat, mtxt, re.M)
        if m:
            facts[key] = fact(int(m.group(1)), _py("import re;print(int(re.search(%r,open(%r).read(),re.M).group(1)))" % (pat, memlog)), os.path.basename(memlog), note)
    mf = re.search(r"===\s*\d+ PASS / (\d+) FAIL\s*===", mtxt)
    if mf:
        facts["w64_mem_probe_fail"] = fact(int(mf.group(1)), _py("import re;print(int(re.search(r'===\\s*\\d+ PASS / (\\d+) FAIL',open(%r).read()).group(1)))" % memlog), os.path.basename(memlog), "内存探针 FAIL 数（必须 0；含 wasm32 上限 / index 陷阱 / BigInt 三条反证）")


def _collect_libm_and_w64_logs(facts: dict[str, Any]) -> str:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    w64l = os.environ.get("W64_LOGS", os.path.join(os.path.dirname(SITE), "w64-logs"))
    lsp = os.path.join(os.path.dirname(SITE), "w64-logs", "libm-spike-verdict.txt")
    ls_txt = _read_text(lsp)
    if ls_txt:
        m = re.search(r"geomean\(cand/base\) = ([0-9.]+)", ls_txt)
        if m:
            facts["libm_spike_geomean"] = fact(float(m.group(1)), _py("import re;print(float(re.search(r'geomean\\(cand/base\\) = ([0-9.]+)',open(%r).read()).group(1)))" % lsp), "w64-logs/libm-spike-verdict.txt", "链接期标量 libm 替换（同源重编覆盖）的每调用几何均值；≥1.5 才值得注册插件 —— 实测 <1.0 ⇒ 负判决（wasm 无标量 FMA，见 NOTES-libm.md）")
    i64p = os.path.join(w64l, "i64.txt")
    i64_txt = _read_text(i64p)
    if i64_txt and i64_txt.strip().isdigit():
        facts["w64_i64_insns"] = fact(int(i64_txt.strip()), _py("print(int(open(%r).read().strip()))" % i64p), "w64-logs/i64.txt", "64 位的指令层证据（wasm32 版为 0）")
    octp = os.path.join(w64l, "oct-wasm64.txt")
    oct_txt = _read_text(octp)
    if oct_txt:
        parts = oct_txt.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            facts["w64_oct_wasm64"] = fact(int(parts[0]), _py("print(int(open(%r).read().split()[0]))" % octp), "w64-logs/oct-wasm64.txt", "`.oct` 车道里 wasm64 的个数（side module 的指针宽度必须与主模块一致）")
            facts["w64_oct_files"] = fact(int(parts[1]), _py("print(int(open(%r).read().split()[1]))" % octp), "w64-logs/oct-wasm64.txt", "车道 `.oct` 总数")
    memlog = os.environ.get("W64_MEM_LOG", os.path.join(w64l, "mem-probe.log"))
    _collect_w64_mem_probe(facts, memlog)
    return os.path.dirname(memlog)


def _floor_stats(w64logd: str) -> tuple[int, int, int]:
    fp = ff = 0
    eng: set[str] = set()
    for f in sorted(glob.glob(os.path.join(w64logd, "floor-*.log"))):
        t = _read_text(f)
        if not t:
            continue
        m = re.search(r"===\s*(\d+) PASS / (\d+) FAIL\s*===", t)
        if m:
            fp += int(m.group(1))
            ff += int(m.group(2))
        eng.update(re.findall(r"^\s*(?:PASS|fail) \| (\S+) · " + _CJK_ONE_MARK, t, re.M))
    return len(eng), fp, ff


def _collect_floor_and_openblas(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    if not glob.glob(os.path.join(w64logd, "floor-*.log")):
        return
    n_eng, fp, ff = _floor_stats(w64logd)
    facts["floor_matrix_engines"] = fact(n_eng, _mo_cmd("print(mo._floor_stats(%r)[0])" % w64logd), "w64-logs/floor-*.log", "跑过的引擎：Chromium 154 / Chromium 125 / Firefox / WebKit（2026-10-01 实测）")
    facts["floor_matrix_pass"] = fact(fp, _mo_cmd("print(mo._floor_stats(%r)[1])" % w64logd), "w64-logs/floor-*.log")
    obp = os.path.join(w64logd, "e2-w64-build.log")
    ot = _read_text(obp)
    if ot:
        m = re.search(_CJK_ARCH_P1 + r"(\d+) " + _CJK_MEMBERS_ALL_W64 + r" wasm64（wasm32=(\d+)）", ot)
        if m:
            facts["w64_ob_lib_wasm64_members"] = fact(int(m.group(1)), _mo_cmd("import re;print(int(re.search(mo._CJK_ARCH_P1+r'(\\d+) '+mo._CJK_MEMBERS_ALL_W64+r' wasm64',open(%r).read()).group(1)))" % obp), "w64-logs/e2-w64-build.log", "w64 车道线程版 OpenBLAS 归档里 wasm64 成员数")
            facts["w64_ob_lib_wasm32_members"] = fact(int(m.group(2)), _py("import re;print(int(re.search(r'wasm32=(\\d+)',open(%r).read()).group(1)))" % obp), "w64-logs/e2-w64-build.log", "必须是 0（side module 的指针宽度必须与主模块一致）")
    _collect_w64_benchmarks(facts, w64logd)
    _collect_native_and_heap(facts, w64logd)
    facts["floor_matrix_fail"] = fact(ff, _mo_cmd("print(mo._floor_stats(%r)[2])" % w64logd), "w64-logs/floor-*.log", "必须 0；含「无 memory64 的引擎必须落 base」这条反向断言（threads 已删）")


def _collect_w64_cand_benchmarks(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    cm, cl, co = _bench3_median(w64logd, "bench-mi2-r%d.log", "matmul 500"), _bench3_median(w64logd, "bench-mi2-r%d.log", "lu 800"), _bench3_median(w64logd, "bench-mi2-r%d.log", "loop 1e6")
    sm, sl = _bench3_median(w64logd, "bench-ship2-r%d.log", "matmul 500"), _bench3_median(w64logd, "bench-ship2-r%d.log", "lu 800")
    if cm is not None:
        facts["w64_cand_matmul500_s"] = fact(cm, _mo_cmd("print(mo._bench3_median(%r,'bench-mi2-r%%d.log','matmul 500'))" % w64logd), "w64-logs/bench-mi2-r1..3.log", "候选（mimalloc，工单 59）产品级 matmul 500²；与现役的同窗配对见 w64_cand_vs_ship_*")
    if cl is not None:
        facts["w64_cand_lu800_s"] = fact(cl, _mo_cmd("print(mo._bench3_median(%r,'bench-mi2-r%%d.log','lu 800'))" % w64logd), "w64-logs/bench-mi2-r1..3.log", "候选（mimalloc）产品级 lu(800)")
    if co is not None:
        facts["w64_cand_loop1e6_s"] = fact(co, _mo_cmd("print(mo._bench3_median(%r,'bench-mi2-r%%d.log','loop 1e6'))" % w64logd), "w64-logs/bench-mi2-r1..3.log", "候选的纯解释器轴（分配器不该动它 —— 诚实记录，防「把好数字全记在头上」）")
    if cm is not None and sm:
        facts["w64_cand_vs_ship_matmul500"] = fact(round(cm / sm, 2), _mo_cmd("print(round(mo._bench3_median(%r,'bench-mi2-r%%d.log','matmul 500')/mo._bench3_median(%r,'bench-ship2-r%%d.log','matmul 500'),2))" % (w64logd, w64logd)), "派生（两组交错日志）", "候选/现役 的 matmul500 比值（<1 = 候选更快；同窗配对，不是跨窗对比）")
    if cl is not None and sl:
        facts["w64_cand_vs_ship_lu800"] = fact(round(cl / sl, 2), _mo_cmd("print(round(mo._bench3_median(%r,'bench-mi2-r%%d.log','lu 800')/mo._bench3_median(%r,'bench-ship2-r%%d.log','lu 800'),2))" % (w64logd, w64logd)), "派生（两组交错日志）", "候选/现役 的 lu800 比值")


def _collect_w64_benchmarks(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    bo = os.path.join(w64logd, "bench-ob-w64.log")
    bs = os.path.join(w64logd, "bench-ship-w64.log")
    ob_m, ob_l = _bench_line(bo, "matmul 500"), _bench_line(bo, "lu 800")
    sh_m = _bench_line(bs, "matmul 500")
    if ob_m is not None:
        facts["w64_ob_matmul500_s"] = fact(ob_m, _mo_cmd("print(mo._bench_line(%r,'matmul 500'))" % bo), "w64-logs/bench-ob-w64.log", "现役 w64（线程版 OpenBLAS NT=8，2026-10-02 上站）的矩阵乘 500² 中位数")
    if ob_l is not None:
        facts["w64_ob_lu800_s"] = fact(ob_l, _mo_cmd("print(mo._bench_line(%r,'lu 800'))" % bo), "w64-logs/bench-ob-w64.log", "现役 w64（线程版 OpenBLAS NT=8）的 lu(800) 中位数")
    if ob_m and sh_m:
        facts["w64_ob_matmul500_speedup"] = fact(round(sh_m / ob_m, 1), _mo_cmd("print(round(mo._bench_line(%r,'matmul 500')/mo._bench_line(%r,'matmul 500'),1))" % (bs, bo)), "派生（两个 bench 日志）", "OpenBLAS 版相对 refblas 版 w64 的加速倍数（历史对照：refblas 的现役地位已由 2026-10-02 NT=8 批取代）")
    _collect_w64_cand_benchmarks(facts, w64logd)


def _collect_heap_ceiling(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    hcp = os.path.join(w64logd, "heap-ceiling.log")
    ht = _read_text(hcp)
    if not ht:
        return
    vals = [float(x) for x in re.findall(_CJK_CEILING + r"=([0-9.]+) GiB", ht)]
    if vals:
        facts["mem_live_ceiling_gib"] = fact(max(vals), _mo_cmd("import re;print(max(float(x) for x in re.findall(mo._CJK_CEILING+r'=([0-9.]+) GiB',open(%r).read())))" % hcp), "w64-logs/heap-ceiling.log", "逐块 0.75 GiB 吃到 OOM 的**存活上限**（四档实测同为 1.49 GiB）")
    m = re.search(r"W64_BIG_HEAP=(yes|no)", ht)
    if m:
        facts["w64_big_heap"] = fact(m.group(1) == "yes", _py("import re;print(re.search(r'W64_BIG_HEAP=(yes|no)',open(%r).read()).group(1)=='yes')" % hcp), "w64-logs/heap-ceiling.log", "工单 31 的结算判据：抬了 MAXIMUM_MEMORY 之后必须变 yes")


def _collect_native_and_heap(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    bo = os.path.join(w64logd, "bench-ob-w64.log")
    ob_m = _bench_line(bo, "matmul 500")
    nbp = os.path.join(w64logd, "native-baseline.json")
    nb = _read_json(nbp)
    if nb is not None:
        _collect_native_entries(facts, nbp, nb, bo, ob_m)
    _collect_heap_ceiling(facts, w64logd)
    spp = os.path.join(w64logd, "speed-w64.log")
    st = _read_text(spp)
    if st:
        for key, case, note in (
            ("w64_matmul500_s", "matmul 500", "w64 档矩阵乘 500²：比 base 慢约 1.2×（i64 指针/索引的代价）"),
            ("w64_lu800_s", "lu 800", "w64 档 lu(800)：比 base 慢约 1.3×"),
        ):
            m = re.search(r"^\s*%s\s+([0-9.]+)s" % re.escape(case), st, re.M)
            if m:
                facts[key] = fact(float(m.group(1)), _mo_cmd("print(mo._bench_line(%r,%r))" % (spp, case)), "w64-logs/speed-w64.log", note)
    dpp = os.path.join(w64logd, "dist-probe-lane.log")
    dt = _read_text(dpp)
    if dt:
        dm = re.search(r"===\s*(\d+) PASS / (\d+) FAIL\s*===", dt)
        if dm:
            facts["dist_lane_probe_pass"] = fact(int(dm.group(1)), _py("import re;print(int(re.search(r'===\\s*(\\d+) PASS / (\\d+) FAIL',open(%r).read()).group(1)))" % dpp), "w64-logs/dist-probe-lane.log", "交付包**内部**的四格选档通过数（不只是字节相同）")
            facts["dist_lane_probe_fail"] = fact(int(dm.group(2)), _py("import re;print(int(re.search(r'===\\s*(\\d+) PASS / (\\d+) FAIL',open(%r).read()).group(2)))" % dpp), "w64-logs/dist-probe-lane.log")


def _collect_native_backend_cases(facts: dict[str, Any], nbp: str, backend_name: str, data: dict[str, Any], cases: tuple[tuple[str, str, str], ...]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    for case, key, note_tpl in cases:
        v = data.get(case, {}).get("s")
        if v is not None:
            facts[key] = fact(v, _py("import json;print(json.load(open(%r))['backends'][%r][%r]['s'])" % (nbp, backend_name, case)), "w64-logs/native-baseline.json", note_tpl % case)


def _collect_native_entries(facts: dict[str, Any], nbp: str, nb: dict[str, Any], bo: str, ob_m: float | None) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    nbob = nb.get("backends", {}).get("openblas24", {})
    nbnet = nb.get("backends", {}).get("netlib", {})
    ob_tpl = "原生天花板（OpenBLAS 0.3.34 pthread）的 %s 中位数"
    net_tpl = "netlib 参考实现的 %s（用户手里的原生 Octave）"
    _collect_native_backend_cases(facts, nbp, "openblas24", nbob, (
        ("matmul500", "native_openblas_matmul500_s", ob_tpl),
        ("matmul1024", "native_openblas_matmul1024_s", ob_tpl),
        ("matmul2000", "native_openblas_matmul2000_s", ob_tpl),
        ("lu800", "native_openblas_lu800_s", ob_tpl),
        ("matmul1000", "native_openblas_matmul1000_s", ob_tpl),
        ("lu1500", "native_openblas_lu1500_s", ob_tpl),
    ))
    vn = nbnet.get("matmul500", {}).get("s")
    if vn is not None:
        facts["native_netlib_matmul500_s"] = fact(vn, _py("import json;print(json.load(open(%r))['backends']['netlib']['matmul500']['s'])" % nbp), "w64-logs/native-baseline.json", "系统默认 BLAS（netlib 参考实现，单线程）的 matmul 500² —— 用户手里的原生 Octave")
    _collect_native_backend_cases(facts, nbp, "netlib", nbnet, (
        ("matmul1000", "native_netlib_matmul1000_s", net_tpl),
        ("lu1500", "native_netlib_lu1500_s", net_tpl),
        ("lu800", "native_netlib_lu800_s", net_tpl),
        ("loop1e6", "native_netlib_loop1e6_s", net_tpl),
    ))
    if nbob.get("threads") is not None:
        facts["native_openblas_threads"] = fact(nbob["threads"], _py("import json;print(json.load(open(%r))['backends']['openblas24']['threads'])" % nbp), "w64-logs/native-baseline.json", "天花板后端的线程数（占比口径的一部分，必须如实记录）")
    _collect_native_ratios(facts, nbp, nbob, nbnet, bo, ob_m, vn)


def _collect_native_ratios(facts: dict[str, Any], nbp: str, nbob: dict[str, Any], nbnet: dict[str, Any], bo: str, ob_m: float | None, vn: float | None) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    if ob_m and nbob.get("matmul500", {}).get("s"):
        facts["w64_ob_matmul500_native_ratio"] = fact(round(nbob["matmul500"]["s"] / ob_m, 2), _mo_cmd("import json;print(round(json.load(open(%r))['backends']['openblas24']['matmul500']['s']/mo._bench_line(%r,'matmul 500'),2))" % (nbp, bo)), "派生（原生基线 ÷ 浏览器）", "浏览器 w64 占原生天花板的比值（占比仪表盘的表头）")
    if ob_m and vn:
        facts["w64_ob_matmul500_vs_netlib"] = fact(round(vn / ob_m, 1), _mo_cmd("import json;print(round(json.load(open(%r))['backends']['netlib']['matmul500']['s']/mo._bench_line(%r,'matmul 500'),1))" % (nbp, bo)), "派生（原生基线 ÷ 浏览器）", "浏览器 w64 相对『系统默认 BLAS 的原生 Octave』的倍数")
    w1000, w1500, wloop = _bench_line(bo, "matmul 1000"), _bench_line(bo, "lu 1500"), _bench_line(bo, "loop 1e6")
    obm1000, nl1000, nl1500, nlloop = nbob.get("matmul1000", {}).get("s"), nbnet.get("matmul1000", {}).get("s"), nbnet.get("lu1500", {}).get("s"), nbnet.get("loop1e6", {}).get("s")
    if w1000 and obm1000:
        facts["w64_ob_matmul1000_native_ratio"] = fact(round(obm1000 / w1000, 2), _mo_cmd("import json;print(round(json.load(open(%r))['backends']['openblas24']['matmul1000']['s']/mo._bench_line(%r,'matmul 1000'),2))" % (nbp, bo)), "派生（原生基线 ÷ 浏览器）", "浏览器 w64 matmul1000 占原生天花板的比值（大矩阵是最吃线程的刻度）")
    if w1000 and nl1000:
        facts["w64_vs_netlib_matmul1000"] = fact(round(nl1000 / w1000, 1), _mo_cmd("import json;print(round(json.load(open(%r))['backends']['netlib']['matmul1000']['s']/mo._bench_line(%r,'matmul 1000'),1))" % (nbp, bo)), "派生（原生基线 ÷ 浏览器）", "浏览器 w64 matmul1000 相对『用户手里的原生 Octave』的倍数")
    if w1500 and nl1500:
        facts["w64_vs_netlib_lu1500"] = fact(round(nl1500 / w1500, 1), _mo_cmd("import json;print(round(json.load(open(%r))['backends']['netlib']['lu1500']['s']/mo._bench_line(%r,'lu 1500'),1))" % (nbp, bo)), "派生（原生基线 ÷ 浏览器）", "浏览器 w64 lu1500 相对『用户手里的原生 Octave』的倍数")
    if wloop and nlloop:
        facts["w64_vs_netlib_loop1e6"] = fact(round(nlloop / wloop, 2), _mo_cmd("import json;print(round(json.load(open(%r))['backends']['netlib']['loop1e6']['s']/mo._bench_line(%r,'loop 1e6'),2))" % (nbp, bo)), "派生（原生基线 ÷ 浏览器）", "浏览器解释器循环相对原生的比值（<1 = 浏览器慢 —— 纯解释器轴是唯一明确输的）")


def _collect_6012_and_webgpu(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    lane_ok = 0
    for t, mode in (("ip", "w64"), ("master", "w64"), ("wasm32", "product")):
        cp = os.path.join(w64logd, "lane6012-%s.verdict" % t)
        v = _read_text(cp)
        if v is not None:
            val = v.strip()
            facts["lane6012_%s_verdict" % t] = fact(val, "cat %s" % cp, "w64-logs/lane6012-%s.verdict" % t, "6.0.12 重链产物 verdict（%s 模式；只有 ok 可部署）" % mode)
            lane_ok += 1 if val == "ok" else 0
    if lane_ok:
        facts["lane6012_ok_lines"] = fact(lane_ok, "grep -l '^ok$' /mnt/hdd/octave-wasm-build/w64-logs/lane6012-*.verdict | wc -l", "w64-logs/lane6012-*.verdict", "三线中 verdict==ok 的条数（0 = 一条没成 ⇒ 那比「部分成功」更该红）")
    wg = os.path.join(w64logd, "probe-webgpu-capability.json")
    d = _read_json(wg)
    if d:
        m, w, hw = d.get("main", {}), d.get("worker", {}), d.get("hw", {})
        facts["webgpu_main_device"] = fact(m.get("device"), _py("import json;print(json.load(open('%s'))['main']['device'])" % wg), "w64-logs/probe-webgpu-capability.json", "主线程 WebGPU 能否拿到 device（前提：安全上下文；**about:blank 探不出**）")
        facts["webgpu_worker_device"] = fact(w.get("device"), _py("import json;print(json.load(open('%s'))['worker']['device'])" % wg), "w64-logs/probe-webgpu-capability.json", "**Worker 内**（DOM-free）能否拿到 WebGPU device —— 算力放 Worker 的前提")
        facts["webgpu_worker_compute_ok"] = fact(bool(w.get("computeOK")), _py("import json;print(json.load(open('%s'))['worker']['computeOK'])" % wg), "w64-logs/probe-webgpu-capability.json", "Worker 里**真跑 compute shader**并读回 [2,2,2,2]（不是只看 typeof）")
        facts["webgpu_worker_webgl2"] = fact(bool(w.get("webgl2")), _py("import json;print(json.load(open('%s'))['worker']['webgl2'])" % wg), "w64-logs/probe-webgpu-capability.json", "Worker 内 OffscreenCanvas+webgl2 可用（渲染不依赖 DOM）")
        facts["hw_apis_available"] = fact(sum(1 for k in ("serial", "usb", "hid") if hw.get(k)), _py("import json;d=json.load(open('%s'))['hw'];print(sum(1 for k in ('serial','usb','hid') if d.get(k)))" % wg), "w64-logs/probe-webgpu-capability.json", "网页原生硬件接口可用数（WebSerial/USB/HID）—— MATLAB 要装驱动，这里是浏览器 API")
        facts["webgpu_vendor"] = fact(m.get("vendor"), _py("import json;print(json.load(open('%s'))['main']['vendor'])" % wg), "w64-logs/probe-webgpu-capability.json", "实测 GPU 厂商（WebGPU **不挑厂商**：NVIDIA/AMD/Intel/Apple 同 API）")


def _collect_sympy_and_pyodide(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    sym = os.path.join(w64logd, "probe-pyodide-sympy.json")
    sd = _read_json(sym)
    if sd:
        ms = {m.get("tag"): (m.get("result") or {}) for m in sd.get("modes", [])}
        coi, no, brk = ms.get("coi=true breakSympy=false", {}), ms.get("coi=false breakSympy=false", {}), ms.get("coi=true breakSympy=true", {})
        facts["sympy_pyodide_ok"] = fact(bool(coi.get("ok")), _py("import json;print(json.load(open('%s'))['modes'][0]['result']['ok'])" % sym), "w64-logs/probe-pyodide-sympy.json", "Pyodide+SymPy 在 **COI** Worker 里起得来（符号计算路线的前提）")
        facts["sympy_pyodide_diff"] = fact(coi.get("diff"), _py("import json;print(json.load(open('%s'))['modes'][0]['result']['diff'])" % sym), "w64-logs/probe-pyodide-sympy.json", "**真算对**：`diff(sin(x),x)` 的符号结果（判据 = 恰好 `cos(x)`）")
        facts["sympy_pyodide_nocoi_ok"] = fact(bool(no.get("ok")) and no.get("diff") == "cos(x)", _py("import json;d=json.load(open('%s'))['modes'][1]['result'];print(bool(d.get('ok')) and d.get('diff')=='cos(x)')" % sym), "w64-logs/probe-pyodide-sympy.json", "**无 COI**（发不了 COOP/COEP 的宿主）同样算对 ⇒ 基础档用户也有份")
        facts["sympy_pyodide_break_fails_loud"] = fact(brk.get("ok") is False, _py("import json;print(json.load(open('%s'))['modes'][2]['result']['ok'] is False)" % sym), "w64-logs/probe-pyodide-sympy.json", "反向断言：拿掉 SymPy 轮子 ⇒ 装载**响亮失败**（`ok` 必须为 False，不许静默）")
        dd = (sd.get("bytes") or {}).get("disk") or {}
        if dd:
            facts["sympy_assets_bytes"] = fact(dd.get("coreTar"), _py("import json;print(json.load(open('%s'))['bytes']['disk']['coreTar'])" % sym), "w64-logs/probe-pyodide-sympy.json", "Pyodide core 压缩包字节（符号计算路线**站点新增交付**的下限口径）")
    _collect_sympy_pyc(facts, w64logd)
    _collect_sympy_perf(facts, w64logd)
    _collect_symbolic_seam(facts, w64logd)


def _collect_sympy_pyc(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    pyc = os.path.join(w64logd, "sympy-pyc-ab.json")
    s = (_read_json(pyc) or {}).get("summary", {})
    if not s.get("importA_ms"):
        return
    facts["sympy_import_ms_source"] = fact(s.get("importA_ms"), _py("import json;print(json.load(open('%s'))['summary']['importA_ms'])" % pyc), "w64-logs/sympy-pyc-ab.json", "`import sympy` 耗时（**源码轮子**档；编译次数见 sympy_pyc_compile_calls）")
    facts["sympy_import_ms_pyc"] = fact(s.get("importB_ms"), _py("import json;print(json.load(open('%s'))['summary']['importB_ms'])" % pyc), "w64-logs/sympy-pyc-ab.json", "`import sympy` 耗时（**.pyc 轮子**档，唯一变量 = 轮子里有没有 `__pycache__`）")
    facts["sympy_pyc_speedup"] = fact(s.get("speedup"), _py("import json;print(json.load(open('%s'))['summary']['speedup'])" % pyc), "w64-logs/sympy-pyc-ab.json", "派生：A÷B（>1 = 预编译更快 —— 用户问「能快几倍」的直接答案）")
    stc = s.get("sourceToCode", {})
    facts["sympy_pyc_compile_calls"] = fact(stc.get("B"), _py("import json;print(json.load(open('%s'))['summary']['sourceToCode']['B'])" % pyc), "w64-logs/sympy-pyc-ab.json", ".pyc 档的源码→字节码编译次数（**必须 ≈0**；不为 0 则 A/B 无效 ⇒ 探针 rc=2）")
    if stc.get("A") is not None:
        facts["sympy_pyc_compile_calls_source"] = fact(stc.get("A"), _py("import json;print(json.load(open('%s'))['summary']['sourceToCode']['A'])" % pyc), "w64-logs/sympy-pyc-ab.json", "**源码轮子**档的源码→字节码编译次数（冷启动固定成本；.pyc 档是 sympy_pyc_compile_calls=[[sympy_pyc_compile_calls]]）")
    by = s.get("bytes", {})
    if by:
        facts["sympy_pyc_bytes_ratio"] = fact(round(by.get("B", 0) / max(by.get("A", 1), 1), 2), _py("import json;d=json.load(open('%s'))['summary']['bytes'];print(round(d['B']/d['A'],2))" % pyc), "w64-logs/sympy-pyc-ab.json", "交付字节代价：.pyc 轮子 ÷ 源码轮子（**速度不是免费的**）")


def _geo_ratio(a_ops: dict[str, Any], b_ops: dict[str, Any], floor: float = 0.5) -> float | None:
    rs = [a_ops[k]["min_ms"] / b_ops[k]["min_ms"] for k in a_ops if k in b_ops and b_ops[k]["min_ms"] > floor]
    return math.exp(sum(math.log(x) for x in rs) / len(rs)) if rs else None


def _collect_sympy_perf(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    perf, nat, perfp = os.path.join(w64logd, "sympy-perf-pyodide.json"), os.path.join(w64logd, "sympy-perf-native.json"), os.path.join(w64logd, "sympy-perf-pyodide-pyc.json")
    pd, nd = _read_json(perf), _read_json(nat)
    if pd and nd:
        geo = _geo_ratio((pd.get("bench") or {}).get("ops", {}), (nd.get("bench") or {}).get("ops", {}))
        if geo:
            facts["sympy_perf_pyodide_over_native"] = fact(round(geo, 2), _mo_cmd("import json;print(round(mo._geo_ratio(json.load(open(%r))['bench']['ops'],json.load(open(%r))['bench']['ops']),2))" % (perf, nat)), "w64-logs/sympy-perf-{native,pyodide}.json", "**用户定论之问**：Pyodide ÷ 原生 CPython 的 CAS 几何均值（≈2× ⇒ 判『接近』）")
            tm = pd.get("timings") or {}
            facts["sympy_perf_cold_start_ms"] = fact(round(tm.get("load", 0) + tm.get("pkg", 0)), _py("import json;d=json.load(open('%s'))['timings'];print(round(d['load']+d['pkg']))" % perf), "w64-logs/sympy-perf-pyodide.json", "浏览器侧**冷启动**（Pyodide 装载 + 装 sympy 包）—— 与稳态倍数分开读")
    pfd = _read_json(perfp)
    if pd and pfd:
        a, b = pd.get("bench") or {}, pfd.get("bench") or {}
        sp = a.get("import_s", 0) / max(b.get("import_s", 0), 1e-9) if a.get("import_s") else None
        cold = [a["cold_ms"][k] / max(b["cold_ms"][k], 1e-9) for k in a.get("cold_ms", {}) if k in b.get("cold_ms", {})]
        cg = math.exp(sum(math.log(x) for x in cold) / len(cold)) if cold else None
        sg = _geo_ratio(a.get("ops", {}), b.get("ops", {}))
        if sp:
            facts["sympy_pyc_import_speedup_pyodide"] = fact(round(sp, 2), _py("import json;a=json.load(open(%r))['bench'];b=json.load(open(%r))['bench'];print(round(a['import_s']/max(b['import_s'],1e-9),2))" % (perf, perfp)), "w64-logs/sympy-perf-pyodide{,-pyc}.json", "**用户追加之问**：.pyc 轮子的 `import sympy` 加速（浏览器侧，同一份基准）")
            facts["sympy_pyc_cold_geo_speedup"] = fact(round(cg, 2) if cg else None, _py("import json,math;a=json.load(open(%r))['bench']['cold_ms'];b=json.load(open(%r))['bench']['cold_ms'];c=[a[k]/max(b[k],1e-9) for k in a if k in b];print(round(math.exp(sum(math.log(x) for x in c)/len(c)),2))" % (perf, perfp)), "w64-logs/sympy-perf-pyodide{,-pyc}.json", "每 op **首次调用**的几何均值加速（惰性子模块加载那段 —— 用户体感）")
            facts["sympy_pyc_steady_geo_ratio"] = fact(round(sg, 2) if sg else None, _mo_cmd("import json;print(round(mo._geo_ratio(json.load(open(%r))['bench']['ops'],json.load(open(%r))['bench']['ops']),2))" % (perf, perfp)), "w64-logs/sympy-perf-pyodide{,-pyc}.json", "**稳态对照**：≈1.0 = 如预期 .pyc 不改执行（预编译不是万能药）")


def _collect_symbolic_seam(facts: dict[str, Any], w64logd: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    syncp = os.path.join(w64logd, "probe-pyodide-sync.json")
    sd = _read_json(syncp)
    if sd:
        facts["pyodide_sync_probe_pass"] = fact(sd.get("pass"), _py("import json;print(json.load(open('%s'))['pass'])" % syncp), "w64-logs/probe-pyodide-sync.json", "**前提实测**：wasm 里的 C 同步调 Pyodide（4 条：装载/版本/真算对/耗时）")
        facts["pyodide_sync_ready_ms"] = fact((sd.get("result") or {}).get("pyodideReadyMs"), _py("import json;print(json.load(open('%s'))['result']['pyodideReadyMs'])" % syncp), "w64-logs/probe-pyodide-sync.json", "Pyodide+sympy 冷启动（必须在 wasm 启动**之前**完成 —— 同步调用等不了 Promise）")
    seam = os.path.join(w64logd, "accept-symbolic-seam.log")
    txt = _read_text(seam)
    if txt:
        m2 = re.findall(r"=== (\d+) PASS / (\d+) FAIL ===", txt)
        if m2:
            facts["symbolic_seam_pass"] = fact(int(m2[-1][0]), "awk '/=== [0-9]+ PASS/{p=$2} END{print p}' %s" % seam, "w64-logs/accept-symbolic-seam.log", "★ **符号计算端到端**：`diff(sin(x),x)`=cos(x) + 类型往返 + 两条反向（真浏览器）")
            facts["symbolic_seam_fail"] = fact(int(m2[-1][1]), "awk '/=== [0-9]+ PASS/{f=$5} END{print f}' %s" % seam, "w64-logs/accept-symbolic-seam.log", "同上（**必须 0** —— 这条接缝的判据是「真算对」）")


def _collect_manual_and_release_facts(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    w64log = "/mnt/hdd/octave-wasm-build/w64-logs/cache-bytes-20261031.log"
    w64txt = _read_text(w64log)
    if w64txt:
        for tag, key in (("first", "cache_first_bytes"), ("second", "cache_reload_bytes")):
            mm = re.search(tag + r"=(\d+)", w64txt)
            if mm:
                facts[key] = fact(int(mm.group(1)), "grep -oP '%s=\\K[0-9]+' %s" % (tag, w64log), w64log, "HTTP 缓存三态实测（%s 次传输字节）" % tag)
    pyd = "/mnt/hdd/octave-wasm-build/site/assets/pyodide/pyodide"
    pyd_files = ["pyodide.asm.wasm", "pyodide.asm.mjs", "python_stdlib.zip", "sympy-1.14.0-py3-none-any.whl", "mpmath-1.4.1-py3-none-any.whl", "pyodide.js", "pyodide.mjs", "python_cli_entry.mjs"]
    if all(os.path.exists(os.path.join(pyd, f)) for f in pyd_files):
        facts["pyodide_min_closure_bytes"] = fact(sum(os.path.getsize(os.path.join(pyd, f)) for f in pyd_files), _py("import os;d='%s';print(sum(os.path.getsize(d+'/'+f) for f in %r))" % (pyd, pyd_files)), "site/assets/pyodide/pyodide/", "Pyodide 最小闭包（symbolic 必需 8 件之和）")
    for key, path, note in (
        ("web_pause_oct_bytes", "/mnt/hdd/octave-wasm-build/site/assets/oct/__web_pause_ms__.oct", "symbolic 接缝要 vendor 的第二件（导出 __web_run_js__ 等 6 个兄弟别名）"),
        ("webshims_js_bytes", "/mnt/hdd/octave-wasm-build/site/assets/m/webshims.js", "symbolic 接缝要 vendor 的第一件（11 个 .m 的自包含 JS 包，bundle-m 产出）"),
    ):
        if os.path.exists(path):
            facts[key] = fact(os.path.getsize(path), "stat -c%%s %s" % path, path.replace("/mnt/hdd/octave-wasm-build/", ""), note)
    _collect_release_e2e(facts)


def _collect_release_e2e(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    brdir = "/mnt/hdd/octave-wasm-build/release-br-e2e"
    brman_p = os.path.join(brdir, "manifest.json")
    man = _read_json(brman_p)
    if man is not None:
        br_entries = [e for e in man.get("entries", []) if any(v.get("codec") == "br" for v in e.get("variants", []))]
        facts["release_br_entries"] = fact(len(br_entries), _py("import json;m=json.load(open('%s'));print(len([e for e in m['entries'] if any(v['codec']=='br' for v in e['variants'])]))" % brman_p), "release-br-e2e/manifest.json", "release 载荷里带 br 变体的 entry 数（065 矩阵：≥1MB 必出；3 个 octave.js <1MB 不出）")
        if man.get("codecs"):
            facts["release_codecs"] = fact(",".join(man["codecs"]), _py("import json;m=json.load(open('%s'));print(','.join(m['codecs']))" % brman_p), "release-br-e2e/manifest.json", "manifest codecs 词表（V9 开放词表；identity 恒末位 V4）")
        tot_gz = sum(c["bytes"] for e in man.get("entries", []) for v in e.get("variants", []) if v.get("codec") == "gzip" for c in v.get("chunks", []))
        tot_br = sum(c["bytes"] for e in br_entries for v in e.get("variants", []) if v.get("codec") == "br" for c in v.get("chunks", []))
        if tot_gz and tot_br:
            facts["release_br_vs_gz_saving_pct"] = fact(round((1 - tot_br / tot_gz) * 100, 1), _py("import json;m=json.load(open('%s'));e=m['entries'];gz=sum(c['bytes'] for x in e for v in x['variants'] if v['codec']=='gzip' for c in v['chunks']);br=sum(c['bytes'] for x in e for v in x['variants'] if v['codec']=='br' for c in v['chunks']);print(round((1-br/gz)*100,1))" % brman_p), "release-br-e2e/manifest.json", "br(q11) 相对 gzip-9 的字节节省（全部大件合计；065 信预测 35% 量级，实测 30.6%）")
    _collect_validator_and_v011(facts, brdir)


def _collect_validator_and_v011(facts: dict[str, Any], brdir: str) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    brv = _read_text(os.path.join(brdir, "validate.log"))
    m_br = re.search(r"=== (\d+) PASS / (\d+) FAIL ===", brv or "")
    if m_br and int(m_br.group(2)) == 0:
        facts["release_br_validator_pass"] = fact(int(m_br.group(1)), "awk '/PASS \\/ 0 FAIL/{print $2}' %s/validate.log | tail -1" % brdir, "release-br-e2e/validate.log", "契约方校验器对含 br 的真产物对盘核验 PASS 数（FAIL 必须 0）")
    mr = _selftest_pass_count(os.path.join(REPO, "build", "make-release.py"))
    if mr is not None:
        cmd_mr = "python3 build/make-release.py --selftest | tail -1 | grep -oE '[0-9]+ PASS / 0 fail' | grep -oE '^[0-9]+'"
        facts["make_release_selftest_pass"] = fact(mr, cmd_mr, "build/make-release.py", "release 生成器自证 PASS 数（含 br 阈值正反用例；缺编码器/verdict≠ok 必报）")
        facts["release_lanes_selftest_pass"] = fact(mr, cmd_mr, "build/make-release.py", "生成器自证总 PASS 数（071 部分：四类反例 + 两条从产物读回的判据）")
    ladir, rlre = "/mnt/hdd/octave-wasm-build/release-lanes-e2e", "/mnt/hdd/octave-wasm-build/release-v011-readback"
    for pfx, d, key, note in (
        ("release_lanes_declared", ladir, "release_lanes_validator_pass", "manifest 顶层 lanes 声明的引擎车道数（071：身份与投送坐标分家；0 = 投影丢了）"),
        ("release_lanes_published", rlre, "release_lanes_published_validator_pass", "已发布 v0.1.1 的 manifest.lanes 引擎车道数（反读自 GitHub，非本地生成）"),
    ):
        man = _read_json(os.path.join(d, "manifest.json"))
        if man is not None:
            facts[pfx] = fact(len(man.get("lanes") or {}), _py("import json;m=json.load(open('%s/manifest.json'));print(len(m.get('lanes') or {}))" % d), "%s/manifest.json" % os.path.basename(d), note)
        vtxt = _read_text(os.path.join(d, "validate.log"))
        vm = re.search(r"=== (\d+) PASS / (\d+) FAIL ===", vtxt or "")
        if vm and int(vm.group(2)) == 0:
            facts[key] = fact(int(vm.group(1)), "awk '/PASS \\/ 0 FAIL/{print $2}' %s/validate.log | tail -1" % d, "%s/validate.log" % os.path.basename(d), "校验 PASS 数（FAIL 必须 0）")
    _collect_v011_sweep(facts)


def _collect_v011_sweep(facts: dict[str, Any]) -> None:
    """PINNED: Ledger notes and cmd descriptions are structured FACTS.json data."""
    v11 = "/mnt/hdd/octave-wasm-build/sweep-logs/20261112-073819.sweep.out"
    vtxt = _read_text(v11)
    if vtxt:
        m = re.search(_CJK_TOTAL_PREFIX + r"(\d+) " + _CJK_SUITE_SUFFIX + r" / (\d+) PASS / (\d+) FAIL", vtxt)
        if m:
            facts["v011_sweep_suites"] = fact(int(m.group(1)), "grep -oE '合计：[0-9]+ 套' %s | grep -oE '[0-9]+'" % v11, "sweep-logs/20261112-073819.sweep.out", "v0.1.1 站点（8769）PROBES=1 全量的套数（对应 20261101 全量 97 套的 8761 形态）")
            facts["v011_sweep_pass"] = fact(int(m.group(2)), "grep -oE '合计：.*PASS' %s | grep -oE '[0-9]+ PASS' | grep -oE '^[0-9]+'" % v11, "sweep-logs/20261112-073819.sweep.out", "v0.1.1 全量 PASS 合计（FAIL 必须 0）")
            facts["v011_sweep_fail"] = fact(int(m.group(3)), "grep -oE '合计：[0-9]+ 套 / [0-9]+ PASS / [0-9]+ FAIL' %s | grep -oE '[0-9]+ FAIL' | grep -oE '^[0-9]+' | tail -1" % v11, "sweep-logs/20261112-073819.sweep.out", "v0.1.1 全量 FAIL 合计（必须 0；三个 NO-SUMMARY 是环境缺件，补跑单套另计）")
    for key, path, note in (
        ("v011_reprobe_matrix", "/tmp/pbm-v011.log", "补跑 probe-browser-matrix（8761；sweep 时因 8761 死而 NO-SUMMARY；5 PASS/0 FAIL）"),
        ("v011_reprobe_wasm32_nocoi", "/tmp/p32-v011.log", "补跑 probe-wasm32-no-coi（SITE=site-v011 产物树；sweep 未注入 SITE 故 NO-SUMMARY；5 PASS/0 FAIL）"),
        ("v011_reprobe_toolchain_gap", "/tmp/ptg-v011.log", "补跑 probe-toolchain-gap（夹具 /tmp/p-throw.oct 按工单 65 配方现编；2 PASS/0 FAIL，两条缺口均已修）"),
    ):
        v = _probe_sum(path)
        if v is not None:
            facts[key] = fact(v, "tail -2 %s | grep -oE '=== [0-9]+ PASS / 0 FAIL ===' | grep -oE '[0-9]+' | tail -1" % path, path.replace("/tmp/", "tmp/"), note)


def measure() -> dict[str, Any]:
    """Measure all host facts; guards and persistence live in `zreflect/facts.py`."""
    facts: dict[str, Any] = {}
    _collect_manifest_and_site(facts)
    _collect_site_artifacts(facts)
    _collect_headers_and_env(facts)
    _collect_sweeps_and_oct(facts)
    _collect_probe_lane_and_e2(facts)
    _collect_w64_lane(facts)
    _collect_hotpath_and_rust(facts)
    _collect_sort_and_ip(facts)
    _collect_locale_xpow_hotpath3(facts)
    _collect_cand_sha_emcc_pins(facts)
    _collect_forge_shelf_and_catalog(facts)
    w64logd = _collect_libm_and_w64_logs(facts)
    _collect_floor_and_openblas(facts, w64logd)
    _collect_6012_and_webgpu(facts, w64logd)
    _collect_sympy_and_pyodide(facts, w64logd)
    _collect_manual_and_release_facts(facts)
    return facts


def _selftest() -> int:
    """Run fast in-process self-tests for helper parsers and fact() shape."""
    import tempfile  # noqa: PLC0415

    cases: list[tuple[str, bool]] = []
    f_ok = fact(42, "echo 42", "src", "note")
    cases.append((
        "measure_octave.fact_shape",
        f_ok.get("value") == 42
        and f_ok.get("cmd") == "echo 42"
        and f_ok.get("source") == "src"
        and f_ok.get("note") == "note",
    ))
    cases.append((
        "measure_octave.probe_sum_missing_is_none",
        _probe_sum("/nonexistent/probe_missing.log") is None,
    ))
    with tempfile.TemporaryDirectory() as tmp:
        p_ok = os.path.join(tmp, "ok.py")
        p_fail = os.path.join(tmp, "fail.py")
        with open(p_ok, "w", encoding="utf-8") as fh:
            fh.write("print('=== 3 PASS / 0 fail ===')\n")
        with open(p_fail, "w", encoding="utf-8") as fh:
            fh.write("import sys\nprint('=== 2 PASS / 1 fail ===')\nsys.exit(1)\n")
        cases.append(("measure_octave.selftest_pass_count_ok", _selftest_pass_count(p_ok) == 3))
        cases.append(("measure_octave.selftest_pass_count_fail_none", _selftest_pass_count(p_fail) is None))
    bad = 0
    for label, passed in cases:
        print(f"{'PASS' if passed else 'FAIL'} | {label}")
        if not passed:
            bad += 1
    print(f"=== {len(cases) - bad} PASS / {bad} FAIL ===")
    return 1 if bad else 0


if __name__ == "__main__":
    _rc = activate_or_fatal()
    if _rc:
        sys.exit(_rc)
    if "--selftest" in sys.argv[1:]:
        sys.exit(_selftest())
    print(json.dumps(measure(), ensure_ascii=False, indent=1))
