# PRINCIPLES · Octave-Full-Wasm

> Architecture principles enforced by `zreflect/doc.py` and `reflect-local/principles.json`, rendered via `python3 zreflect/facts.py --render-doc`.

<!-- AUTO:RULES -->
> This block is rendered by `zreflect/facts.py --render-doc` from the `RULES` table in `zreflect/doc.py` (plus optional `reflect-local/principles.json`); **do not hand-edit**.
> Every row's judging command is executed verbatim at every commit (`check_facts_replay`).

| id | principle | judging command |
|---|---|---|
| `assertion_lifecycle` | a retracted claim must not quietly return as current state | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_retractions.py'))"` |
| `client_side_only` | client-side execution only: deployed site/ ships static HTML, JS, and wasm artifacts with zero server-side execution endpoints | `python3 -c "import os,sys;ok=os.path.isfile('site/index.html') and os.path.isfile('site/octave-core.js');print('client_side_only=ok' if ok else 'missing');sys.exit(0 if ok else 1)"` |
| `comments_earn_their_place` | explanation volume must fit AST complexity under `mismatch`, or carry no docstrings under `strict` | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_explain.py'))"` |
| `core_sealed` | shared suite core modules, gates, hooks, and language packs match `zreflect/SEAL.json` | `python3 zreflect/registry.py --verify-seal` |
| `declared_not_globbed` | predicates are declarations, not filenames: the execution surface reads registry --run <phase> | `python3 zreflect/registry.py --gates` |
| `exec_position_is_a_command` | every execution position (stamp cmd / pin cmd / Settling / evidence) must hold a runnable command | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;bad=doc.all_exec_position_problems();[print(p) for p in bad] or print('prose_positions=0');sys.exit(1 if bad else 0)"` |
| `falsifiable` | claims must be falsifiable: every declared gate carries a runnable --selftest | `python3 zreflect/registry.py --all-runnable` |
| `hard_needs_criterion` | a rule is hard only if it has a machine criterion; without one it does not enter the table at all | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;p=doc._cmd_shape_problems();print('shape_problems=%d' % len(p));sys.exit(1 if p else 0)"` |
| `host_agnostic` | the suite's source recognizes no host's directory names or config formats | `python3 -c "import os,sys;w=['.'+chr(122)+chr(99)+chr(111)+chr(100)+chr(101)+'/','ZCODE_'+'PROJECT_DIR','hook'+'SpecificOutput'];bad=[(d,f) for d in ('zreflect','reflect-local') for r,_,fs in os.walk(d) for f in fs if f.endswith('.py') and any(k in open(os.path.join(r,f),encoding='utf-8',errors='replace').read() for k in w)];print('host_coupled=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `lane_purity` | two visible lanes only (base=wasm32, w64=wasm64): retired threads and w64-base lanes must never reappear in site artifacts or scripts | `python3 build/113/check-lane-purity.py --selftest` |
| `legacy_channels_retired` | legacy mail inbox, legacy hook wrapper directory, root facts wrapper, and root selftest shim remain retired after Trust v2 upgrade | `python3 -c "import os,sys;bad=[p for p in ('mail','reflect-'+'hooks','build/'+'facts.py','gates-selftest.sh') if os.path.exists(p)];print('legacy_channels_retired=ok' if not bad else 'bad='+','.join(bad));sys.exit(1 if bad else 0)"` |
| `machine_rows` | machine rows are defined in one place (`i18n.ROWS`) for both producers and consumers | `python3 -c "import sys;sys.path.insert(0,'zreflect');import i18n;print('rows=%d' % len(i18n.ROWS));sys.exit(0 if i18n.ROWS else 1)"` |
| `no_retired_names` | retired names must not appear as current state; sha provenance and age are checkable | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_stale.py'))"` |
| `number_once` | each number is produced once and re-reconciled every commit: documents cite it as `[[key]]`, never hand-copy it | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_facts.py'))"` |
| `only_measured` | numbers/behavior trust measurement only; every fact must carry a re-run command | `python3 -c "import json,sys;sys.path.insert(0,'zreflect');import knobs;d=json.load(open(knobs.repo_path('REFLECT_FACTS'),encoding='utf-8'))['facts'];bad=[k for k,v in d.items() if not (isinstance(v,dict) and str(v.get('cmd','')).strip())];print('facts_without_cmd=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `open_questions_settle` | every unresolved open question must carry a runnable settler | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_questions.py'))"` |
| `selfcert_harness` | every declared module must have a --selftest entry | `python3 -c "import sys;sys.path.insert(0,'zreflect');import registry;u=registry.selftest_modules()[1];print('missing_selftest=%d' % len(u));sys.exit(1 if u else 0)"` |
| `snapshot_hygiene` | a mutable global imported across modules is a value copy: read via the module attribute instead | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_snapshots.py'))"` |
| `style_is_not_a_rule` | style preferences do not enter the rule table | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;style=('style','naming','comment','layout','format');bad=[r.id for r in doc.all_rules() if r.id in style];print('style_ids=%d' % len(bad));sys.exit(1 if bad else 0)"` |
| `three_readmes` | the README group is checked structurally and kept in the same push batch | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_readme_sync.py'))"` |
| `zero_language` | zero language in the core: user-visible messages go through M(code); machine contracts are untranslatable by construction | `python3 -c "import sys;sys.path.insert(0,'zreflect');import doc;sys.exit(doc.enforced_by('check_i18n.py'))"` |

21 principles -- each with a judging command that **really runs**.
<!-- /AUTO:RULES -->
