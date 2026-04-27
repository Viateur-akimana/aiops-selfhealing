# TechStream AIOps - Self-Healing Observability System

## Overview

TechStream's AIOps platform reduces **Mean Time To Resolution (MTTR)** by combining Golden Signal monitoring, chaos engineering, automated self-healing, and AI-powered root cause analysis. The system detects anomalies autonomously and remediates them before paging an engineer.

---

## Architecture

```
+---------------------------------------------------------------------+
|                         TechStream AIOps                             |
|                                                                       |
|  +--------------+    +----------------+    +----------------------+  |
|  |  Web App     |<---|  Load Gen /    |    |   Chaos Script       |  |
|  |  (Flask)     |    |  Real Traffic  |    |   (Error/CPU/        |  |
|  |  :5000       |    +----------------+    |    Latency inject)   |  |
|  |  /metrics    |                          +----------+-----------+  |
|  +------+-------+                                     |              |
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
|  +--------------+                             |                  |   |
|                                               |  +-------------+ |   |
|  +--------------+    PromQL queries           |  | AI Analyzer | |   |
|  |  Grafana     | <-----------                |  |  :9000      | |   |
|  |  :3000       |                             |  +-------------+ |   |
|  |  4 Dashboards|                             +------------------+   |
|  +--------------+                                                    |
+---------------------------------------------------------------------+
```

### AWS Equivalent Mapping

| Local Component | AWS Equivalent |
|---|---|
| Flask App + psutil | EC2 / ECS application |
| Prometheus scrape | CloudWatch Agent / custom metrics |
| Prometheus AlertManager | CloudWatch Alarms |
| AlertManager webhook | EventBridge rule -> target |
| Remediation Service | Lambda Function / SSM Run Command |
| AI Analyzer | Amazon DevOps Guru |
| Grafana dashboards | CloudWatch Dashboards |
| node_exporter | CloudWatch Agent (host metrics) |
| cAdvisor | Container Insights |

---

## Golden Signals

Google's SRE book defines four signals that, together, are sufficient to diagnose most production incidents:

| Signal | Metric | Alert Threshold | PromQL |
|---|---|---|---|
| **Latency** | P95 request duration | > 1 s | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| **Traffic** | Requests per second | < 0.1 rps (drop) | `sum(rate(http_requests_total[1m]))` |
| **Errors** | HTTP error rate | > 5% | `rate(http_errors_total[2m]) / rate(http_requests_total[2m])` |
| **Saturation** | CPU utilisation | > 80% | `cpu_saturation_percent` |

---

## Services

### 1. Web Application (`app/app.py`)
- **Framework**: Flask + `prometheus_client`
- **Endpoints**:
  - `GET /` - home, subject to chaos
  - `GET /api/data` - data API, subject to chaos
  - `GET /api/slow` - naturally slow endpoint (1.5-3.5 s)
  - `GET /health` - health check, returns 503 when degraded
  - `GET /metrics` - Prometheus scrape endpoint
  - `POST /chaos/errors/start` - inject HTTP 500 errors
  - `POST /chaos/errors/stop`
  - `POST /chaos/latency/start` - inject artificial delay
  - `POST /chaos/latency/stop`
  - `POST /chaos/cpu/start` - burn CPU
  - `POST /chaos/cpu/stop`
  - `POST /chaos/reset` - clear all chaos
  - `GET /chaos/status`

### 2. Prometheus (`prometheus/`)
- Scrapes `/metrics` every 5 s
- Evaluates alert rules every 15 s
- Retains 7 days of data

**Key alert rules** (`prometheus/alert_rules.yml`):
```yaml
HighErrorRate:    error_rate > 5%    for 30s  -> critical
HighLatencyP95:   P95 latency > 1s   for 1m   -> critical
HighCPUSaturation: CPU > 80%         for 1m   -> critical
ServiceDown:      service_up == 0    for 15s  -> critical
TrafficDrop:      rps < 0.1          for 2m   -> warning
```

### 3. AlertManager (`alertmanager/`)
- Routes critical alerts to the Remediation Service webhook within 5 s
- Applies inhibition rules (if service is down, suppress sub-alerts)
- Deduplicates alerts with 60 s group intervals
- Configured webhook URL: `http://remediation:8080/webhook/alert`

### 4. Grafana (`grafana/`)
- **Golden Signals Dashboard** (`golden-signals.json`)
  - Service Status stat panel
  - Error Rate (%) with 5% SLO line
  - P50/P95/P99 Latency with 1 s SLO line
  - Traffic by endpoint
  - CPU & Memory Saturation
- **Incident Timeline Dashboard** (`incident-timeline.json`)
  - Active firing alerts count
  - Alert state over time
  - All four signals overlaid

Access: `http://localhost:3000` - credentials: `admin / techstream`

### 5. Remediation Service (`remediation/remediation_service.py`)
**Self-healing playbook** - maps each alert to actions:

| Alert | Actions |
|---|---|
| `HighErrorRate` | Stop error injection -> full reset |
| `ServiceDown` | Full chaos reset |
| `HighLatencyP95/99` | Stop latency injection |
| `HighCPUSaturation` | Stop CPU spike |
| `HighMemorySaturation` | Full chaos reset |

Features:
- 60-second cooldown prevents action storms
- Parallel AI analysis request for every incident
- Incident audit log (last 200 entries) at `GET /incidents`
- Manual trigger at `POST /remediate/manual`

### 6. AI Analyzer (`ai_analyzer/analyzer.py`)
**DevOps Guru simulation** - performs root cause analysis:

1. Fetches a live metric snapshot from Prometheus
2. Scores a hypothesis knowledge base against current signal values
3. Ranks root causes by confidence
4. Classifies the failure pattern (`CASCADE_FAILURE`, `ERROR_SPIKE`, `LATENCY_DEGRADATION`, `RESOURCE_EXHAUSTION`)
5. Returns structured JSON with `primary_root_cause`, `insights`, and `anomaly_correlation`

Sample response:
```json
{
  "primary_root_cause": {
    "hypothesis": "Chaos error injection is active",
    "confidence": 0.97,
    "category": "chaos_engineering",
    "impact": "high",
    "recommended_actions": ["POST /chaos/errors/stop", "POST /chaos/reset"]
  },
  "anomaly_correlation": {
    "correlated_signals": ["errors", "latency"],
    "pattern": "CASCADE_FAILURE"
  }
}
```

---

## Quick Start

### Prerequisites
- Docker Engine >= 24.0
- Docker Compose >= 2.24
- Python 3.9+ (for running chaos scripts from host)

### Start the Stack
```bash
make up
# or
docker compose up --build -d
```

### URLs after startup
| Service | URL | Credentials |
|---|---|---|
| Grafana | http://localhost:3000 | admin / techstream |
| Prometheus | http://localhost:9090 | - |
| AlertManager | http://localhost:9093 | - |
| App | http://localhost:5000 | - |
| Remediation API | http://localhost:8085 | - |
| AI Analyzer API | http://localhost:9000 | - |

---

## Incident Simulation Walkthrough

### Step 1 - Verify Baseline
```bash
make health
# -> all services return { "status": "ok" }
# Grafana: Error Rate ~= 0%, P95 Latency < 100 ms, CPU < 30%
```

### Step 2 - Inject Chaos (Error Spike)
```bash
make chaos-errors
# or
curl -X POST http://localhost:5000/chaos/errors/start \
  -H "Content-Type: application/json" \
  -d '{"error_rate": 0.8}'
```

**Expected sequence (T+0 to T+90s):**
```
T+0s   Chaos starts - 80% of requests return HTTP 500
T+5s   Prometheus scrapes elevated http_errors_total
T+30s  HighErrorRate alert fires (error_rate > 5% for 30s)
T+35s  AlertManager routes alert to Remediation webhook
T+36s  Remediation Service calls POST /chaos/errors/stop
T+37s  AI Analyzer returns root cause: "Chaos error injection is active" (confidence 0.97)
T+60s  Error rate drops to ~0% in Grafana
T+90s  Alert resolves in AlertManager
```

### Step 3 - Full Cascade Failure
```bash
make chaos-full
# Injects errors + latency + CPU spike simultaneously
```

### Step 4 - Inspect Results
```bash
make incidents       # View remediation audit log
make analysis        # View AI root cause analyses
```

### Step 5 - Reset Everything
```bash
make chaos-reset
```

---

## Chaos Script Reference

```bash
# From host (requires: pip install requests)
python3 chaos/chaos_script.py errors   --rate 0.8  --duration 60
python3 chaos/chaos_script.py latency  --ms 2000   --duration 60
python3 chaos/chaos_script.py cpu                  --duration 60
python3 chaos/chaos_script.py full                 --duration 120
python3 chaos/chaos_script.py reset
python3 chaos/chaos_script.py traffic  --rps 10    --duration 120
python3 chaos/chaos_script.py status
```

---

## AWS Deployment Guide

For production AWS deployment, map each component:

### Terraform Infrastructure
```
modules/
  vpc/              - VPC, subnets, security groups
  ecs/              - ECS Fargate cluster + task definitions
  rds/              - RDS (if app needs DB)
  alb/              - Application Load Balancer
  cloudwatch/       - Log groups, dashboards, alarms
  eventbridge/      - Rules to connect alarms to Lambda
  lambda/           - Remediation functions
  devops-guru/      - DevOps Guru resource group
```

### CloudWatch Alarms (replaces Prometheus alerts)
```hcl
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "HighErrorRate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 0.05
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

### EventBridge Rule (replaces AlertManager webhook)
```hcl
resource "aws_cloudwatch_event_rule" "high_error_rate" {
  name        = "HighErrorRateRule"
  description = "Trigger remediation on high error rate"
  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      alarmName = ["HighErrorRate"]
      state     = { value = ["ALARM"] }
    }
  })
}

resource "aws_cloudwatch_event_target" "lambda_remediation" {
  rule      = aws_cloudwatch_event_rule.high_error_rate.name
  target_id = "RemediationLambda"
  arn       = aws_lambda_function.remediation.arn
}
```

### Lambda Remediation Function
```python
# Equivalent to remediation_service.py
def handler(event, context):
    alarm_name = event['detail']['alarmName']
    if alarm_name == 'HighErrorRate':
        ecs_client.update_service(
            cluster='techstream',
            service='web_app',
            forceNewDeployment=True  # restart
        )
```

### Amazon DevOps Guru (replaces ai_analyzer)
- Enable on the CloudFormation stack or resource group
- Automatically correlates anomalies across CloudWatch metrics
- Provides ML-powered insights with OpsItem integration
- Enable via: AWS Console -> DevOps Guru -> Enable for this account

---

## Metrics Reference

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `http_requests_total` | Counter | method, endpoint, status_code | Total requests |
| `http_request_duration_seconds` | Histogram | method, endpoint | Request latency |
| `http_errors_total` | Counter | endpoint, error_type | Error events |
| `cpu_saturation_percent` | Gauge | - | CPU utilisation % |
| `memory_saturation_percent` | Gauge | - | Memory utilisation % |
| `service_up` | Gauge | - | 1=healthy, 0=degraded |
| `active_requests_count` | Gauge | - | In-flight requests |

---

## SLO Definitions

| Signal | SLO | Alert |
|---|---|---|
| Availability | > 99.9% uptime | `service_up == 0` for 15 s |
| Error rate | < 1% p30d | > 5% for 30 s -> critical |
| Latency P95 | < 500 ms | > 1000 ms for 1 min -> critical |
| CPU Saturation | < 70% sustained | > 80% for 1 min -> critical |

---

## File Structure

```
AIops/
+-- docker-compose.yml          # Full stack orchestration
+-- Makefile                    # Operational shortcuts
|
+-- app/
|   +-- app.py                  # Flask app + Prometheus metrics + chaos endpoints
|   +-- requirements.txt
|   +-- Dockerfile
|
+-- prometheus/
|   +-- prometheus.yml          # Scrape config + AlertManager integration
|   +-- alert_rules.yml         # Golden Signal alert thresholds
|
+-- alertmanager/
|   +-- alertmanager.yml        # Alert routing -> remediation webhook
|
+-- grafana/
|   +-- provisioning/
|   |   +-- datasources/prometheus.yml
|   |   +-- dashboards/dashboards.yml
|   +-- dashboards/
|       +-- golden-signals.json # Main Golden Signals dashboard
|       +-- incident-timeline.json
|
+-- remediation/
|   +-- remediation_service.py  # Self-healing webhook handler
|   +-- requirements.txt
|   +-- Dockerfile
|
+-- ai_analyzer/
|   +-- analyzer.py             # AI/ML root cause analysis (DevOps Guru sim)
|   +-- requirements.txt
|   +-- Dockerfile
|
+-- chaos/
|   +-- chaos_script.py         # Interactive chaos CLI
|   +-- chaos_cpu.sh            # Shell-level CPU chaos
|
+-- screenshoots/               # Lab evidence screenshots
|
+-- terraform/                  # AWS infrastructure as code
|
+-- docs/
    +-- README.md               # This file
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Grafana shows "No data" | `curl http://localhost:9090/api/v1/query?query=up` - verify targets |
| Alerts not firing | `http://localhost:9090/alerts` - check rule evaluation |
| Remediation not triggering | `http://localhost:9093` - verify webhook config; check `make logs-remedy` |
| AI analysis missing | `make logs-ai` - confirm Prometheus reachable from ai_analyzer container |
| App not starting | `docker compose logs web_app` |

---

## Screenshots

All screenshots are in the [`screenshoots/`](../screenshoots/) folder. They are organized below by lab objective.

---

### 1. Local Stack - Application Running

**Web app responding at `localhost:5000`**

![Web app root endpoint](../screenshoots/Screenshot%20from%202026-04-27%2010-32-21.png)

The Flask application returns `{"service": "TechStream", "status": "ok", "version": "1.0.0"}`, confirming the web server is live.

---

**App health endpoint at `localhost:5000/health`**

![App health endpoint](../screenshoots/Screenshot%20from%202026-04-27%2010-32-46.png)

The `/health` endpoint reports `status: healthy` with live chaos state flags (all false at baseline), CPU at 40.2%, and memory at 82.6%.

---

**Raw Prometheus metrics at `localhost:5000/metrics`**

![Prometheus metrics endpoint](../screenshoots/Screenshot%20from%202026-04-27%2010-33-11.png)

The `/metrics` endpoint exposes all Golden Signal counters and histograms in Prometheus text format, ready for scraping.

---

**Prometheus API query confirming all targets up**

![Prometheus query up](../screenshoots/Screenshot%20from%202026-04-27%2010-41-18.png)

`/api/v1/query?query=up` returns value `"1"` for all four instances: `techstream-web`, `node_exporter:9100`, `cadvisor:8080`, and `localhost:9090` (Prometheus itself).

---

### 2. Golden Signal Monitoring - Prometheus Targets and Alerts

**Prometheus scrape targets - all UP**

![Prometheus targets](../screenshoots/Screenshot%20from%202026-04-27%2010-34-24.png)

The Targets page at `localhost:9090/targets` shows cadvisor, node_exporter, prometheus, and techstream_app all in the **UP** state with healthy scrape durations.

---

**Prometheus alert rules loaded**

![Prometheus alert rules](../screenshoots/Screenshot%20from%202026-04-27%2010-34-52.png)

The Alerts page at `localhost:9090/alerts` shows all 9 Golden Signal rules loaded from `alert_rules.yml`: `HighErrorRate`, `ErrorRateWarning`, `HighLatencyP95`, `HighLatencyP99`, `HighCPUSaturation`, `HighMemorySaturation`, `TrafficDrop`, `ServiceDown`, `ServiceHealthCheckFailing`. All are **Inactive** at baseline.

---

### 3. Golden Signals Dashboard - Grafana

**Golden Signals dashboard - all four panels**

![Grafana Golden Signals dashboard](../screenshoots/Screenshot%20from%202026-04-27%2010-38-25.png)

The Grafana dashboard at `localhost:3000` shows:
- **Service Status**: HEALTHY (green)
- **Error Rate**: baseline ~0% with 5% SLO threshold line
- **Latency**: P50/P95/P99 curves with 1s SLO line
- **Traffic**: requests per second by endpoint
- **CPU & Memory Saturation**: live host metrics from node_exporter

---

**Incident Timeline dashboard**

![Grafana Incident Timeline dashboard](../screenshoots/Screenshot%20from%202026-04-27%2010-38-47.png)

The Incident Timeline dashboard shows Active Alerts Count = **0** at baseline, Alert State Over Time graph, and the All Four Golden Signals overlay normalized view - confirming normal operation before chaos injection.

---

### 4. Automated Remediation - Self-Healing Evidence

**Remediation service incident log at `localhost:8085/incidents`**

![Remediation incidents log](../screenshoots/Screenshot%20from%202026-04-27%2010-40-03.png)

The incident audit log shows the complete self-healing sequence: `action_stop_latency_chaos` with result `SUCCESS`, followed by `auto_resolved` entries for `HighLatencyP95` and `ServiceDown` alerts. The timestamps confirm automated resolution within seconds of the alert firing - no human intervention required.

---

### 5. AWS Deployment

**AWS ECR - Docker image repositories created and pushed**

![AWS ECR repositories](../screenshoots/Screenshot%20from%202026-04-27%2011-14-23.png)

Amazon Elastic Container Registry shows three private repositories created by Terraform: `techstream-web-app`, `techstream-remediation`, and `techstream-analyzer`, all pushed on April 27, 2026.

---

**Terraform apply output - all AWS resources deployed**

![Terraform deployment output](../screenshoots/Screenshot%20from%202026-04-27%2012-38-54.png)

The terminal shows `terraform apply` completing successfully with output values including the CloudWatch dashboard URL, Grafana URL, Prometheus URL, ECS cluster name (`techstream-cluster`), and Lambda function ARNs for `auto-restart` and `scale-out`.

---

**AWS Application Load Balancer - active and routing traffic**

![AWS ALB](../screenshoots/Screenshot%20from%202026-04-27%2012-55-29.png)

The EC2 Load Balancers console shows `techstream-alb` in **Active** state, Internet-facing, IPv4, deployed across multiple Availability Zones. This is the AWS equivalent of the local Flask app port.

---

**AWS ECS Cluster - all three services running**

![AWS ECS Cluster](../screenshoots/Screenshot%20from%202026-04-27%2012-59-10.png)

The ECS Cluster `techstream-cluster` console shows the cluster **ACTIVE** with CloudWatch monitoring enabled and three Fargate services running: `techstream-analyzer-service`, `techstream-remediation`, and the web app service.

---

**AWS Lambda - remediation functions deployed**

![AWS Lambda functions](../screenshoots/Screenshot%20from%202026-04-27%2012-59-53.png)

The Lambda Functions console shows four functions including the two TechStream remediation handlers: `techstream-auto-restart` (restarts ECS service on high error rate) and `techstream-scale-out` (triggers ASG scale-out on high saturation). Both use Python 3.11 runtime.

---

**AWS SNS - alert notification topics**

![AWS SNS topics](../screenshoots/Screenshot%20from%202026-04-27%2013-01-18.png)

Amazon SNS shows three topics: `techstream-alerts` (routes CloudWatch alarm notifications to Lambda via EventBridge) and `techstream-devops-guru_insights` (receives DevOps Guru anomaly insights). These are the AWS equivalents of the local AlertManager webhook.

---

**AWS CloudWatch - alarms active**

![AWS CloudWatch alarms](../screenshoots/Screenshot%20from%202026-04-27%2013-59-08.png)

The CloudWatch Overview shows alarms in **ALARM** state: `techstream-low-traffic` and `techstream-high-latency`, confirming that the AWS-side alerting pipeline mirrors the local Prometheus alert rules and fires under the same conditions.

---

**AWS CloudWatch - ECS Cluster monitoring dashboard**

![AWS CloudWatch ECS dashboard](../screenshoots/Screenshot%20from%202026-04-27%2014-03-06.png)

The CloudWatch ECS Cluster dashboard shows live metrics for the deployed `techstream-cluster`: CPU Utilization, Memory Utilization, Disk Utilization, Network throughput, Container Instance Count, Task Count, and Service Count - the AWS equivalent of the local Grafana Golden Signals dashboard.
