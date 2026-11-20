# E20 - broken rollout halted, recovered with git revert

- Break: PR #23 (merge f24ed77) set the API readiness path to /health/broken; Argo CD synced it from main.
- Detection: the new pod stayed 0/1 (readiness 404); after progressDeadlineSeconds 90 the Deployment reported ProgressDeadlineExceeded and Argo CD showed Synced / Degraded.
- User impact: none. maxUnavailable 0 kept both old pods serving; probe on /health/ready via the NodePort: 961/961 HTTP 200 over 240 s (E20-probe-broken.csv).
- Recovery: git revert -m 1 f24ed77 in PR #24 (merge fd4a976). Argo CD synced, the broken ReplicaSet was scaled to 0, back to Synced / Healthy. No manual kubectl patch.
- Orders: order 74079830-8963-45e7-99bc-e824082a9867 created before the drill; completed orders = 1 before, during and after.
- Full captures: E20-broken-rollout.log (before / during / after).

## Rollback vs fix-forward
We rolled back because the last good revision was known and a revert is one reviewed commit that Argo CD applies like any other change, so Git stays the source of truth. Fix-forward is better when the bad release included a database migration that cannot be undone, or when the fix is a small, already-tested change. Here the bad change was configuration only, so reverting was the fastest and lowest-risk option.
