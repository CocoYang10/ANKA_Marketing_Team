# Schedule the weekly ANKA Agent pipeline

## What scheduling means

The pipeline is already one command. Scheduling means a private job runner calls
that command every Monday after the previous Monday-Sunday period is complete.
It does not make the Agent continuously monitor or spend money.

Recommended schedule: **Monday 08:00 America/New_York**.

The job performs:

1. pull GA4, Meta and MailerLite for the exact completed week;
2. stop on connector failure rather than substituting zero;
3. validate and build the aggregate snapshot;
4. generate/update the Action Registry;
5. evaluate due verification checks;
6. write a manifest that records success or the failed stage.

## V1 deployment boundary

`backend/Dockerfile.job` packages the private weekly runner. Do not deploy it
until these are confirmed:

- Google Cloud project and region;
- private service account;
- Secret Manager entries for source credentials;
- persistent `/data` storage for the reviewed snapshot and action state;
- who receives a failed-job alert.

The API service and scheduled job must share the reviewed snapshot and Action
Registry. GitHub Pages must not be that storage layer.

## Cloud Run + Cloud Scheduler setup

1. Build `backend/Dockerfile.job` with `marketing/` as the build context.
2. Deploy the image as one Cloud Run Job with one task, bounded retries and a
   service account that can read only the required secrets/storage.
3. Run it once manually and confirm the manifest, snapshot and Action Registry.
4. In the Cloud Run Job **Triggers** tab, add a Cloud Scheduler trigger.
5. Set cron to `0 8 * * 1` and timezone to `America/New_York`.
6. Use a Scheduler service account with permission to invoke only this job.
7. Force one controlled connector failure and verify that the run fails and the
   latest valid snapshot remains available.

Official references:

- https://cloud.google.com/run/docs/create-jobs
- https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule

## Local/manual fallback

Until the cloud project and shared storage are approved, run:

```bash
.venv/bin/python run_weekly_pipeline.py
```

This produces the same evidence and verification flow, but it is not considered
a production schedule because it depends on a person and a laptop.
