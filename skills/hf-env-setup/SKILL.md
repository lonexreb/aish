---
description: Set up a HuggingFace model or dataset environment — recommend Python/CUDA/torch versions, generate a Modal app spec, and warn about license/gating before download.
---

# hf-env-setup

When the user wants to use a HuggingFace model or dataset, this skill walks them through the environment they need before they kick off a download or training run.

Use it when the user says any of:

- "Run `<owner>/<model>` on Modal"
- "Set up an env for `<dataset>`"
- "What CUDA / torch version do I need for `<model>`?"
- "Train this model on TensorDock"

## What it produces

1. A short report describing:
   - Model / dataset license and gating status (gated / public / requires HF auth).
   - Recommended Python and torch versions.
   - Required CUDA compute capability (cross-referenced against `gpu-detect`).
   - Approximate memory footprint and a guess at minimum GPU class.
2. A Modal app spec scaffold (`modal_app.py`) tuned to the model size.
3. A `requirements.txt` snippet pinning torch + transformers + accelerate.

## How the model should run it

Pseudocode of the workflow:

```
1. Parse the user's HF identifier (owner/repo).
2. Use the Bash tool to run `huggingface-cli scan-cache --help` to confirm CLI is installed;
   if not, recommend `pip install huggingface_hub`.
3. Use WebFetch on `https://huggingface.co/api/models/<id>` to read public metadata
   (config.json, modelcard, gating). Handle 401/404 gracefully.
4. Run gpu-detect skill. Cross-check compute capability against the model's recommended dtype.
5. Generate the modal_app.py + requirements.txt in the user's workspace, with a clearly
   labeled "// EDIT ME" section for storage / volume / secret choices.
6. Surface the gating warning if the model is gated — never auto-accept terms.
```

## Defaults

- Python 3.11 (matches Modal's default and aish's pinned range).
- torch 2.4 + cu121 unless the model card specifies otherwise.
- transformers 4.46+, accelerate 1.0+.
- For models > 13B params: recommend H100 / A100 80 GB; smaller models can use L4 / A10G.

## What this skill does NOT do

- Auto-accept gated-model terms. The user must do that on huggingface.co.
- Store HF tokens. Tokens go in `modal secret create hf` as `HF_TOKEN` (use `aish-modal:create_secret`).
- Run training. It only sets up the environment.

## Cross-references

- `gpu-detect` skill — for local capability check.
- `aish-modal:create_volume` — for dataset cache.
- `aish-modal:create_secret` — for HF_TOKEN.
- `aish-modal:deploy_app` / `run_app` — to actually launch the workload.

## Provenance

Replaces the empty stub `application/gpu_setup.py` from AIsh-v0. The intent (HF-aware
env bring-up) was named there but never implemented. This skill fills it in.
