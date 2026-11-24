# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual strings used in this repo's tracker.

**本仓的 tracker 是本地 markdown**（`.scratch/`），没有标签系统 —— 角色以每张工单头部的
`**Status:**` 行的字符串表示。所以右列就是**该行该写什么**。

| Label in mattpocock/skills | 本仓 `Status:` 行的值 | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | 待评估：这条悬案还没人确认过它是否真的未结案 |
| `needs-info`               | `needs-info`         | 等补充：结算件写不出来，得先问人或先量一次    |
| `ready-for-agent`          | `ready-for-agent`    | 已完整规格化，AFK 的 agent 可以直接抓      |
| `ready-for-human`          | `ready-for-human`    | 需要人做（真机手测、需要设备/凭据）        |
| `resolved`                 | `resolved`           | 已结案（附可执行 `Settling:` 与 `## Answer`；历史工单保留不删） |

⚠️ 本仓的一条本地约定：Trust v2 下 `check_questions.py` 只接受
`ready-for-agent`、`ready-for-human`、`resolved` 三种状态；已决定不做或结案的悬案同样留在目录里、标记为 `resolved` 并写明原因，不删文件，以免后来者重复踩坑。
（同源规矩见 `AGENTS.md` 事实纪律第 4 条（推断与实测分开）与 `retractions.json` 的用法。）

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding string from this table.
