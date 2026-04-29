---
description: Run a Modal function from a one-line description. Generates the app file, deploys, runs.
---

# /aish:modal-run

Hand off to the `ml-env-setup` subagent.

## What to do

1. Take the user's one-line description (e.g. "fine-tune all-MiniLM on /data/queries.jsonl").
2. Delegate to `ml-env-setup` with the description.
3. Subagent will:
   - call the `hf-env-setup` skill to choose torch/transformers/CUDA versions
   - generate `modal_app.py` in the user's CWD with a `@app.function` entry point
   - SHOW the generated file to the user before deploy
   - on user OK, call `aish-modal:deploy_app` then `aish-modal:run_app`
   - stream the result back

## Hard rules

- Never write outside the user's CWD without explicit confirmation.
- Never overwrite an existing `modal_app.py` without a diff and confirmation.
- If the model is gated (HF), surface that and stop — do not auto-accept terms.
- Use `aish-modal:create_secret` for HF_TOKEN if needed; never inline tokens into the app file.
