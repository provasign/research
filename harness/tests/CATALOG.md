# Harness test catalog

One entry per test, generated from the test source so it stays literal --
regenerate after adding/renaming tests rather than hand-editing stale rows.
See `../README.md` for how these fit the harness as a whole.

## Two run styles

| Style | Files | Run with |
|---|---|---|
| `unittest.TestCase` (discoverable) | 9 files, 76 tests | `python3 -m unittest discover -s tests` (from `harness/`) |
| standalone script, `assert` + `if __name__ == "__main__"` | 6 files, 44 tests | `python3 tests/<file>.py` individually |

## `unittest` suite (`python3 -m unittest discover -s tests`)

### `test_bench.py` (9 tests)

Unit tests for harness/bench.py: arm construction, model overrides, and
the results index -- everything testable without live claude/codex/docker.

**`ArmsForTests`**

- [`test_both_matches_legacy_four_arm_order`](test_bench.py#L23) -- Both matches legacy four arm order.
- [`test_on_is_prism_only`](test_bench.py#L29) -- On is prism only.
- [`test_off_is_native_only`](test_bench.py#L32) -- Off is native only.
- [`test_single_agent_smoke_test`](test_bench.py#L36) -- Single agent smoke test.

**`ParseKvTests`**

- [`test_defaults_when_unset`](test_bench.py#L41) -- Defaults when unset.
- [`test_overrides_one_model`](test_bench.py#L44) -- Overrides one model.
- [`test_overrides_both_models`](test_bench.py#L49) -- Overrides both models.

**`IndexTests`**

- [`test_index_is_idempotent`](test_bench.py#L68) -- Index is idempotent.
- [`test_index_dedupes_by_run_dir_and_cell_id`](test_bench.py#L86) -- Index dedupes by run dir and cell id.

### `test_coding_suite.py` (10 tests)

Back-compat tests for `coding_suite.py`'s re-exported names (it's now a thin
preset over `bench.py`/`lib/`) -- GPT-5.5 cost calc, source-vs-generated path
filtering, PATH isolation, and the native/prism protocol audit.

**`GptCostTests`**

- [`test_standard_cost_separates_cached_input`](test_coding_suite.py#L23) -- Standard cost separates cached input.
- [`test_long_context_multiplier_applies_to_full_run`](test_coding_suite.py#L37) -- Long context multiplier applies to full run.
- [`test_incomplete_measurement_has_no_estimated_cost`](test_coding_suite.py#L51) -- Incomplete measurement has no estimated cost.

**`SourcePathTests`**

- [`test_accepts_python_implementation_files`](test_coding_suite.py#L60) -- Accepts python implementation files.
- [`test_rejects_tests_docs_and_generated_databases`](test_coding_suite.py#L64) -- Rejects tests docs and generated databases.
- [`test_template_content_includes_generated_source_but_not_indexes`](test_coding_suite.py#L70) -- Template content includes generated source but not indexes.

**`AgentPathTests`**

- [`test_prism_arm_exposes_pinned_cli`](test_coding_suite.py#L85) -- Prism arm exposes pinned cli.
- [`test_native_arm_does_not_expose_prism_cli`](test_coding_suite.py#L96) -- Native arm does not expose prism cli.

**`AuditTests`**

- [`test_codex_cli_fallback_counts_as_prism_adoption`](test_coding_suite.py#L105) -- Codex cli fallback counts as prism adoption.
- [`test_native_cli_prism_is_a_protocol_violation`](test_coding_suite.py#L115) -- Native cli prism is a protocol violation.

### `test_docker_eval.py` (4 tests)

Tests for `scoring/docker_eval.py`'s own error handling: distinguishing a
Docker-daemon problem from a real scoring failure, and a pytest *collection*
error (bad test file) from a genuinely empty/passing run.

**`DockerPreflightTests`**

- [`test_require_docker_accepts_running_daemon`](test_docker_eval.py#L25) -- Require docker accepts running daemon.
- [`test_require_docker_reports_daemon_error`](test_docker_eval.py#L31) -- Require docker reports daemon error.

**`CollectionDetectionTests`**

- [`test_collection_error_is_distinct_from_empty_run`](test_docker_eval.py#L41) -- Collection error is distinct from empty run.
- [`test_pytest_run_keeps_collection_status_separate`](test_docker_eval.py#L49) -- Pytest run keeps collection status separate.

### `test_gate_measurement.py` (12 tests)

Tests for `ab_gate.py`'s cost/quality gate: an arm only "passes" if it is
provably no worse on quality and no more expensive, with cost/tokens/retries
tracked per invocation so a stale or partial measurement can never be
silently treated as free or complete.

**`GateMeasurementTests`**

- [`test_unknown_cost_and_skipped_tasks_cannot_pass`](test_gate_measurement.py#L49) -- Unknown cost and skipped tasks cannot pass.
- [`test_retries_count_first_cost_and_tokens_and_fail_when_still_broken`](test_gate_measurement.py#L58) -- Retries count first cost and tokens and fail when still broken.
- [`test_equal_quality_cheaper_complete_bed_passes`](test_gate_measurement.py#L68) -- Equal quality cheaper complete bed passes.
- [`test_missing_retry_usage_and_baseline_failure_are_harness_errors`](test_gate_measurement.py#L76) -- Missing retry usage and baseline failure are harness errors.
- [`test_attempts_are_immutable_and_unknowns_not_zeroed`](test_gate_measurement.py#L82) -- Attempts are immutable and unknowns not zeroed.
- [`test_run_cell_isolates_corpus_and_invalidates_changed_manifest`](test_gate_measurement.py#L95) -- Run cell isolates corpus and invalidates changed manifest.
- [`test_run_arm_records_full_usage_and_marks_provider_errors`](test_gate_measurement.py#L152) -- Run arm records full usage and marks provider errors.
- [`test_measurement_excludes_other_invocations_and_keeps_current_retries`](test_gate_measurement.py#L172) -- Measurement excludes other invocations and keeps current retries.
- [`test_legacy_or_inconsistent_measurement_identity_is_unknown`](test_gate_measurement.py#L185) -- Legacy or inconsistent measurement identity is unknown.
- [`test_invocation_spend_is_fresh_only_and_saved_before_fail_fast`](test_gate_measurement.py#L189) -- Invocation spend is fresh only and saved before fail fast.
- [`test_invocation_unknown_attempt_never_becomes_free`](test_gate_measurement.py#L214) -- Invocation unknown attempt never becomes free.
- [`test_old_manifest_spend_does_not_decide_cheaper_gate`](test_gate_measurement.py#L226) -- Old manifest spend does not decide cheaper gate.

### `test_lib_pricing.py` (6 tests)

Unit tests for harness/lib/pricing.py.

**`Gpt55CostTests`**

- [`test_standard_cost_separates_cached_input`](test_lib_pricing.py#L19) -- Standard cost separates cached input.
- [`test_long_context_multiplier_applies_to_full_run`](test_lib_pricing.py#L31) -- Long context multiplier applies to full run.
- [`test_incomplete_measurement_has_no_estimated_cost`](test_lib_pricing.py#L43) -- Incomplete measurement has no estimated cost.
- [`test_untabulated_model_is_a_no_op`](test_lib_pricing.py#L48) -- Untabulated model is a no op.

**`PricingTableTests`**

- [`test_pricing_for_known_model`](test_lib_pricing.py#L56) -- Pricing for known model.
- [`test_pricing_for_unknown_model_is_none`](test_lib_pricing.py#L59) -- Pricing for unknown model is none.

### `test_lib_runner_core.py` (16 tests)

Unit tests for harness/lib/runner_core.py: the audit logic, PATH
isolation, and the template content-hash mismatch check -- everything
testable without live claude/codex/docker.

**`InvokesPrismTests`**

- [`test_detects_bare_prism_invocation`](test_lib_runner_core.py#L23) -- Detects bare prism invocation.
- [`test_detects_prism_under_a_path`](test_lib_runner_core.py#L26) -- Detects prism under a path.
- [`test_ignores_unrelated_commands`](test_lib_runner_core.py#L29) -- Ignores unrelated commands.
- [`test_tolerates_unterminated_quotes`](test_lib_runner_core.py#L32) -- Tolerates unterminated quotes.

**`AuditCallsTests`**

- [`test_native_arm_using_mcp_prism_is_a_violation`](test_lib_runner_core.py#L37) -- Native arm using mcp prism is a violation.
- [`test_native_arm_using_prism_cli_is_a_violation`](test_lib_runner_core.py#L43) -- Native arm using prism cli is a violation.
- [`test_prism_arm_using_prism_cli_is_adoption_not_a_violation`](test_lib_runner_core.py#L49) -- Prism arm using prism cli is adoption not a violation.
- [`test_delegation_tool_is_a_violation_for_sonnet`](test_lib_runner_core.py#L57) -- Delegation tool is a violation for sonnet.
- [`test_duplicate_prism_calls_are_counted`](test_lib_runner_core.py#L63) -- Duplicate prism calls are counted.

**`TemplateContentTests`**

- [`test_excludes_vcs_and_index_databases`](test_lib_runner_core.py#L74) -- Excludes vcs and index databases.
- [`test_content_hash_changes_when_a_file_changes`](test_lib_runner_core.py#L90) -- Content hash changes when a file changes.

**`AgentPathTests`**

- [`test_prism_arm_exposes_pinned_cli_ahead_of_rg`](test_lib_runner_core.py#L101) -- Prism arm exposes pinned cli ahead of rg.
- [`test_native_arm_does_not_expose_prism_cli`](test_lib_runner_core.py#L108) -- Native arm does not expose prism cli.
- [`test_no_env_dir_is_tolerated`](test_lib_runner_core.py#L112) -- No env dir is tolerated.

**`SourcePathTests`**

- [`test_accepts_python_implementation_files`](test_lib_runner_core.py#L118) -- Accepts python implementation files.
- [`test_rejects_tests_and_generated_databases`](test_lib_runner_core.py#L121) -- Rejects tests and generated databases.

### `test_lib_suites.py` (6 tests)

Unit tests for harness/lib/suites.py: suite/task discovery from
harness/tasks/<suite>/ and SUITE.json metadata.

**`RealSuiteTests`** -- Exercises the real harness/tasks/e2e and harness/tasks/manual

- [`test_e2e_suite_is_discovered_with_kind_and_pilot`](test_lib_suites.py#L26) -- E2e suite is discovered with kind and pilot.
- [`test_manual_suite_is_discovered_with_kind`](test_lib_suites.py#L34) -- Manual suite is discovered with kind.
- [`test_phases_partition_e2e_tasks`](test_lib_suites.py#L39) -- Phases partition e2e tasks.

**`SyntheticSuiteTests`**

- [`test_suite_without_suite_json_scans_directory`](test_lib_suites.py#L48) -- Suite without suite json scans directory.
- [`test_suite_json_pilot_and_category_metadata`](test_lib_suites.py#L60) -- Suite json pilot and category metadata.
- [`test_missing_suite_returns_empty`](test_lib_suites.py#L80) -- Missing suite returns empty.

### `test_read_after_locate.py` (8 tests)

Tests for the "did the agent actually read the file before editing it"
audit: read/edit/search events must genuinely cover the changed lines --
duplicate reads, stale ranges after an edit, a shell command's uncertain
effect, and basename-only matches must not be credited as proof.

**`ReadAfterLocateTests`**

- [`test_read_does_not_credit_its_own_result_and_stream_duplicates`](test_read_after_locate.py#L36) -- Read does not credit its own result and stream duplicates.
- [`test_partial_window_cannot_prove_whole_file_read_duplicate`](test_read_after_locate.py#L48) -- Partial window cannot prove whole file read duplicate.
- [`test_edit_invalidates_old_lines_before_partial_redelivery`](test_read_after_locate.py#L56) -- Edit invalidates old lines before partial redelivery.
- [`test_basename_suffix_is_not_file_identity`](test_read_after_locate.py#L68) -- Basename suffix is not file identity.
- [`test_search_context_is_delivered_source_and_compaction_invalidates_it`](test_read_after_locate.py#L76) -- Search context is delivered source and compaction invalidates it.
- [`test_shell_uncertainty_does_not_turn_location_into_a_confirmed_edit`](test_read_after_locate.py#L85) -- Shell uncertainty does not turn location into a confirmed edit.
- [`test_successful_edit_is_reread_but_failed_edit_is_only_uncertain`](test_read_after_locate.py#L100) -- Successful edit is reread but failed edit is only uncertain.
- [`test_fresh_source_after_shell_restores_range_coverage`](test_read_after_locate.py#L113) -- Fresh source after shell restores range coverage.

### `test_usage_account.py` (5 tests)

Tests for `usage_account.py`'s token/turn accounting from a Claude session
transcript: cache-creation tokens counted, streaming duplicates resolved to
the latest usage snapshot, and incomplete/missing usage data flagged as
`unknown` rather than defaulting to zero or "complete."

**`UsageTests`**

- [`test_cache_creation_is_included_and_unknown_is_not_zero`](test_usage_account.py#L21) -- Cache creation is included and unknown is not zero.
- [`test_streaming_duplicates_use_latest_usage_and_distinct_tool_ids`](test_usage_account.py#L36) -- Streaming duplicates use latest usage and distinct tool ids.
- [`test_session_transcript_without_stdout_result_has_valid_diagnostics`](test_usage_account.py#L61) -- Session transcript without stdout result has valid diagnostics.
- [`test_explicit_zero_cache_counters_are_valid_but_missing_is_unknown`](test_usage_account.py#L76) -- Explicit zero cache counters are valid but missing is unknown.
- [`test_missing_message_ids_cannot_be_treated_as_complete_usage`](test_usage_account.py#L88) -- Missing message ids cannot be treated as complete usage.

## Standalone scripts (`python3 tests/<file>.py`)

### `test_impact_oracle.py` (5 tests)

Deterministic tests for the change-impact ceiling gate.

- [`test_anchor_is_explicit_metadata_not_ground_truth`](test_impact_oracle.py#L38) -- Anchor is explicit metadata not ground truth.
- [`test_change_impact_deduplicates_and_preserves_fidelity`](test_impact_oracle.py#L50) -- Change impact deduplicates and preserves fidelity.
- [`test_thresholds_gate_recall_precision_payload_and_completeness`](test_impact_oracle.py#L84) -- Thresholds gate recall precision payload and completeness.
- [`test_snapshot_uses_pinned_commit_and_checks_index`](test_impact_oracle.py#L96) -- Snapshot uses pinned commit and checks index.
- [`test_index_failure_is_a_harness_error`](test_impact_oracle.py#L123) -- Index failure is a harness error.

### `test_query_oracle.py` (2 tests)

file_sections: delivered context is credited per file, and a section ends
at the next bold header of ANY kind.

Run: cd research/harness && python -m pytest -p no:asyncio -p no:pytest_asyncio tests/test_query_oracle.py -q

- [`test_sections_are_per_file`](test_query_oracle.py#L47) -- Sections are per file.
- [`test_appendix_does_not_accrue_to_previous_file`](test_query_oracle.py#L54) -- Appendix does not accrue to previous file.

### `test_run_codex.py` (5 tests)

Unit tests for Codex JSONL event parsing.

Run: cd research/harness && python -m pytest tests/test_run_codex.py -q

- [`test_parse_events_detects_prism_command_and_usage`](test_run_codex.py#L26) -- Parse events detects prism command and usage.
- [`test_parse_events_normalizes_usage_aliases`](test_run_codex.py#L62) -- Parse events normalizes usage aliases.
- [`test_parse_events_keeps_largest_repeated_usage_snapshot`](test_run_codex.py#L82) -- Parse events keeps largest repeated usage snapshot.
- [`test_parse_events_captures_codex_errors`](test_run_codex.py#L93) -- Parse events captures codex errors.
- [`test_lead_bin_unwraps_shell_commands`](test_run_codex.py#L102) -- Lead bin unwraps shell commands.

### `test_score.py` (13 tests)

Unit tests for the Mode-A scorer -- no agent, no network.

Run: cd research/harness && python -m pytest tests/ -q
(or: python tests/test_score.py)

- [`test_perfect_and_complete`](test_score.py#L41) -- Perfect and complete.
- [`test_incomplete_but_confident_is_overconfident`](test_score.py#L50) -- Incomplete but confident is overconfident.
- [`test_incomplete_and_honest_not_overconfident`](test_score.py#L58) -- Incomplete and honest not overconfident.
- [`test_false_positive_lowers_precision`](test_score.py#L67) -- False positive lowers precision.
- [`test_wrong_file_same_symbol_is_a_false_positive`](test_score.py#L76) -- Wrong file same symbol is a false positive.
- [`test_wrong_directory_same_basename_is_not_a_match`](test_score.py#L96) -- Wrong directory same basename is not a match.
- [`test_absolute_worktree_prefix_still_agrees`](test_score.py#L106) -- Absolute worktree prefix still agrees.
- [`test_bare_basename_is_weak_when_ambiguous`](test_score.py#L113) -- Bare basename is weak when ambiguous.
- [`test_pathless_symbol_is_weak_evidence_only`](test_score.py#L122) -- Pathless symbol is weak evidence only.
- [`test_test_sites_are_neutral_not_false_positives`](test_score.py#L135) -- Test sites are neutral not false positives.
- [`test_maven_java_test_paths_are_neutral`](test_score.py#L145) -- Maven java test paths are neutral.
- [`test_duplicate_answer_sites_have_set_semantics`](test_score.py#L150) -- Duplicate answer sites have set semantics.
- [`test_no_json_yields_zero`](test_score.py#L162) -- No json yields zero.

### `test_swebench_ab.py` (8 tests)

Offline, zero-cost checks for swebench_ab.py's own mechanics — no API
calls. Run before spending any money on agent cells: python3 -m pytest
test_swebench_ab.py, or just: python3 test_swebench_ab.py

History: the 2026-08-11 grep-denial bug (prism arm silently kept full grep
access — --allowedTools omission is not a deny in headless mode; only
--disallowedTools is) was found live, by hand, after >$100 of cells had
already run under the broken assumption. That was fixed with a harness-side
--disallowedTools construction, verified here through 2026-08-14.

2026-08-14: superseded. v0.50.0 shipped prism's own PreToolUse hook as the
real deployment mechanism, so the harness ran the REAL `prism init
--deny-builtin-search` inside the prism-arm worktree instead of simulating
denial.

2026-08-15: superseded AGAIN, in the other direction. v0.52.0 reverted the
whole denial arc — no hook ships, and `prism init` writes no deny rules. The
harness kept passing --deny-builtin-search for three prism releases after
that, so every prism-arm cell ran with grep/rg blocked: a configuration no
user gets, which makes "the agent used prism" unfalsifiable. Found in the
v054-smoke traces (4 denied greps in the prism arm, 0 in baseline). The
contract is now the inverse of what this file asserted a day earlier, which
is exactly why it is asserted rather than remembered.

This file is still where this class of check belongs: verified for free,
before the first paid cell.

- [`test_prism_arm_runs_plain_init_and_never_denies_search`](test_swebench_ab.py#L85) -- The prism arm must run `prism init` with NO flags.
- [`test_boundary_is_denied_in_every_arm`](test_swebench_ab.py#L125) -- The contamination boundary must hold on BOTH arms, always.
- [`test_broad_bash_is_allowed_so_the_toolchain_works`](test_swebench_ab.py#L143) -- Ordinary Python build/test idioms must not be refused.
- [`test_both_arms_get_identical_investigation_guidance`](test_swebench_ab.py#L161) -- Arm isolation: the only prompt difference may be the prism block.
- [`test_prism_cli_arm_has_no_mcp_at_all`](test_swebench_ab.py#L173) -- The CLI arm's whole point is that MCP is ABSENT.
- [`test_cli_and_mcp_steering_teach_the_same_routes`](test_swebench_ab.py#L201) -- Arm isolation again: the two prism arms must differ in SURFACE, not in
- [`test_tool_calls_capture_mcp_arguments`](test_swebench_ab.py#L212) -- parse_stream must keep MCP tool ARGUMENTS, not just names.
- [`test_clip_keeps_lists_but_bounds_strings`](test_swebench_ab.py#L231) -- Clip keeps lists but bounds strings.

### `test_wide_score.py` (11 tests)

Unit tests for the wide-bed site scorer -- synthetic diffs, no git.

Run: cd research/harness && python -m pytest -p no:asyncio -p no:pytest_asyncio tests/test_wide_score.py -q

- [`test_gold_against_itself_is_perfect`](test_wide_score.py#L41) -- Gold against itself is perfect.
- [`test_one_of_two_sites_in_a_file_is_half`](test_wide_score.py#L47) -- One of two sites in a file is half.
- [`test_todo_in_place_of_the_change_is_not_exact`](test_wide_score.py#L55) -- Todo in place of the change is not exact.
- [`test_equivalent_but_textually_different_replacement_is_substituted`](test_wide_score.py#L68) -- Equivalent but textually different replacement is substituted.
- [`test_touching_the_file_elsewhere_is_missed`](test_wide_score.py#L78) -- Touching the file elsewhere is missed.
- [`test_wrong_place_in_right_file_costs_precision`](test_wide_score.py#L84) -- Wrong place in right file costs precision.
- [`test_files_complete_requires_every_site_in_the_file`](test_wide_score.py#L99) -- Files complete requires every site in the file.
- [`test_clean_sweep_has_full_site_precision`](test_wide_score.py#L109) -- Clean sweep has full site precision.
- [`test_u3_context_diff_agrees_with_u0`](test_wide_score.py#L114) -- U3 context diff agrees with u0.
- [`test_whitespace_differences_do_not_matter`](test_wide_score.py#L126) -- Whitespace differences do not matter.
- [`test_symbol_only_in_context_line_does_not_count`](test_wide_score.py#L137) -- Symbol only in context line does not count.

