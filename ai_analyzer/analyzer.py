"""
TechStream AI Root Cause Analyzer
Simulates Amazon DevOps Guru / ML-based anomaly correlation.

Pipeline:
  1. Ingest alert + labels
  2. Fetch recent metrics from Prometheus
  3. Run rule-based correlation (simulates ML inference)
  4. Score hypotheses and return ranked root causes
  5. Recommend remediation actions
"""

import os
import time
import random
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://prometheus:9090')

# Knowledge Base
# Maps (alert_name, signal) -> possible root causes with base confidence scores

HYPOTHESIS_KB = {
    'HighErrorRate': [
        {
            'hypothesis': 'Chaos error injection is active',
            'confidence': 0.95,
            'evidence_queries': ['chaos_active'],
            'category': 'chaos_engineering',
            'remediation': ['POST /chaos/errors/stop', 'POST /chaos/reset'],
            'impact': 'high',
        },
        {
            'hypothesis': 'Upstream dependency failure (database/cache)',
            'confidence': 0.72,
            'evidence_queries': ['db_errors'],
            'category': 'dependency',
            'remediation': ['Check DB connection pool', 'Restart dependency services'],
            'impact': 'high',
        },
        {
            'hypothesis': 'Code deployment introduced regression',
            'confidence': 0.55,
            'evidence_queries': ['deployment_event'],
            'category': 'deployment',
            'remediation': ['Rollback to previous version', 'Review recent diff'],
            'impact': 'medium',
        },
        {
            'hypothesis': 'Memory pressure causing OOM kills',
            'confidence': 0.40,
            'evidence_queries': ['memory_saturation'],
            'category': 'resource',
            'remediation': ['Increase memory limit', 'Check for memory leak'],
            'impact': 'medium',
        },
    ],
    'HighLatencyP95': [
        {
            'hypothesis': 'Latency chaos injection is active',
            'confidence': 0.95,
            'evidence_queries': ['latency_chaos'],
            'category': 'chaos_engineering',
            'remediation': ['POST /chaos/latency/stop'],
            'impact': 'high',
        },
        {
            'hypothesis': 'CPU saturation causing request queuing',
            'confidence': 0.80,
            'evidence_queries': ['cpu_saturation'],
            'category': 'resource',
            'remediation': ['Horizontal scale-out', 'Stop CPU-intensive jobs'],
            'impact': 'high',
        },
        {
            'hypothesis': 'Slow database queries or N+1 problem',
            'confidence': 0.60,
            'evidence_queries': ['db_latency'],
            'category': 'code',
            'remediation': ['Add query indexes', 'Enable query result caching'],
            'impact': 'medium',
        },
    ],
    'HighCPUSaturation': [
        {
            'hypothesis': 'CPU spike chaos injection is active',
            'confidence': 0.95,
            'evidence_queries': ['cpu_chaos'],
            'category': 'chaos_engineering',
            'remediation': ['POST /chaos/cpu/stop'],
            'impact': 'high',
        },
        {
            'hypothesis': 'Traffic spike causing CPU exhaustion',
            'confidence': 0.65,
            'evidence_queries': ['request_rate'],
            'category': 'traffic',
            'remediation': ['Auto-scale horizontally', 'Enable rate limiting'],
            'impact': 'high',
        },
        {
            'hypothesis': 'Runaway background job or infinite loop',
            'confidence': 0.50,
            'evidence_queries': ['thread_count'],
            'category': 'code',
            'remediation': ['Restart affected process', 'Review job scheduler'],
            'impact': 'medium',
        },
    ],
    'ServiceDown': [
        {
            'hypothesis': 'Process crashed due to unhandled exception',
            'confidence': 0.85,
            'evidence_queries': ['health_check'],
            'category': 'availability',
            'remediation': ['Restart service', 'Check application logs'],
            'impact': 'critical',
        },
        {
            'hypothesis': 'OOM kill from container memory limit',
            'confidence': 0.70,
            'evidence_queries': ['memory_saturation'],
            'category': 'resource',
            'remediation': ['Increase container memory limit', 'Check for memory leak'],
            'impact': 'critical',
        },
    ],
}

DEFAULT_HYPOTHESES = [
    {
        'hypothesis': 'Unknown transient error - insufficient signal',
        'confidence': 0.30,
        'evidence_queries': [],
        'category': 'unknown',
        'remediation': ['Collect more metrics', 'Review application logs'],
        'impact': 'unknown',
    }
]

analysis_history = []


def _query_prometheus(query: str, lookback_minutes: int = 5):
    """Run an instant PromQL query and return the result."""
    try:
        r = requests.get(
            f'{PROMETHEUS_URL}/api/v1/query',
            params={'query': query},
            timeout=5
        )
        r.raise_for_status()
        return r.json().get('data', {}).get('result', [])
    except Exception as exc:
        logger.warning("Prometheus query failed (%s): %s", query, exc)
        return []


def _fetch_metric_snapshot():
    """Pull key metrics from Prometheus to enrich the analysis."""
    snapshot = {}

    # Error rate
    err_results = _query_prometheus(
        'rate(http_errors_total[2m]) / (rate(http_requests_total[2m]) + 0.001) * 100'
    )
    if err_results:
        snapshot['error_rate_pct'] = float(err_results[0]['value'][1])

    # P95 latency
    lat_results = _query_prometheus(
        "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
    )
    if lat_results:
        snapshot['p95_latency_s'] = float(lat_results[0]['value'][1])

    # CPU
    cpu_results = _query_prometheus('cpu_saturation_percent')
    if cpu_results:
        snapshot['cpu_pct'] = float(cpu_results[0]['value'][1])

    # Memory
    mem_results = _query_prometheus('memory_saturation_percent')
    if mem_results:
        snapshot['memory_pct'] = float(mem_results[0]['value'][1])

    # Request rate
    rr_results = _query_prometheus('rate(http_requests_total[2m])')
    if rr_results:
        snapshot['rps'] = sum(float(r['value'][1]) for r in rr_results)

    # Service up
    up_results = _query_prometheus('service_up')
    if up_results:
        snapshot['service_up'] = float(up_results[0]['value'][1])

    return snapshot


def _score_hypotheses(alert_name: str, metrics: dict) -> list:
    """Adjust hypothesis confidence using live metrics and return sorted list."""
    hypotheses = HYPOTHESIS_KB.get(alert_name, DEFAULT_HYPOTHESES)[:]

    for h in hypotheses:
        score = h['confidence']

        # Boost/reduce based on live evidence
        if h['category'] == 'chaos_engineering':
            # If we see simultaneous high error + high CPU/latency the chaos flag is very likely
            if metrics.get('error_rate_pct', 0) > 50:
                score = min(score + 0.04, 0.99)
            if metrics.get('cpu_pct', 0) > 80 and 'cpu' in h['hypothesis'].lower():
                score = min(score + 0.03, 0.99)

        if h['category'] == 'resource':
            if metrics.get('cpu_pct', 0) > 80:
                score = min(score + 0.10, 0.95)
            if metrics.get('memory_pct', 0) > 85:
                score = min(score + 0.08, 0.95)

        if h['category'] == 'traffic':
            if metrics.get('rps', 0) > 100:
                score = min(score + 0.15, 0.90)

        # Small random jitter to simulate ML uncertainty
        score += random.uniform(-0.02, 0.02)
        h = dict(h)
        h['confidence'] = round(min(max(score, 0.01), 0.99), 3)
        hypotheses[hypotheses.index(h) if h in hypotheses else -1] = h

    # Re-sort by confidence
    return sorted(hypotheses, key=lambda x: x['confidence'], reverse=True)


def _generate_insights(alert_name: str, metrics: dict, top_hypothesis: dict) -> list:
    """Generate human-readable insight bullets - simulates DevOps Guru narrative."""
    insights = []

    if metrics.get('error_rate_pct', 0) > 5:
        insights.append(
            f"Error rate is {metrics['error_rate_pct']:.1f}% - "
            f"{metrics['error_rate_pct'] / max(metrics.get('rps', 1), 0.1):.0f} errors/req"
        )

    if metrics.get('p95_latency_s', 0) > 0.5:
        insights.append(
            f"P95 latency = {metrics['p95_latency_s'] * 1000:.0f} ms "
            f"({'above' if metrics['p95_latency_s'] > 1 else 'near'} SLO threshold of 1000 ms)"
        )

    if metrics.get('cpu_pct', 0) > 70:
        insights.append(
            f"CPU at {metrics['cpu_pct']:.0f}% - "
            f"{'critical saturation' if metrics['cpu_pct'] > 90 else 'elevated, monitor closely'}"
        )

    if metrics.get('memory_pct', 0) > 75:
        insights.append(f"Memory at {metrics['memory_pct']:.0f}%")

    if metrics.get('service_up', 1) == 0:
        insights.append("service_up gauge = 0 - health endpoint reports degraded state")

    if not insights:
        insights.append("Metrics within normal bounds at time of analysis - possible transient spike")

    return insights


# API Endpoints
@app.route('/analyze', methods=['POST'])
def analyze():
    payload = request.json or {}
    alert_name = payload.get('alert_name', 'Unknown')
    labels = payload.get('labels', {})
    annotations = payload.get('annotations', {})
    triggered_at = payload.get('triggered_at', datetime.utcnow().isoformat())

    logger.info("AI analysis requested for alert: %s", alert_name)

    # 1. Fetch live metrics
    t0 = time.time()
    metrics = _fetch_metric_snapshot()

    # 2. Score hypotheses
    hypotheses = _score_hypotheses(alert_name, metrics)

    # 3. Generate insights
    top = hypotheses[0] if hypotheses else DEFAULT_HYPOTHESES[0]
    insights = _generate_insights(alert_name, metrics, top)

    analysis_time_ms = round((time.time() - t0) * 1000, 1)

    result = {
        'analysis_id': f"RCA-{int(time.time())}",
        'alert_name': alert_name,
        'triggered_at': triggered_at,
        'analyzed_at': datetime.utcnow().isoformat() + 'Z',
        'analysis_time_ms': analysis_time_ms,
        'metric_snapshot': metrics,
        'root_cause_ranking': hypotheses,
        'primary_root_cause': {
            'hypothesis': top['hypothesis'],
            'confidence': top['confidence'],
            'category': top['category'],
            'impact': top['impact'],
            'recommended_actions': top['remediation'],
        },
        'insights': insights,
        'anomaly_correlation': {
            'correlated_signals': [s for s in ['errors', 'latency', 'saturation', 'traffic']
                                   if _is_signal_anomalous(s, metrics)],
            'confidence_score': round(top['confidence'], 3),
            'pattern': _classify_pattern(alert_name, metrics),
        },
        'devops_guru_simulation': {
            'insight_type': 'REACTIVE',
            'insight_severity': labels.get('severity', 'unknown').upper(),
            'anomalous_behaviors': len([h for h in hypotheses if h['confidence'] > 0.5]),
            'recommendation_count': len(top['remediation']),
        },
    }

    analysis_history.append(result)
    if len(analysis_history) > 100:
        analysis_history.pop(0)

    logger.info(
        "Analysis complete: primary_cause='%s' confidence=%.2f",
        top['hypothesis'], top['confidence']
    )
    return jsonify(result)


def _is_signal_anomalous(signal: str, metrics: dict) -> bool:
    return {
        'errors':     metrics.get('error_rate_pct', 0) > 5,
        'latency':    metrics.get('p95_latency_s', 0) > 1.0,
        'saturation': metrics.get('cpu_pct', 0) > 80,
        'traffic':    metrics.get('rps', 1) < 0.1,
    }.get(signal, False)


def _classify_pattern(alert_name: str, metrics: dict) -> str:
    if metrics.get('error_rate_pct', 0) > 70 and metrics.get('cpu_pct', 0) > 80:
        return 'CASCADE_FAILURE'
    if metrics.get('error_rate_pct', 0) > 30:
        return 'ERROR_SPIKE'
    if metrics.get('p95_latency_s', 0) > 2:
        return 'LATENCY_DEGRADATION'
    if metrics.get('cpu_pct', 0) > 80:
        return 'RESOURCE_EXHAUSTION'
    return 'TRANSIENT_ANOMALY'


@app.route('/history')
def history():
    limit = int(request.args.get('limit', 20))
    return jsonify({'analyses': analysis_history[-limit:]})


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'ai_analyzer'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, threaded=True)
