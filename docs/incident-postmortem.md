# Postmortem: broken API release halted by readiness, recovered by Git revert

- **Date:** 2026-11-20
- **Environment:** kind cluster `fulfillops`, deployed by Argo CD from `main`
- **Type:** planned failure drill (hard gate 3), written up as a real incident
- **Severity:** none for users (no failed requests, no lost orders); the release was blocked
- **Duration:** 8 min 44 s from the bad merge (18:20:21 UTC) to Argo CD back to Healthy (18:29:05 UTC)
- **Evidence:** `docs/evidence/E20-broken-rollout.log`, `E20-broken-rollout.md`, `E20-probe-broken.csv`
- **Format:** blameless. The question is what let the change through, not who made it.

## Summary

A one-line change to `infra/k8s/api.yaml` pointed the API readiness probe at `/health/broken`, a
path the application does not serve. Argo CD synced it from `main` and Kubernetes started a
rolling update. The new pod never became Ready, so it never received traffic and never replaced
an old pod. After 90 s the Deployment reported `ProgressDeadlineExceeded` and Argo CD showed
`Degraded`. The two old pods kept serving the whole time: 961 out of 961 probe requests returned
200. A `git revert` of the change, merged as a normal PR, restored the previous manifest, and Argo
CD returned to `Synced / Healthy`. No manual `kubectl` change was made.

## Impact

- **Users:** none. Readiness probe through the NodePort: 961 requests over 240 s
  (18:20:50–18:24:50 UTC), **961 × HTTP 200, 0 failures**.
- **Orders:** none lost. Order `74079830-8963-45e7-99bc-e824082a9867`, created before the drill,
  stayed `completed`; the count of completed orders was 1 before, during and after.
- **Delivery:** the release was blocked; any further deploy would have queued behind the failed
  rollout until the revert.

## Timeline (UTC)

| Time | Event |
| --- | --- |
| 18:14:10 | Baseline: Argo CD `Synced / Healthy` on `751f5c0`; ReplicaSet `fulfillops-api-6c9f776fcd` serving; `/health/ready` → 200 |
| 18:20:21 | PR #23 merged (`f24ed77`): readiness `path: /health/broken` in `infra/k8s/api.yaml` |
| ≈18:20:41 | Argo CD synced; new ReplicaSet `fulfillops-api-6f885676c4` created one surge pod (`maxSurge: 1`) |
| 18:20:50 | Probe started: `/health/ready` every 0.25 s through the NodePort |
| ≈18:21:26 | New pod `…-vntkk` running; readiness failing with `HTTP probe failed with statuscode: 404` |
| 18:21:29 | Captured: Argo CD `Synced / Progressing`; Deployment `Progressing=True, ReplicaSetUpdated`; both old pods still Ready |
| ≈18:22 | `progressDeadlineSeconds: 90` passed without progress |
| 18:24:50 | Probe ended: 961/961 HTTP 200 |
| 18:26:04 | Captured: Deployment `Progressing=False, ProgressDeadlineExceeded`; Argo CD `Synced / Degraded`; old ReplicaSet still serving |
| 18:28:55 | PR #24 merged (`fd4a976`): `git revert -m 1 f24ed77` |
| 18:29:05 | Captured: Argo CD `Synced / Healthy` on `fd4a976`; broken ReplicaSet scaled to 0; `NewReplicaSetAvailable`; completed orders still 1 |

Times marked ≈ are derived from the age of Kubernetes events in the 18:21:29 capture.

## Detection

- **Kubernetes:** readiness probe failures on the new pod (`404`), then the Deployment condition
  `ProgressDeadlineExceeded` 90 s into the rollout.
- **Argo CD:** application health `Degraded` while sync status stayed `Synced`. `Synced` only means
  the cluster matches Git; health is what showed that Git itself was wrong.
- **Users:** nothing to detect. The readiness gate meant the bad pod was never in the Service.

## Root cause

The readiness `path` in the API Deployment referenced an endpoint the application does not
implement. Nothing between the commit and the cluster checks that the probe paths in
`infra/k8s/` match the routes in `api/`:

- CI builds and tests the application and its image, but does not validate the Kubernetes
  manifests or deploy them anywhere before merge.
- Review looked at a one-line YAML diff, which is easy to approve without running it.

## What limited the damage

| Control | Effect |
| --- | --- |
| `readinessProbe` on `/health/ready` | The new pod never joined the Service, so no request reached it |
| `maxUnavailable: 0`, `maxSurge: 1` | No old pod was removed before a new one was available, so capacity never dropped |
| `minReadySeconds: 5` | A pod has to stay Ready for 5 s before it counts, so a flapping pod cannot replace an old one |
| `progressDeadlineSeconds: 90` | Turned "stuck" into an explicit failed condition within 90 s |
| Orders in Postgres | The rollout only touched API pods; committed data was never at risk |
| GitOps with self-heal | The fix had to go through Git; a `kubectl` patch would have been reverted and Git would still have said "broken" |

## Resolution

We rolled back with `git revert -m 1 f24ed77`, merged as PR #24. Argo CD applied it like any other
commit, Kubernetes scaled the broken ReplicaSet to 0, and the application was back to `Healthy`
within 10 s of the merge.

**Why rollback and not fix-forward:** the last good revision was known, the bad change was
configuration only (no schema migration to undo), and a revert is one reviewed commit that keeps
Git as the source of truth. Fix-forward is the better choice when a release contains a migration
that cannot be undone, or when the fix is small and already tested.

## Action items

| # | Action | Type | Owner |
| --- | --- | --- | --- |
| 1 | CI check that every `httpGet.path` in `infra/k8s/*.yaml` is a route the API serves (a small script comparing the manifests with the FastAPI routes) | Prevent | Person B |
| 2 | Validate manifests in CI (`kustomize build infra/k8s` + schema validation such as kubeconform) | Prevent | Person B |
| 3 | Deploy each PR to a throwaway kind cluster in CI and wait for `kubectl rollout status` before merge | Prevent | Person B |
| 4 | Argo CD notification when an application turns `Degraded`, so detection does not depend on someone watching | Detect | Person B |
| 5 | Short runbook in the README: symptoms (`0/1 Ready`, `ProgressDeadlineExceeded`, `Degraded`), first commands (`kubectl describe pod`, `kubectl get events --sort-by=.lastTimestamp`), fix by `git revert` | Respond | Person A |
| 6 | Record `kubernetes.io/change-cause` on releases so `kubectl rollout history` shows what each revision was (currently `<none>`) | Respond | Person B |

## What went well

- The safety settings did exactly what they were designed for: zero user impact.
- The failure was visible in three places (pod events, Deployment conditions, Argo CD health).
- Recovery used the normal delivery path, a PR, with no special access.

## What we learned

- `Synced` is not `Healthy`. GitOps guarantees the cluster matches Git, not that Git is correct.
- Readiness is the real release gate. A wrong probe blocks the rollout safely; a missing probe
  would have sent traffic to a broken pod.
- Configuration needs tests too. A one-line YAML change got through every application check.
