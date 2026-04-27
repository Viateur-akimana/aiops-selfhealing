"""
TechStream Web Application - Buggy server with Golden Signal instrumentation.
Exposes Prometheus metrics for Latency, Traffic, Errors, and Saturation.
"""

import os
import time
import random
import threading
import logging
import psutil
from flask import Flask, jsonify, request, Response
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, multiprocess
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Golden Signal Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)
ERROR_COUNTER = Counter(
    'http_errors_total',
    'Total HTTP errors by type',
    ['endpoint', 'error_type']
)
CPU_SATURATION = Gauge('cpu_saturation_percent', 'CPU utilization %')
MEMORY_SATURATION = Gauge('memory_saturation_percent', 'Memory utilization %')
ACTIVE_REQUESTS = Gauge('active_requests_count', 'Currently active requests')
SERVICE_UP = Gauge('service_up', 'Service health: 1=healthy, 0=degraded')

# Chaos State (controlled by /chaos/* endpoints)
chaos = {
    'error_injection': False,
    'error_rate': 0.8,          # fraction of requests that error during injection
    'latency_injection': False,
    'latency_ms': 2000,
    'cpu_spike': False,
}
_cpu_spike_thread = None
_chaos_lock = threading.Lock()


def _burn_cpu():
    """Burn CPU until chaos['cpu_spike'] is cleared."""
    logger.warning("CPU spike started")
    while chaos['cpu_spike']:
        _ = [x ** 2 for x in range(50_000)]
    logger.info("CPU spike stopped")


def _update_system_metrics():
    """Background thread: refresh CPU/memory gauges every 5 s."""
    while True:
        CPU_SATURATION.set(psutil.cpu_percent(interval=1))
        MEMORY_SATURATION.set(psutil.virtual_memory().percent)
        time.sleep(5)


threading.Thread(target=_update_system_metrics, daemon=True).start()

# Middleware
@app.before_request
def before():
    request.start_time = time.time()
    ACTIVE_REQUESTS.inc()


@app.after_request
def after(response):
    duration = time.time() - request.start_time
    endpoint = request.endpoint or 'unknown'
    REQUEST_DURATION.labels(method=request.method, endpoint=endpoint).observe(duration)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=str(response.status_code)
    ).inc()
    ACTIVE_REQUESTS.dec()
    return response


# Application Endpoints
@app.route('/')
def index():
    if chaos['latency_injection']:
        time.sleep(chaos['latency_ms'] / 1000)
    if chaos['error_injection'] and random.random() < chaos['error_rate']:
        ERROR_COUNTER.labels(endpoint='/', error_type='injected_500').inc()
        SERVICE_UP.set(0)
        return jsonify({'error': 'Internal Server Error', 'source': 'chaos'}), 500
    SERVICE_UP.set(1)
    return jsonify({'service': 'TechStream', 'status': 'ok', 'version': '1.0.0'})


@app.route('/api/data')
def api_data():
    if chaos['latency_injection']:
        time.sleep(chaos['latency_ms'] / 1000)
    if chaos['error_injection'] and random.random() < chaos['error_rate']:
        ERROR_COUNTER.labels(endpoint='/api/data', error_type='injected_500').inc()
        return jsonify({'error': 'Service temporarily unavailable'}), 500

    # Simulate realistic processing time
    time.sleep(random.uniform(0.01, 0.15))
    return jsonify({
        'records': [{'id': i, 'value': random.random()} for i in range(10)],
        'latency_ms': round((time.time() - request.start_time) * 1000, 2)
    })


@app.route('/api/slow')
def api_slow():
    """Naturally slow endpoint - simulates a DB-heavy query."""
    time.sleep(random.uniform(1.5, 3.5))
    return jsonify({'result': 'slow query complete'})


@app.route('/health')
def health():
    healthy = not chaos['error_injection']
    SERVICE_UP.set(1 if healthy else 0)
    status = 'healthy' if healthy else 'degraded'
    code = 200 if healthy else 503
    return jsonify({
        'status': status,
        'chaos': chaos,
        'cpu': psutil.cpu_percent(),
        'memory': psutil.virtual_memory().percent
    }), code


@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# Chaos Control Endpoints
@app.route('/chaos/errors/start', methods=['POST'])
def chaos_errors_start():
    rate = float(request.json.get('error_rate', 0.8)) if request.json else 0.8
    with _chaos_lock:
        chaos['error_injection'] = True
        chaos['error_rate'] = min(max(rate, 0.0), 1.0)
    logger.warning("CHAOS: error injection started at rate=%.0f%%", chaos['error_rate'] * 100)
    return jsonify({'chaos': 'error_injection_started', 'error_rate': chaos['error_rate']})


@app.route('/chaos/errors/stop', methods=['POST'])
def chaos_errors_stop():
    with _chaos_lock:
        chaos['error_injection'] = False
    SERVICE_UP.set(1)
    logger.info("CHAOS: error injection stopped")
    return jsonify({'chaos': 'error_injection_stopped'})


@app.route('/chaos/latency/start', methods=['POST'])
def chaos_latency_start():
    ms = int(request.json.get('latency_ms', 2000)) if request.json else 2000
    with _chaos_lock:
        chaos['latency_injection'] = True
        chaos['latency_ms'] = ms
    logger.warning("CHAOS: latency injection started at %d ms", ms)
    return jsonify({'chaos': 'latency_injection_started', 'latency_ms': ms})


@app.route('/chaos/latency/stop', methods=['POST'])
def chaos_latency_stop():
    with _chaos_lock:
        chaos['latency_injection'] = False
    logger.info("CHAOS: latency injection stopped")
    return jsonify({'chaos': 'latency_injection_stopped'})


@app.route('/chaos/cpu/start', methods=['POST'])
def chaos_cpu_start():
    global _cpu_spike_thread
    with _chaos_lock:
        if not chaos['cpu_spike']:
            chaos['cpu_spike'] = True
            _cpu_spike_thread = threading.Thread(target=_burn_cpu, daemon=True)
            _cpu_spike_thread.start()
    logger.warning("CHAOS: CPU spike started")
    return jsonify({'chaos': 'cpu_spike_started'})


@app.route('/chaos/cpu/stop', methods=['POST'])
def chaos_cpu_stop():
    with _chaos_lock:
        chaos['cpu_spike'] = False
    logger.info("CHAOS: CPU spike stopped")
    return jsonify({'chaos': 'cpu_spike_stopped'})


@app.route('/chaos/status')
def chaos_status():
    return jsonify(chaos)


@app.route('/chaos/reset', methods=['POST'])
def chaos_reset():
    with _chaos_lock:
        chaos['error_injection'] = False
        chaos['latency_injection'] = False
        chaos['cpu_spike'] = False
    SERVICE_UP.set(1)
    logger.info("CHAOS: all chaos reset")
    return jsonify({'chaos': 'all_reset', 'state': chaos})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
