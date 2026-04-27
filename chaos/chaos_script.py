#!/usr/bin/env python3
"""
TechStream Chaos Engineering Script
Injects failures into the web application to test monitoring, alerting, and self-healing.

Usage:
    python chaos_script.py errors          # inject HTTP 500 errors at 80% rate
    python chaos_script.py latency         # inject 2-second artificial latency
    python chaos_script.py cpu             # spike CPU usage
    python chaos_script.py full            # all three simultaneously
    python chaos_script.py reset           # clear all chaos
    python chaos_script.py traffic <n>     # generate n req/s of normal traffic
    python chaos_script.py status          # show current chaos state
"""

import sys
import time
import argparse
import threading
import requests
import json
from datetime import datetime

APP_URL = "http://localhost:5000"


def _post(path: str, body: dict = None):
    try:
        r = requests.post(f"{APP_URL}{path}", json=body, timeout=5)
        return r.json()
    except Exception as e:
        print(f"  [ERROR] {path} failed: {e}")
        return {}


def _get(path: str):
    try:
        r = requests.get(f"{APP_URL}{path}", timeout=5)
        return r.json()
    except Exception as e:
        print(f"  [ERROR] {path} failed: {e}")
        return {}


def banner(msg: str):
    width = 60
    print("\n" + "=" * width)
    print(f"  {msg}")
    print("=" * width)


def chaos_errors(rate: float = 0.8, duration: int = 0):
    banner(f"CHAOS: Injecting HTTP 500 errors at {int(rate*100)}% rate")
    result = _post("/chaos/errors/start", {"error_rate": rate})
    print(f"  Response: {json.dumps(result, indent=2)}")
    print(f"  Tip: Watch Grafana -> 'Error Rate' panel spike above the 5% threshold")
    print(f"       AlertManager should fire 'HighErrorRate' within ~30 seconds")
    if duration > 0:
        print(f"\n  Running for {duration} seconds...")
        time.sleep(duration)
        chaos_reset()


def chaos_latency(ms: int = 2000, duration: int = 0):
    banner(f"CHAOS: Injecting {ms}ms artificial latency")
    result = _post("/chaos/latency/start", {"latency_ms": ms})
    print(f"  Response: {json.dumps(result, indent=2)}")
    print(f"  Tip: Watch Grafana -> 'Latency' panel - P95 will breach 1 s SLO")
    if duration > 0:
        print(f"\n  Running for {duration} seconds...")
        time.sleep(duration)
        _post("/chaos/latency/stop")
        print("  Latency injection stopped.")


def chaos_cpu(duration: int = 0):
    banner("CHAOS: Starting CPU spike")
    result = _post("/chaos/cpu/start")
    print(f"  Response: {json.dumps(result, indent=2)}")
    print(f"  Tip: Watch Grafana -> 'Saturation' panel - CPU will climb above 80%")
    if duration > 0:
        print(f"\n  Running for {duration} seconds...")
        time.sleep(duration)
        _post("/chaos/cpu/stop")
        print("  CPU spike stopped.")


def chaos_full(duration: int = 60):
    banner("CHAOS: Full incident - errors + latency + CPU spike")
    print("  Simulating a cascading failure across all Golden Signals...\n")
    _post("/chaos/errors/start",  {"error_rate": 0.8})
    _post("/chaos/latency/start", {"latency_ms": 1500})
    _post("/chaos/cpu/start")
    print("  All chaos active. Waiting for AlertManager to fire and Remediation to respond...")
    print(f"  Duration: {duration} seconds")

    # Generate traffic during chaos so metrics are visible
    stop_flag = threading.Event()
    def _traffic():
        while not stop_flag.is_set():
            try:
                requests.get(f"{APP_URL}/api/data", timeout=5)
                requests.get(f"{APP_URL}/", timeout=5)
            except Exception:
                pass
            time.sleep(0.2)

    t = threading.Thread(target=_traffic, daemon=True)
    t.start()

    for remaining in range(duration, 0, -10):
        time.sleep(min(10, remaining))
        state = _get("/chaos/status")
        snapshot = {k: v for k, v in state.items() if k != '__doc__'}
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] chaos_state={snapshot}")

    stop_flag.set()
    print("\n  Chaos duration elapsed - remediation should have fired by now.")
    print("  Checking current state...")
    time.sleep(2)
    state = _get("/chaos/status")
    print(f"  Final chaos state: {json.dumps(state, indent=2)}")


def chaos_reset():
    banner("CHAOS: Resetting all injections")
    result = _post("/chaos/reset")
    print(f"  Response: {json.dumps(result, indent=2)}")
    print("  All Golden Signals should return to baseline within ~30 seconds.")


def generate_traffic(rps: float = 5.0, duration: int = 60):
    banner(f"TRAFFIC: Generating {rps} req/s for {duration} seconds")
    interval = 1.0 / rps
    end_time = time.time() + duration
    count = 0
    endpoints = ["/", "/api/data", "/health"]

    print(f"  Hitting endpoints: {endpoints}")
    while time.time() < end_time:
        endpoint = endpoints[count % len(endpoints)]
        try:
            r = requests.get(f"{APP_URL}{endpoint}", timeout=3)
            if count % 50 == 0:
                print(f"  [{count:5d} reqs] last={r.status_code} elapsed={time.time():.0f}s")
        except Exception as e:
            if count % 50 == 0:
                print(f"  [{count:5d} reqs] error: {e}")
        count += 1
        time.sleep(interval)

    print(f"\n  Done. Sent {count} requests.")


def show_status():
    banner("STATUS")
    chaos_state = _get("/chaos/status")
    health = _get("/health")
    print(f"  Chaos:  {json.dumps(chaos_state, indent=2)}")
    print(f"  Health: {json.dumps(health, indent=2)}")


def main():
    parser = argparse.ArgumentParser(description="TechStream Chaos Script")
    parser.add_argument('command', choices=['errors', 'latency', 'cpu', 'full', 'reset', 'traffic', 'status'],
                        help='Chaos command to run')
    parser.add_argument('--rate',     type=float, default=0.8,  help='Error rate 0-1 (default 0.8)')
    parser.add_argument('--ms',       type=int,   default=2000, help='Latency in ms (default 2000)')
    parser.add_argument('--duration', type=int,   default=60,   help='Duration in seconds (default 60)')
    parser.add_argument('--rps',      type=float, default=5.0,  help='Requests/sec for traffic (default 5)')
    args = parser.parse_args()

    cmd = args.command
    if cmd == 'errors':
        chaos_errors(rate=args.rate, duration=args.duration)
    elif cmd == 'latency':
        chaos_latency(ms=args.ms, duration=args.duration)
    elif cmd == 'cpu':
        chaos_cpu(duration=args.duration)
    elif cmd == 'full':
        chaos_full(duration=args.duration)
    elif cmd == 'reset':
        chaos_reset()
    elif cmd == 'traffic':
        generate_traffic(rps=args.rps, duration=args.duration)
    elif cmd == 'status':
        show_status()


if __name__ == '__main__':
    main()
