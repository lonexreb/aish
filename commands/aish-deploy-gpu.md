---
description: Guided GPU VM provisioning on TensorDock. Asks just enough to choose a hostnode, then deploys.
---

# /aish:deploy-gpu

Hand off to the `gpu-operator` subagent for an end-to-end provisioning workflow. The user provides a workload description in plain English; the agent picks a sensible config.

## What to do

1. Confirm the user's workload in one sentence (e.g. "training a 7B model overnight").
2. Confirm budget cap (default: ask once).
3. Delegate to the `gpu-operator` subagent with:
   - the workload description
   - the budget cap
   - the user's region preference (if stated)
4. Subagent will:
   - call `aish-tensordock:list_locations` and rank by `price_per_hr`
   - call `aish-tensordock:list_hostnodes` for capacity confirmation
   - propose a deploy config and SHOW it before executing
   - on user OK, call `aish-tensordock:deploy_instance`
   - return the instance id and SSH command

## Hard rules

- **Never deploy without user confirmation of the proposed config.** Cost is real.
- If `gpu-detect` shows a usable local GPU and the workload is small, suggest local first.
- Always set a `name` of the form `aish-<workload>-<YYYYMMDD>`.
- Always include `cloud_init_commands` that install the user's stated framework (torch, jax, etc.).
