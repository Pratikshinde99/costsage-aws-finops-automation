# CostSage AWS

## Serverless FinOps Automation Platform for AWS Cost Governance and Optimization

CostSage AWS is a **serverless FinOps automation system** designed to monitor AWS environments, detect cost anomalies, identify unused resources, enforce tagging compliance, and generate actionable cost optimization insights.

The system runs automatically on a daily schedule and provides engineers and teams with alerts, reports, and dashboards that help prevent unexpected cloud bills and improve governance.

CostSage AWS is implemented using **production-grade cloud engineering practices**, including infrastructure-as-code, idempotent execution, retry handling, CI/CD pipelines, secret management, and secure dashboard delivery.

---

# Live Demo

**Dashboard**

https://dmswkcszk7esj.cloudfront.net

**Latest Daily Cost Report (JSON)**

https://dmswkcszk7esj.cloudfront.net/daily/latest/report.json

---

# Project Overview

Modern cloud environments frequently accumulate hidden inefficiencies such as:

* unused resources
* inconsistent tagging
* cost spikes from misconfigured services

Manual monitoring of cloud cost and governance becomes difficult as environments scale.

CostSage AWS solves this problem by running automated daily analysis that:

* analyzes cloud spending
* detects anomalies
* identifies unused resources
* validates governance policies
* estimates potential savings

Results are published as reports, alerts, and an interactive dashboard.

---

# Key Features

## Automated Daily Cost Analysis

The system automatically analyzes AWS cost data every day using Cost Explorer.

Metrics analyzed include:

* yesterday’s total spend
* 7-day average cost
* month-to-date usage
* top services contributing to cost changes

---

## Cost Anomaly Detection

Cost spikes are detected using a configurable threshold algorithm.

Example logic:

```
If yesterday_cost > (7_day_average × threshold_multiplier)
→ trigger anomaly alert
```

Default multiplier: **1.30**

This helps teams detect abnormal spending early.

---

## Waste Resource Detection

CostSage scans AWS infrastructure to detect common sources of waste.

Detected resources include:

* stopped EC2 instances
* unattached EBS volumes
* old snapshots
* optional inactive load balancers

Each finding includes estimated monthly cost impact.

---

## Tag Governance Compliance

CostSage validates tagging compliance for required governance tags:

* Owner
* Project
* Environment

Resources missing required tags are flagged in reports and alerts.

This helps maintain accountability and cost attribution.

---

## Savings Estimation

For each waste resource detected, the system calculates estimated monthly savings.

Example output:

```
Stopped EC2 instance → Save $42/month
Unattached EBS volume → Save $9/month
Old snapshot → Save $3/month

Total potential savings → $118/month
```

---

## Alerting and Notifications

Important events automatically trigger alerts.

Notifications are delivered through:

* Slack webhook alerts
* Email alerts using SNS

Alert messages include:

* anomaly detection results
* top cost increases
* potential savings
* governance violations

---

## Daily Reports

Each execution generates reports in multiple formats:

* JSON (dashboard feed)
* HTML (human readable summary)
* CSV (analysis friendly format)

Reports are stored using immutable run paths for auditability.

Example storage structure:

```
daily/
  2026-03-07/
    report.json
    report.html
    report.csv

  latest/
    report.json
```

---

## Interactive Dashboard

A lightweight React dashboard visualizes cost insights.

Dashboard components include:

* total cost metrics
* anomaly indicators
* top services by cost
* waste resources table
* estimated savings

The dashboard automatically refreshes every five minutes.

---

# Architecture Overview

CostSage AWS uses a **serverless event-driven architecture** designed for low cost, scalability, and operational simplicity.

Core components include:

Compute
AWS Lambda (Python runtime)

Scheduling
Amazon EventBridge

Storage
Amazon S3 (report storage)
Amazon DynamoDB (trend tracking)

Alerting
Amazon SNS
Slack Webhook

Monitoring
Amazon CloudWatch Logs
CloudWatch Alarms
SQS Dead Letter Queue

Frontend
React + Vite dashboard

Delivery
CloudFront with Origin Access Control

Infrastructure
AWS SAM (Infrastructure as Code)

---

# Technology Stack

## Backend

Python 3.11
boto3 / botocore

---

## Frontend

React 18
Vite
Recharts

---

## DevOps and Quality

AWS SAM
GitHub Actions CI/CD
pytest
ruff (linting)
pre-commit hooks
detect-secrets

---

# Repository Structure

```
CostSage-AWS/
│
├── costsage/                      # Lambda backend modules
│
├── dashboard/                     # React dashboard
│
├── tests/                         # Unit tests
│
├── config/                        # SAM parameter configuration
│
├── .github/workflows/deploy.yml   # CI/CD pipeline
│
├── template.yaml                  # Infrastructure (AWS SAM)
│
├── samconfig.toml                 # Deployment configuration
│
├── DEPLOYMENT.md                  # Deployment guide
│
└── README.md
```

---

# Local Development

## Prerequisites

Python 3.11+
Node.js 18+
AWS CLI configured
AWS SAM CLI installed

---

## Backend Setup

Create virtual environment

```
python -m venv .venv
```

Activate environment (Windows)

```
.venv\Scripts\activate
```

Install dependencies

```
pip install -r costsage/requirements.txt -r requirements-dev.txt
```

Run tests

```
pytest -q
```

---

## Frontend Setup

```
cd dashboard
npm install
npm run dev
```

---

# Deployment

Build infrastructure

```
sam build
```

Deploy stack

```
sam deploy --config-env prod
```

Full deployment instructions are available in **DEPLOYMENT.md**.

---

# Dashboard Publishing

```
cd dashboard
npm run build
aws s3 sync dist/ s3://<dashboard-bucket> --delete --exclude "daily/*"
aws cloudfront create-invalidation --distribution-id <distribution-id> --paths "/*"
```

---

# Reliability and Operations

CostSage AWS includes multiple production-grade safeguards:

* idempotent daily execution lock
* exponential backoff retry logic for AWS APIs
* dead letter queue for failed executions
* CloudWatch alarms for runtime failures
* structured JSON logging with execution IDs

These safeguards ensure consistent daily execution.

---

# Security

Security best practices implemented:

* least privilege IAM access
* secrets stored in AWS Secrets Manager
* private S3 dashboard bucket
* CloudFront Origin Access Control
* repository secret scanning

---

# CI/CD Pipeline

The project includes a GitHub Actions pipeline.

Pipeline stages:

1. linting
2. unit tests
3. SAM validation
4. build verification
5. manual environment deployment

Deployment uses secure **OIDC-based AWS authentication**.

---

# Data Interpretation Notes

If dashboard cost values appear as **0.00**, this typically indicates:

* minimal billable usage
* Cost Explorer reporting delay

Execution health can still be verified through:

* report timestamps
* DynamoDB trend records
* immutable run history

---

# Future Enhancements

Possible improvements include:

* multi-account scanning using AWS Organizations
* automated remediation of unused resources
* historical cost trend visualization
* AI-based cost optimization recommendations

---

# Author

Pratik Shinde

GitHub
https://github.com/<your-username>

LinkedIn
https://www.linkedin.com/in/<your-linkedin-id>

---

# License

This project is provided for educational and demonstration purposes.
