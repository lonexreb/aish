---
description: One-shot health check across both aish providers — TensorDock instances + Modal apps + local GPU.
---

# /aish:status

Snapshot what's running and what's available. Read-only; never mutates anything.

## What to do

1. Call `aish-tensordock:list_instances`. Summarize:
   - count of running vs stopped instances
   - per-instance: name, gpu, hourly cost (if visible), uptime
2. Call `aish-modal:list_apps`. Summarize:
   - count of live apps; flag any `errored` state
3. Run the `gpu-detect` skill (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/gpu-detect/detect.py`) to report the local GPU.
4. Combine into a 6-10 line status block. No emoji; aim for terse.

## Output shape

```
TensorDock — N running, M stopped
  · <name> · <gpu> · <state> · $<rate>/hr
Modal — N apps live
  · <name> · <state>
Local GPU — <model> (<gpu_type>, <capability>)
  Note: <one-line follow-up if anything is off, e.g. CUDA mismatch>
```

## Footguns

- Do **not** call any state-changing tool from this command.
- If `TENSORDOCK_API_TOKEN` is unset, surface that as the first line; do not silently skip.
- If Modal CLI is missing, surface that; recommend `pip install modal && modal setup`.
