You are auditing the ev-apm-agent repository at the current commit. Produce a written status report for the human maintainers covering the sections below. Do not modify any files. Do not run destructive commands. You may read files, run tests, execute `git log`, `git diff`, and `grep`, and run `make verify` or the equivalent test scripts if present.

Ground rules:
- Every claim must be traceable to a file, commit, test result, or command output. Cite paths and line ranges.
- If a section has nothing to report, write "None observed" rather than inventing content.
- If evidence is missing, say so plainly. Do not guess.
- Do not restate the project brief. Assume the reader knows it.


Produce the report in this exact structure:

## 1. Executive Summary
Three to five sentences. What is the current state of the repo relative to FINALS_EXIT_CRITERIA.md. Which hard gates are green, which are at risk, which are red. One-sentence recommendation.

## 2. Datasets Discovered
List every dataset present under data/ (raw, interim, processed, reference, sql). For each: filename, row count, columns, whether it is gitignored or committed, and which downstream module consumes it. Flag any dataset referenced in code but missing from disk, or present on disk but never consumed.

## 3. Knowledge Graph / Cross-Reference Search Results
Run grep/rg across the repo for the following anchor terms and report where each is defined vs. referenced. Flag orphans (defined but never referenced) and dangling references (referenced but never defined):
- err1051, err1024, WeakSignal, GroundFailure, UnderVoltage, OverVoltage
- Err1051Detector, Err1024Detector, TelemetrySilenceDetector, AlertPrioritizer, SessionFeatureExtractor, Layer2Anomaly, HealthRollup, VendorCodeNormalizer
- priority_tier, deciding_signal, likely_root_cause, recommended_action, impact_class, confidence, health_state
- P1, P2, P3

## 4. Files Modified (since last tag)
`git log --stat` from the most recent version tag to HEAD. Summarize which files changed, grouped by module (detector/, replay/, ui/, docs/, tests/, data/). Note any file that was renamed or deleted.

## 5. Code Changes Made
For each meaningful change since the last tag, in commit order:
- Commit hash (short), commit message, author
- What changed in prose (do not paste diffs)
- Which SPEC.md section or FINALS_EXIT_CRITERIA.md gate it addresses
- Whether tests were added or updated for the change

## 6. Data Pipeline Updates
Trace the end-to-end path: CSV export → replay harness → detector → prioritizer → UI. For each stage, note the current file, the input schema, the output schema, and whether the stage has tests. Flag any schema mismatch between stages.

## NOTE: 

1) Master_AI_Training_Matrix_Telemetry_Raw_Data.csv contains temperature data.
2) final_ai_training_matrix_1051.csv contains Connector 2036074 err10151 Full evidence.

## 7. UI Improvements
Inspect ui/main.py and any templates/static assets. Report:
- Current UI surfaces (summary header, alert feed, drift panel, health rollup, category coverage)
- Which fields each alert row displays
- Whether priority tier colors are implemented (P1 red / P2 amber / P3 grey)
- Whether deciding_signal text is rendered as plain English
- Any UI element referenced in demo_script.md that is not present in the code

## 8. Power Curve Removal Details
Search the repo for all references to CC-CV, power curve, taper slope, cc_cv_*, power_curve_*. For each reference, report whether it is:
- Live code still in use
- Documentation still referring to it
- Test still asserting on it
- Dead code awaiting removal
If a decision to remove power-curve features was made, verify it was applied consistently across code, tests, docs, and deck. If inconsistent, list the specific files still referencing it.

## 9. Bugs Identified and Fixed
List bugs closed in the recent commit range with commit hash and fix summary. Separately, list any TODO, FIXME, XXX, or HACK comments still present in the codebase with file and line number. Flag any test currently marked skip, xfail, or disabled.

## 10. Validation and Testing Performed
Run the test suite. Report:
- Total tests, passed, failed, skipped
- Coverage per module if measurable
- Which FINALS_EXIT_CRITERIA hard gates have automated test coverage and which rely on manual review
- Any test that passes but does not actually assert on the behavior it claims to test (look for tests that only check `assert x is not None` on complex behavior)

Then run `docker compose config` and `docker compose up -d` on a scratch environment if safe. Report whether the cold-start UI check passes.

## 11. Exit Criteria Verification Table
Reproduce every hard gate from FINALS_EXIT_CRITERIA.md Section 2 as a table:
| Gate ID | Description | Status (Green / At Risk / Red) | Evidence (file:line or command output) | Blocker if not green |

Then the same table for soft gates (Section 3).


## 12. Remaining Limitations
Honest list of what the system cannot do that a judge might reasonably ask about. Distinguish between:
- Scope-boundary limitations (deliberately out of scope, defensible)
- Data limitations (no lead-time signal on labeled faults, only 2 fault labels historically, etc.)
- Time-budget limitations (would be built with more days)

## 13. Risks
Ranked list of risks to finals qualification. For each: description, likelihood (High/Med/Low), impact, and mitigation available before submission. Reference the anti-goals from FINALS_EXIT_CRITERIA.md Section 10.

## 14. Recommendations
Specific actions the maintainers should take in the next 24–72 hours before submission, ranked by impact. Each recommendation must be actionable (name the file to change, the test to add, the number to verify), not general advice.

## 15. Overall Project Readiness Assessment
One paragraph. Given the state of hard gates, soft gates, and deliverables, is the project ready to submit for finals? If not, what is the smallest additional work required to reach ready. If yes, what is the strongest and weakest part of the submission.

## 16. Suggested Next Steps Before Finalist Submission
Ordered checklist, up to 15 items. Each item: what to do, who should do it (Abhishek / Akhil / Joint), and estimated time. Sequence for a 2-day pre-submission runway. Terminal item is "submit."

Formatting: use headers as shown above. Prose over bullets except in Sections 11 and 16. No emojis. No summaries at the end of each section beyond what is asked. Do not include a preamble or a closing paragraph outside the numbered sections.