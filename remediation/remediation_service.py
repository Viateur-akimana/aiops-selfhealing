"""
TechStream Automated Remediation Service
Receives AlertManager webhooks and executes self-healing actions.
Acts as the EventBridge + Lambda equivalent in local/Docker environments.
"""

import os
import time
import logging
import threading
import subprocess
import requests
from datetime import datetime
from collections import deque
from flask import Flask, request, jsonify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

WEBAPP_URL = os.environ.get('WEBAPP_URL', 'http://web_app:5000')
AI_ANALYZER_URL = os.environ.get('AI_ANALYZER_URL', 'http://ai_analyzer:9000')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'techstream-webhook-secret')

# In-memory incident log (last 200 entries)
incident_log = deque(maxlen=200)
remediation_stats = {
    'total_alerts_received': 0,
    'total_remediations_executed': 0,
    'total_remediations_succeeded': 0,
    'total_remediations_failed': 0,
}

# Cooldown tracking - avoid re-triggering the same fix within 60 s
_cooldowns = {}
_cooldown_lock = threading.Lock()
COOLDOWN_SECONDS = 60


def _is_in_cooldown(alert_name: str) -> bool:
    with _cooldown_lock:
        last = _cooldowns.get(alert_name)
        if last and (time.time() - last) < COOLDOWN_SECONDS:
            return True
        _cooldowns[alert_name] = time.time()
        return False


def _log_incident(alert_name, severity, action, result, details=''):
    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'alert': alert_name,
        'severity': severity,
        'action': action,
        'result': result,
        'details': details,
    }
    incident_log.appendleft(entry)
    logger.info("INCIDENT LOG | alert=%s action=%s result=%s", alert_name, action, result)
    return entry


# Remediation Actions

def action_reset_chaos():
    """Tell the web app to clear all chaos flags - the 'restart' equivalent."""
    try:
        r = requests.post(f'{WEBAPP_URL}/chaos/reset', timeout=5)
        r.raise_for_status()
        return True, 'chaos reset via /chaos/reset'
    except Exception as exc:
        return False, str(exc)


def action_stop_error_chaos():
    try:
        r = requests.post(f'{WEBAPP_URL}/chaos/errors/stop', timeout=5)
        r.raise_for_status()
        return True, 'error injection stopped'
    except Exception as exc:
        return False, str(exc)


def action_stop_latency_chaos():
    try:
        r = requests.post(f'{WEBAPP_URL}/chaos/latency/stop', timeout=5)
        r.raise_for_status()
        return True, 'latency injection stopped'
    except Exception as exc:
        return False, str(exc)


def action_stop_cpu_chaos():
    try:
        r = requests.post(f'{WEBAPP_URL}/chaos/cpu/stop', timeout=5)
        r.raise_for_status()
        return True, 'cpu spike stopped'
    except Exception as exc:
        return False, str(exc)


def action_request_ai_analysis(alert_name, labels, annotations):
    """Ask the AI analyzer for a root-cause assessment asynchronously."""
    try:
        payload = {
            'alert_name': alert_name,
            'labels': labels,
            'annotations': annotations,
            'triggered_at': datetime.utcnow().isoformat(),
        }
        r = requests.post(
            f'{AI_ANALYZER_URL}/analyze',
            json=payload,
            timeout=10
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("AI analyzer unavailable: %s", exc)
        return {'error': str(exc)}


# Alert -> Action mapping
REMEDIATION_PLAYBOOK = {
    'HighErrorRate':        [action_stop_error_chaos, action_reset_chaos],
    'ServiceDown':          [action_reset_chaos],
    'HighLatencyP95':       [action_stop_latency_chaos],
    'HighLatencyP99':       [action_stop_latency_chaos],
    'HighCPUSaturation':    [action_stop_cpu_chaos],
    'HighMemorySaturation': [action_reset_chaos],
    'TrafficDrop':          [action_reset_chaos],
}


def _execute_remediation(alert_name, severity, labels, annotations):
    """Run remediation playbook for a given alert in a background thread."""
    if _is_in_cooldown(alert_name):
        logger.info("Cooldown active for %s - skipping remediation", alert_name)
        return

    remediation_stats['total_remediations_executed'] += 1
    actions = REMEDIATION_PLAYBOOK.get(alert_name, [action_reset_chaos])

    # Request AI analysis in parallel
    ai_thread = threading.Thread(
        target=action_request_ai_analysis,
        args=(alert_name, labels, annotations),
        daemon=True
    )
    ai_thread.start()

    all_ok = True
    for action in actions:
        ok, detail = action()
        log_result = 'SUCCESS' if ok else 'FAILED'
        _log_incident(alert_name, severity, action.__name__, log_result, detail)
        if not ok:
            all_ok = False
            logger.error("Remediation action %s FAILED: %s", action.__name__, detail)

    if all_ok:
        remediation_stats['total_remediations_succeeded'] += 1
        logger.info("Remediation for %s completed successfully", alert_name)
    else:
        remediation_stats['total_remediations_failed'] += 1
        logger.error("Remediation for %s had failures - manual intervention may be needed", alert_name)


# Webhook Endpoint
@app.route('/webhook/alert', methods=['POST'])
def webhook_alert():
    auth = request.headers.get('Authorization', '')
    if WEBHOOK_SECRET and f'Bearer {WEBHOOK_SECRET}' != auth:
        logger.warning("Unauthorized webhook attempt from %s", request.remote_addr)
        return jsonify({'error': 'unauthorized'}), 401

    payload = request.json or {}
    remediation_stats['total_alerts_received'] += 1

    alerts = payload.get('alerts', [])
    logger.info("Webhook received: %d alert(s), status=%s", len(alerts), payload.get('status'))

    for alert in alerts:
        alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
        severity = alert.get('labels', {}).get('severity', 'unknown')
        status = alert.get('status', 'unknown')
        labels = alert.get('labels', {})
        annotations = alert.get('annotations', {})

        if status == 'firing':
            logger.warning("ALERT FIRING: %s (severity=%s)", alert_name, severity)
            t = threading.Thread(
                target=_execute_remediation,
                args=(alert_name, severity, labels, annotations),
                daemon=True
            )
            t.start()
        elif status == 'resolved':
            logger.info("ALERT RESOLVED: %s", alert_name)
            _log_incident(alert_name, severity, 'auto_resolved', 'RESOLVED', 'Alert cleared by Prometheus')

    return jsonify({'received': len(alerts), 'status': 'processing'}), 202


# Management Endpoints
@app.route('/incidents')
def list_incidents():
    limit = int(request.args.get('limit', 50))
    return jsonify({
        'incidents': list(incident_log)[:limit],
        'stats': remediation_stats,
    })


@app.route('/stats')
def stats():
    return jsonify(remediation_stats)


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'remediation'})


@app.route('/remediate/manual', methods=['POST'])
def manual_remediate():
    """Trigger a manual remediation - useful for testing without an alert."""
    body = request.json or {}
    alert_name = body.get('alert_name', 'ManualTrigger')
    _execute_remediation(alert_name, 'manual', {}, {})
    return jsonify({'triggered': alert_name})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)
