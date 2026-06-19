# Solution Steps

1. Open `agent/postprocess.py`; this is the boundary layer where raw tool outputs must be converted into a deterministic telemetry contract before the LLM sees them.

2. Define explicit read states for the two telemetry reads: `ok`, `stale`, `missing`, `offline`, and `error`. Treat `ok` as the only fresh, complete, healthy-compatible state.

3. Keep timestamp parsing and freshness checking in code. Parse ISO timestamps, normalize them to UTC, compute read age, and compare it with `config.READING_FRESHNESS_SECONDS`.

4. For each raw tool result, implement a classifier. If `available` is not true, mark the read `missing`. If the timestamp is absent or invalid, mark it `missing` because freshness cannot be proven. If the timestamp is too old, mark it `stale`. If the fresh status is `offline`, mark it `offline`. If the fresh status is `error` or unrecognized, mark it `error`. If the fresh status is `online` and the gateway uplink is OK, mark it `ok`.

5. Build the reconciled diagnosis context from the classified sensor and gateway reads. Set `overall_status` to `complete` only when both reads are `ok`. Set it to `degraded` when there is a fresh explicit offline/error condition. Otherwise set it to `unknown` for stale or missing telemetry. Set `data_complete` and `can_confirm_healthy` to true only for `complete`.

6. Include traceable details in the context: schema version, generation time, freshness budget, per-read ages and reasons, overall status, completeness flag, health signal, and blocking reasons for non-complete diagnoses.

7. Implement `render_context_for_model` so it preserves the typed context instead of summarizing away the important distinctions. Render the full context as JSON and repeat the critical rule: if `can_confirm_healthy` is false, the model must not claim the device is healthy or operating normally.

8. Leave the LLM client, tools, tool schemas, and prompts unchanged. The orchestrator already calls both tools, reconciles their outputs with `build_diagnosis_context`, renders that context for the final model call, and persists `overall_status` and `data_complete` in `diagnosis_log`.

9. Run the scaffold with `./run.sh` to start PostgreSQL and verify the app loads.

10. Run the invariant tests with `pytest invariants/` to confirm fresh healthy telemetry is complete, offline gateway telemetry is degraded, stale/missing telemetry is not treated as complete, the rendered model context keeps the degraded signal, and diagnosis logs persist the completeness fields.

