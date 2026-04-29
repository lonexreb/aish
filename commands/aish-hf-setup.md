---
description: Plan a HuggingFace model or dataset environment without deploying anything.
---

# /aish:hf-setup

Run the `hf-env-setup` skill against a HuggingFace identifier and report back. **Plan only — does not deploy.**

## What to do

1. Parse the HF identifier from the user's prompt (`owner/repo`).
2. Run the `hf-env-setup` skill (see `skills/hf-env-setup/SKILL.md`).
3. Run the `gpu-detect` skill to read the local GPU.
4. Produce:
   - License / gating status
   - Recommended Python / torch / CUDA versions
   - Estimated GPU class (e.g. "needs ≥80GB VRAM, recommend H100")
   - Whether the user's local GPU can run it, with reasoning
   - A drop-in `modal_app.py` if they want to run on Modal
   - A drop-in TensorDock `cloud_init_commands` array if they want a VM

## Hard rules

- Never download model weights as part of this command.
- Never auto-accept gated-model terms.
- If the user is on Apple Silicon, mention `device='mps'` and CUDA-only kernel limitations explicitly.
