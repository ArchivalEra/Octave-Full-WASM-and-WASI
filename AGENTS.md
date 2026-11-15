# AGENTS.md · Octave-Full-Wasm

Operating contract for agents working in this repository. It contains only
behavioral rules, hard constraints, and path definitions. Explanations,
incident narratives, and history live in `HISTORY.md`; current state lives in
`STATE.md`; terminology lives in `CONTEXT.md`. If this file disagrees with a
script's behavior, trust the script, then fix this file.

## Absolute rules

1. **Client-side only.** Octave always runs in browser wasm. No endpoint that
   executes code server-side, ever.
2. **No history rewriting.** No force-push, no deleting git objects, no
   rewriting history, no `--no-verify`.
3. **The course repo `/mnt/hdd/zcode-projects/GONGCHENGSHUXUE20260917` is
   read-only except its `mail/`.** Delivering a letter = adding a file to its
   `mail/` (never committing to it, never pushing it). Everything else in that
   repository is untouchable.
4. **Push discipline (final ruling).** The write path works via SSH SK key
   signed through the akr FIDO2 agent with phone-based MFA approval, over the
   `github-ArchivalEra` SSH alias (locked to the ArchivalEra SK key); both gh
   tokens are read-only and HTTPS push returns 403. The origin remote is split
   into two URLs: **fetch = HTTPS** (`https://github.com/ArchivalEra/
   Octave-Full-Wasm.git`, silent via the read-only PAT), **push = SSH alias**
   — any `ssh://` fetch URL triggers a phone approval on every `git fetch`
   and is forbidden. Reads are split by tool: accounting and queries go
   through the gh CLI (`gh api`, `gh repo view` — read-only PATs cover the
   whole account-visible surface); actually fetching objects falls back to
   plain `git fetch` over HTTPS (the split remote handles this; `gh repo
   sync` requires write access and must not be used). Everyday `git fetch` /
   `git pull` therefore need zero approvals; only push rings the phone.
   Push requests and review conclusions never go through wo-u: write the
   change summary and the code-review conclusion into your session's final
   output (and into the commit message), then stop outputting and wait for the
   maintainer's approval before pushing. The push itself is the gate;
   undocumented pushes are ignored.

   ```sh
   # push recipe for this repo (proxy is mandatory; direct:22/443 time out)
   # NOTE: zreflect/lang/{zh,en,de}/knobs.json match the vendored mechanism layer
   # (they differ from upstream's newer packs by design; sync them only when the
   # vendored zreflect/ itself is upgraded, as one batch).
   export https_proxy=http://127.0.0.1:2080 http_proxy=http://127.0.0.1:2080
   . reflect-hooks/Einfacht.env                  # local gate knobs
   python3 zreflect/registry.py --run commit     # gates must be green first
   git push ssh://git@github-ArchivalEra/ArchivalEra/Octave-Full-Wasm.git master
   ```

## Paths

| Path | What it is |
|---|---|
| `/mnt/hdd/zcode-projects/Octave-Full-Wasm` | the only writable git repo |
| `/mnt/hdd/octave-wasm-build/` | sites, artifacts, logs, mirror repos (not git; writable) |
| `/mnt/hdd/crossbuild-tools/` | one-off toolchains, playwright browsers |
| docker container `o113` | build environment for the 11.3.0 lane |

## Three products, one trunk

| Product | Arch | Constraint |
|---|---|---|
| `wasm32` (`product` mode) | wasm32, single-thread | none — the only line without COI |
| `wasm64std` (`w64-std` mode) | wasm64, multi-thread | requires COI + threads |
| `wasm64ip` (`w64` mode) | wasm64, multi-thread + Rust sort kernel | requires COI |

Lane gating is decided by exactly two things: whether a user can run it
(browser support / COI), and whether it ships as non-free software. Never by
performance. "Non-free" here is a maintenance-world term — upstream does not
accept the Rust patch — **not a licence term**: all artifacts are
AGPL-3.0-or-later (`docs/RUST-SORT-KERNEL-LICENSE.md`). The site shows two
cells, `base` (wasm32) and `w64` (wasm64). `threads` and `w64-base` are dead
lanes: their appearance anywhere is a defect (machine-checked by
`build/113/check-lane-purity.py`). New experiments go on new branches; never
add cells to the site.

## Fact discipline

Every "this is now true" claim must be provable by a rerunnable command.

1. **Numbers come from the ledger only.** `build/FACTS.json` (each key carries
   its `cmd`). Documents reference numbers as `[[key]]`; hand-copying numbers
   into prose is rejected by `check_facts.py`.
2. **"It compiles" ≠ "it works".** Anything touching runtime behavior (GL,
   fonts, load paths, assets) must be verified in a real browser. A green build
   plus green artifact self-checks is not acceptance.
3. **Assertions must be falsifiable.** Every gate carries `--selftest` with all
   three case classes: normal input passes, violations must fail, empty input
   must fail. A gate that cannot be shown red is not a gate.
4. **Inference and measurement stay separate.** Inference goes to
   `build/113/NOTES-*.md` naming the experiment that would settle it;
   overturned claims go to `build/lib/retractions.json` (the gate fails when
   they reappear).

## Acceptance floor

`http://127.0.0.1:8761/` always serves the last browser-verified build. A
failed experiment must never degrade it. Batches that change the artifact,
thread count, GL, or assets run the full sweep (`PROBES=1`) before promotion;
numeric suites alone do not qualify.

Promotion goes only through the governed scripts
(`promote-pages.sh` / `promote-webgl.sh` / `promote-w64-lane.sh`, chosen by
batch type). Experiments write only `siteWebGL/`. Before delivery, run:

```bash
sudo -E $(which python3) build/lib/doctor.py      # must print ok
sh build/sweep.sh http://127.0.0.1:8768/          # experiment site green first
sh build/promote-pages.sh                         # or promote-webgl / promote-w64-lane
sh build/check-boot.sh http://127.0.0.1:8761/     # or stop here
sh build/check-deploy-sha.sh <site> <sha> <URL>   # disk / HTTP / page three-layer
sh build/sweep.sh http://127.0.0.1:8761/          # once plain, once PROBES=1
sh build/check-site-parity.sh --strict            # 8761 / 8768 / repo site/ agree
```

## Mail boundary

Cross-agent mail is inbox-based:

1. Deliver to the **recipient's** `mail/` (never leave letters in your own).
2. Read **only your own** `mail/`.
3. This repo's inbox is guarded by `.githooks/check-mail-boundary.py`:
   `**To:**` must name this repo. External consumers follow the same rules once
   they have a `mail/` inbox. `/mnt/hdd/octave-wasm-build/outbox/` is the
   fallback for recipients without one.

## Before committing

The only executor is
`. reflect-hooks/Einfacht.env && python3 zreflect/registry.py --run commit`
(knobs are mandatory; `check_facts.py` also blocks bare numbers, block/ledger
mismatches, and bad references). Then prove every gate can fail:
`sh gates-selftest.sh && sh build/gates-selftest.sh`. "All green" must not
count skipped gates — `off` means untested.

## Silently failing pitfalls

- **Never use `sleep`.** The harness kills foreground `sleep` at its budget and
  backgrounded it elsewhere; long jobs go to `run_in_background: true`, and an
  already-backgrounded job is never re-run.
- **Scripts inside the container are a copy.** After editing repo scripts or
  `main.cc`, `docker cp` them in or you run the stale version.
- **A flag that is assigned but never read fails silently.** After changing a
  flag group, add a self-check that reads it back from the artifact.
- **Never touch the interpreter before `Module.execute_interp()`**; guard
  boot-path probes with try/catch or `__octaveReady` stays false and the page
  looks hung.
- **`addpath` reads MEMFS, not the site's HTTP directory.** Files must be
  written into MEMFS before Octave can see them.
- **Never guess mount points**: `assets.py bundle-m` reads them verbatim from
  `build/assets-meta.json`.
- **Test dlopen on a fresh page every time**; a second call on the same page is
  unreliable.
- **Probes and self-checks never run on the boot path**: a bad artifact would
  hang the page and take every acceptance down with it.
- **Shell traps**: `pkill -f 'x'` matches itself (use `'x[y]'`); `rc=$?` after a
  pipe reads the last command; `&&` before `&` backgrounds the whole chain;
  `grep -c` exits 1 on zero matches.
- **HTTP caching accepts only `no-cache` + `ETag`**: `no-store` disables
  caching; headers without an ETag force full retransfers. Machine-checked by
  `build/serve-coi.py --selftest`.
- **When something fails, suspect the instrument first**: a probe timeout
  shorter than the real transfer turns a working product red.
- **Conclusions come from artifacts only** (`sha256sum`, `sweep-logs/`,
  probe output), never from impressions.

## Agent workflow

- **Tickets**: `.scratch/open-questions/issues/NN-*.md` (local tracker, not
  GitHub Issues). An open ticket must carry a runnable `**Settling:**` line;
  anything that cannot name one is a guess and belongs in `NOTES-*.md`.
- **Triage labels** on the `**Status:**` line: `needs-triage`, `needs-info`,
  `ready-for-agent`, `ready-for-human`, `wontfix`, `resolved` — see
  `docs/agents/triage-labels.md`; resolved tickets are never deleted.
- **Domain glossary**: `CONTEXT.md`; agent-facing docs live in `docs/agents/`.
