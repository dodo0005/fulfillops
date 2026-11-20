# E19 - rolling update with continuous probe
- Change: API pod annotation fulfillops/release 5 -> 6 (PR b/rollout-6), deployed by Argo CD from main
- Probe: 961 samples every 0.25 s, 17:51:10 to 17:55:10 UTC, 0 failures (docs/rolling_update_probe.csv)
- New ReplicaSet fulfillops-api-6c9f776fcd created 17:51:24 UTC, inside the probe window
- Strategy: RollingUpdate maxSurge 1, maxUnavailable 0, minReadySeconds 5, readiness on /health/ready
## Argo CD revisions (before / after)
0eb4a3ca58c22ca0747cb22d1f036f3ac82a0207 2026-11-20T17:47:23Z
751f5c059b9cbc4d69382e46ebe9e1d1107054c0 2026-11-20T17:51:24Z
## Rollout history
deployment.apps/fulfillops-api 
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
3         <none>
4         <none>
5         <none>
6         <none>

