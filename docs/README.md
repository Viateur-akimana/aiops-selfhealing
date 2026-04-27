# TechStream AIOps - Self-Healing Observability System

## Overview

TechStream's AIOps platform reduces **Mean Time To Resolution (MTTR)** by combining Golden Signal monitoring, chaos engineering, automated self-healing, and AI-powered root cause analysis. The system detects anomalies autonomously and remediates them before paging an engineer.

---

## Architecture

```
+---------------------------------------------------------------------+
|                         TechStream AIOps                             |
|  +--------------+    +----------------+    +----------------------+  |
|  |  Web App     |<---|  Load Gen /    |    |   Chaos Script       |  |
|  |  (Flask)     |    |  Real Traffic  |    |   (Error/CPU/        |  |
|  |  :5000       |    +----------------+    |    Latency inject)   |  |
|  +------+-------+                          +----------+-----------+  |
|         | scrape                                       | POST /chaos  |
|         v                                             |              |
|  +--------------+    alert_rules.yml                 |              |
|  |  Prometheus  |-------------------------------------->             |
|  |  :9090       |                                                    |
|  +------+-------+                                                    |
|         | alerts                                                      |
|         v                                                             |
|  +--------------+    webhook                  +------------------+   |
|  | AlertManager |----------------------------->  Remediation     |   |
|  |  :9093       |                             |  Service :8085   |   |
|  +--------------+                             |  + AI Analyzer   |   |
|  +--------------+                             |    :9000         |   |
|  |  Grafana     |<-- PromQL                   +------------------+   |
|  |  :3000       |                                                    |
|  +--------------+                                                    |
+---------------------------------------------------------------------+
```

### AWS Equivalent Mapping

| Local Component | AWS Equivalent |
|---|---|
| Flask App | ECS Fargate service |
| Prometheus + AlertManager | CloudWatch Alarms |
| AlertManager webhook | EventBridge rule -> Lambda |
| Remediation Service | Lambda Function / SSM Run Command |
| AI Analyzer | Amazon DevOps Guru |
| Grafana | CloudWatch Dashboards |

---

## Golden Signals

| Signal | Alert Threshold | PromQL |
|---|---|---|
| **Latency** P95 | > 1 s | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| **Traffic** | < 0.1 rps drop | `sum(rate(http_requests_total[1m]))` |
| **Errors** | > 5% | `rate(http_errors_total[2m]) / rate(http_requests_total[2m])` |
| **Saturation** CPU | > 80% | `cpu_saturation_percent` |

SLOs: Availability > 99.9% | Error rate < 1% | P95 latency < 500 ms | CPU < 70% sustained

---

## Quick Start

**Prerequisites:** Docker Engine >= 24.0, Docker Compose >= 2.24

```bash
make up
```

| Service | URL | Credentials |
|---|---|---|
| Grafana | http://localhost:3000 | admin / techstream |
| Prometheus | http://localhost:9090 | - |
| AlertManager | http://localhost:9093 | - |
| App | http://localhost:5000 | - |
| Remediation API | http://localhost:8085 | - |
| AI Analyzer API | http://localhost:9000 | - |

---

## Incident Simulation

```bash
make health          # verify baseline - all services ok
make chaos-full      # inject errors + latency + CPU spike simultaneously
make incidents       # view self-healing audit log
make analysis        # view AI root cause analysis
make chaos-reset     # restore normal state
```

**Automated sequence after `chaos-full`:**
```
T+0s   80% requests return HTTP 500, latency +2s, CPU spikes
T+30s  HighErrorRate alert fires in Prometheus
T+35s  AlertManager routes alert to Remediation webhook
T+36s  Remediation Service stops chaos automatically
T+37s  AI Analyzer identifies root cause (confidence 0.97)
T+60s  Error rate returns to ~0% in Grafana
T+90s  Alert resolves in AlertManager
```

---

## File Structure

```
AIops/
+-- docker-compose.yml       # Full stack (9 services)
+-- Makefile                 # Operational shortcuts
+-- app/                     # Flask app + chaos endpoints + /metrics
+-- prometheus/              # Scrape config + 9 alert rules
+-- alertmanager/            # Alert routing -> remediation webhook
+-- grafana/                 # Golden Signals + Incident Timeline dashboards
+-- remediation/             # Self-healing webhook handler
+-- ai_analyzer/             # Root cause analysis (DevOps Guru equivalent)
+-- chaos/                   # Chaos injection scripts
+-- load_gen/                # Background traffic generator
+-- lambda_code/             # AWS Lambda remediation functions
+-- terraform/               # AWS infrastructure as code (ECS, ALB, Lambda, SNS)
+-- screenshoots/            # Lab evidence screenshots
+-- docs/README.md
```

---

## Screenshots

All screenshots are in the [`screenshoots/`](../screenshoots/) folder.

---

### 1. Local Stack - Application Running

**Web app responding at `localhost:5000`**

![Web app root endpoint](../screenshoots/Screenshot%20from%202026-04-27%2010-32-21.png)

The Flask application returns `{"service": "TechStream", "status": "ok", "version": "1.0.0"}`.

---

**App health endpoint at `localhost:5000/health`**

![App health endpoint](../screenshoots/Screenshot%20from%202026-04-27%2010-32-46.png)

The `/health` endpoint reports `status: healthy` with chaos state flags (all false at baseline), CPU at 40.2%, memory at 82.6%.

---

**Raw Prometheus metrics at `localhost:5000/metrics`**

![Prometheus metrics endpoint](../screenshoots/Screenshot%20from%202026-04-27%2010-33-11.png)

The `/metrics` endpoint exposes all Golden Signal counters and histograms in Prometheus text format.

---

**Prometheus API confirming all targets up**

![Prometheus query up](../screenshoots/Screenshot%20from%202026-04-27%2010-41-18.png)

`/api/v1/query?query=up` returns value `"1"` for all instances: `techstream-web`, `node_exporter:9100`, `cadvisor:8080`, and `prometheus`.

---

### 2. Golden Signal Monitoring

**Prometheus scrape targets - all UP**

![Prometheus targets](../screenshoots/Screenshot%20from%202026-04-27%2010-34-24.png)

All four scrape targets — cadvisor, node_exporter, prometheus, techstream_app — are **UP**.

---

**Prometheus alert rules loaded**

![Prometheus alert rules](../screenshoots/Screenshot%20from%202026-04-27%2010-34-52.png)

All 9 Golden Signal rules loaded from `alert_rules.yml` — `HighErrorRate`, `HighLatencyP95`, `HighCPUSaturation`, `ServiceDown`, and others — all **Inactive** at baseline.

---

### 3. Grafana Dashboards

**Golden Signals dashboard - all four panels**

![Grafana Golden Signals dashboard](../screenshoots/Screenshot%20from%202026-04-27%2010-38-25.png)

Service Status: **HEALTHY**. Error Rate ~0%, Latency P50/P95/P99 within SLO, steady traffic, CPU saturation normal.

---

**Incident Timeline dashboard**

![Grafana Incident Timeline dashboard](../screenshoots/Screenshot%20from%202026-04-27%2010-38-47.png)

Active Alerts Count = **0** at baseline. Alert State Over Time and all four Golden Signals overlaid show normal operation.

---

### 4. Automated Remediation

**Remediation service incident log at `localhost:8085/incidents`**

![Remediation incidents log](../screenshoots/Screenshot%20from%202026-04-27%2010-40-03.png)

The audit log shows the complete self-healing sequence: `action_stop_latency_chaos` with result `SUCCESS` and `auto_resolved` entries for `HighLatencyP95` and `ServiceDown` — automated resolution with no human intervention.

---

### 5. AWS Deployment

**AWS ECR - Docker image repositories pushed**

![AWS ECR repositories](../screenshoots/Screenshot%20from%202026-04-27%2011-14-23.png)

Three private ECR repositories created by Terraform: `techstream-web-app`, `techstream-remediation`, `techstream-analyzer`.

---

**Terraform apply output - all AWS resources deployed**

![Terraform deployment output](../screenshoots/Screenshot%20from%202026-04-27%2012-38-54.png)

`terraform apply` completed with all output values: CloudWatch dashboard URL, ALB URL, ECS cluster name, Lambda ARNs.

---

**AWS Application Load Balancer - active**

![AWS ALB](../screenshoots/Screenshot%20from%202026-04-27%2012-55-29.png)

`techstream-alb` in **Active** state, Internet-facing, deployed across multiple Availability Zones.

---

**AWS ECS Cluster - all services running**

![AWS ECS Cluster](../screenshoots/Screenshot%20from%202026-04-27%2012-59-10.png)

Cluster `techstream-cluster` **ACTIVE** with three Fargate services running: analyzer, remediation, and web app.

---

**AWS Lambda - remediation functions deployed**

![AWS Lambda functions](../screenshoots/Screenshot%20from%202026-04-27%2012-59-53.png)

`techstream-auto-restart` and `techstream-scale-out` Lambda functions deployed — the AWS equivalent of the local remediation service.

---

**AWS SNS - alert notification topics**

![AWS SNS topics](../screenshoots/Screenshot%20from%202026-04-27%2013-01-18.png)

`techstream-alerts` and `techstream-devops-guru_insights` SNS topics — the AWS equivalent of AlertManager webhook routing.

---

**AWS CloudWatch - alarms firing**

![AWS CloudWatch alarms](../screenshoots/Screenshot%20from%202026-04-27%2013-59-08.png)

CloudWatch alarms `techstream-low-traffic` and `techstream-high-latency` in **ALARM** state, confirming the AWS alerting pipeline fires under the same conditions as local Prometheus rules.

---

**AWS CloudWatch - ECS Cluster monitoring dashboard**

![AWS CloudWatch ECS dashboard](../screenshoots/Screenshot%20from%202026-04-27%2014-03-06.png)

Live ECS cluster metrics: CPU, Memory, Disk, Network, Container count, Task count, Service count — the AWS equivalent of the Grafana Golden Signals dashboard.
