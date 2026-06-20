# Splunk (Emulated) — SplunkPy command validation

These artifacts validate that the Splunk mimic answers the Cortex XSOAR
**SplunkPy** integration's command surface. They are **not** shipped in the
mimic image (the Dockerfile only copies `src/` + `requirements.txt`).

## Scope

Only SplunkPy commands that use the **splunkd REST API** the mimic emulates are
in scope. Out of scope (operator decision — handled separately):

- **HEC** (`splunk-submit-event-hec`) — the HTTP Event Collector is a separate
  listener/token, not the management REST API.
- **KV-store data** ops and **ES notable mirroring** beyond a stub ack — these
  need a stateful KV store / Enterprise Security app, not the bare REST API.

## How the REST-API commands are validated

The authoritative proof is **driving the mimic with the real `splunklib` SDK
exactly as SplunkPy does**, asserted in `tests/test_server.py` (the
`test_splunklib_*_roundtrip` tests). Covered, all green:

| SplunkPy command | splunklib call | splunkd route |
|---|---|---|
| `splunk-search` (oneshot) | `service.jobs.oneshot(q)` | `POST search/jobs` (oneshot) |
| `splunk-search` (create→poll→results) | `service.jobs.create(q)` → `job.results()` | `search/jobs` + `/{sid}` + `/results` |
| `splunk-job-create` / `splunk-results` / `splunk-job-status` | `service.jobs.create` / `service.job(sid).results()` / `job['dispatchState']` | `search/jobs/{sid}*` |
| `splunk-job-share` | `job.set_ttl()` + ACL `POST` | `search/jobs/{sid}` + `/{sid}/acl` |
| `splunk-get-indexes` | `| rest .../data/indexes` oneshot **and** `service.indexes` | `data/indexes` (+ `/{name}`) |
| `splunk-submit-event` | `service.indexes[name].submit(...)` | `data/indexes/{name}` + `receivers/simple` |
| `splunk-update-notable-events` | `service.post('notable_update', ...)` | `notable_update` (stub ack) |

## End-to-end playbook proof

`splunk_notable_triage_mimic.yml` is a **mimic-safe** playbook whose every
automation task maps to a supported REST-API command (job-create → results,
get-indexes). Live flow:

1. `xsoar_import_playbook` the YAML onto the xsoar-v6 tenant (SplunkPy points at
   the mimic).
2. Pick a fetched **Splunk Notable** incident → `xsoar_run_playbook(incident_id,
   "Splunk Notable Triage (mimic-safe)")`.
3. Poll `xsoar_get_playbook_state(incident_id)` until `overall_state` is
   `Completed`; assert `ran_to_success` is true and `failed_tasks` is empty.

> Do **not** add tasks using `splunk-submit-event` / `splunk-update-notable-events`
> to the success criteria — the mimic stub-acks them (they go green without
> proving anything). `splunk-submit-event` also requires `index=main` (only
> `main`/`notable`/`_internal` exist).
