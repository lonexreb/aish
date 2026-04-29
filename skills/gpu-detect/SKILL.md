---
description: Detect the local GPU (NVIDIA via nvidia-smi, macOS / Apple Silicon via system_profiler), report compute capability, and fall back to a simulated GPU for cross-platform development.
---

# gpu-detect

Detect the user's local GPU and tell them what it can and can't do for ML workloads. Use this skill when the user asks any of:

- "What GPU do I have?"
- "Is CUDA working?"
- "Why isn't my training using the GPU?"
- "What's my compute capability?"
- before recommending TensorDock / Modal provisioning, to know whether they need cloud GPUs at all.

## How to use it

Run the bundled helper:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/gpu-detect/detect.py
```

It prints a JSON object with shape:

```json
{
  "platform": "Darwin" | "Linux" | "Windows",
  "detected": true | false,
  "simulated": false,
  "gpu": {
    "model": "NVIDIA H100 80GB HBM3",
    "memory_gb": 80.0,
    "gpu_type": "NVIDIA" | "AMD" | "INTEL" | "APPLE" | "UNKNOWN",
    "cuda_capability": "9.0",
    "driver_version": "535.104.05",
    "cuda_version": "12.2"
  },
  "notes": ["informational strings"]
}
```

If no physical GPU is detected (e.g. on a CI runner), `simulated: true` is set and a representative simulated entry is returned so downstream tools can keep planning. **Never** present a simulated GPU to the user as if it were real — surface the `simulated: true` flag.

## Decision rules for the model after running this

- **Apple Silicon detected** (`gpu_type: APPLE`): tell the user CUDA is unavailable; recommend Metal Performance Shaders for Torch (`device='mps'`) or pivot to TensorDock / Modal for CUDA workloads.
- **NVIDIA detected with `cuda_capability >= 7.0`**: modern. Suggest local training with `torch.cuda`.
- **NVIDIA with `cuda_capability < 7.0`** (Pascal or older): some kernels (FP16, BF16, FlashAttention) won't run; recommend cloud GPUs for non-trivial training.
- **No GPU detected** (`detected: false`): drive the user toward TensorDock / Modal via the `gpu-operator` subagent.

## What this skill does NOT do

- Install drivers or CUDA. That's deliberately out of scope for v1.
- Touch the network. The detector only reads local hardware.
- Recommend specific GPU SKUs to buy. Use the `gpu-operator` subagent for that.

## Provenance

Logic carried over from [AIsh-v0 `infrastructure/hardware.py`](https://github.com/lonexreb/AIsh-v0/blob/main/agentic_terminal/agentic_terminal/infrastructure/hardware.py) — the original 297-line detector — flattened into a single dependency-free script and reshaped into the SKILL.md format Claude Code expects.
