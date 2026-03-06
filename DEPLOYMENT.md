# CostSage AWS Deployment Runbook

## 1) Prerequisites
- AWS CLI configured (`aws configure`)
- AWS SAM CLI installed
- Python 3.11+
- Node.js 18+
- Existing S3 report bucket with SSE enabled
- Existing SNS topic with email subscription confirmed
- Secrets Manager secret for Slack webhook (`webhook_url` JSON or plain URL)

## 2) Deploy Backend (SAM)
From repository root:

```bash
sam build
sam deploy --guided
```

After initial values are set in `samconfig.toml`, use one-command deploys:

```bash
sam build
sam deploy --config-env dev
```

```bash
sam build
sam deploy --config-env prod
```

Parameter templates are provided in:
- `config/dev.parameter-overrides.txt`
- `config/prod.parameter-overrides.txt`

Use them as your source of truth when updating `parameter_overrides` inside `samconfig.toml`.

Use these key guided values:
- `ReportBucketName`: your report bucket
- `SnsTopicArn`: alert topic ARN
- `SlackWebhookSecretName`: secret name storing webhook URL
- `ScheduleExpression`: default is `cron(0 9 * * ? *)`

This deploys:
- Lambda `costsage-engine-*`
- EventBridge daily trigger
- DynamoDB table `CostTrends`
- SQS DLQ
- CloudWatch alarms (Errors/Throttles/Duration)

## 3) Validate Backend
- Invoke once manually:

```bash
aws lambda invoke --function-name <function-name> out.json
```

- Check CloudWatch logs for successful completion.
- Confirm S3 objects exist under:
  - `daily/<YYYY-MM-DD>/report.json`
  - `daily/latest/report.json`
- Confirm DynamoDB row exists for current date.
- Confirm Slack and SNS email alerts when thresholds are triggered.

## 4) Deploy Dashboard to S3 Static Hosting
Inside `dashboard/`:

```bash
npm install
npm run build
aws s3 sync dist/ s3://<dashboard-bucket> --delete --exclude "daily/*"
```

Get dashboard infra outputs from your stack first:

```bash
aws cloudformation describe-stacks --stack-name <stack-name>
```

Use:
- `DashboardBucketName` for the sync target bucket
- `DashboardDistributionDomainName` as the public dashboard URL
- `DashboardDistributionId` for cache invalidation

Set dashboard environment variable before build:
- `VITE_REPORT_JSON_URL=https://<report-bucket>.s3.<region>.amazonaws.com/daily/latest/report.json`

After upload, invalidate CloudFront cache:

```bash
aws cloudfront create-invalidation --distribution-id <dashboard-distribution-id> --paths "/*"
```

Security model:
- Dashboard S3 bucket is private (public access blocked).
- CloudFront serves static files via Origin Access Control.
- Do not enable public bucket policies or public ACLs for dashboard assets.

Important:
- Keep `--exclude "daily/*"` in the sync command. This prevents dashboard deploys from deleting generated report files stored under `daily/`.

## 5) Operations Checklist
- Rotate Slack webhook secret regularly.
- Review DLQ messages daily/weekly.
- Keep pricing overrides updated (`EC2_TYPE_HOURLY_OVERRIDES`).
- Review CloudWatch alarms and tune thresholds as usage scales.
- Re-deploy dashboard after UI updates (`npm run build` + `aws s3 sync`).
