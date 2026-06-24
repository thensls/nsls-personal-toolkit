# Task 11 verification — DEFERRED

End-to-end verification of /harvest-meeting against the synthetic fixture (2026-05-26-slt-sample.md) requires:

1. A fresh Claude Code session where the harvest-meeting skill is loaded at startup (this session built the skill but it's not loadable as a slash command until next session)
2. Interactive user typing `cancel` at the Step 7 approval prompt

Procedure when Kevin runs it (in a future session):

1. Open a new Claude session
2. Stage the fixture again: `bash` the Step 1 Python block from Task 11 of `docs/plans/2026-05-29-kb-harvest.md`
3. Invoke `/harvest-meeting --fathom-url https://fathom.video/share/SYNTHETIC`
4. Inspect the heartbeats (Steps 0-6 should each produce one)
5. At Step 7's approval prompt, expect to see 3 candidates + 1 dropped (per the expected-output table in 2026-05-26-slt-sample.md)
6. Type `cancel` to abort without writing to the KB
7. Paste the actual approval-list output into 2026-05-26-slt-sample-actual-output.md
8. Commit the actual-output file
9. Mark Task 11 complete in the controller's task list

If the actual output deviates materially from expected, debug per task before continuing the rollout.
