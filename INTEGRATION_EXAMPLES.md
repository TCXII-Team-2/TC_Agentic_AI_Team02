# Integration Examples & Recipes

## Using the Observability System

### 1. Basic Workflow with Monitoring

```bash
# Process a ticket and get trace_id
curl -X POST http://localhost:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Password reset issue",
    "content": "I cannot reset my password",
    "created_at": "2025-12-23",
    "userPlan": "Premium"
  }' | jq '{"trace_id": .trace_id, "duration_ms": .duration_ms, "success_rate": .response.quality_score}'
```

### 2. Monitor Real-Time System Health

```bash
#!/bin/bash
# monitor.sh - Real-time health monitoring

while true; do
  clear
  echo "=== System Health Dashboard ==="
  curl -s http://localhost:8000/monitoring/metrics | jq '{
    success_rate: .metrics.success_rate,
    avg_response_ms: .metrics.avg_request_duration_ms,
    total_requests: .metrics.total_requests,
    error_count: .metrics.failed_requests,
    avg_confidence: .metrics.avg_confidence_score
  }'
  
  echo ""
  echo "=== Agent Performance ==="
  curl -s http://localhost:8000/monitoring/agent-performance | jq '.agent_performance | to_entries[] | {agent: .key, avg_ms: .value.avg_latency_ms, max_ms: .value.max_latency_ms}'
  
  sleep 10
done
```

### 3. Custom Trace ID Tracking

```python
# Python client example
import requests
import uuid

trace_id = str(uuid.uuid4())

response = requests.post(
    'http://localhost:8000/workflow/run',
    json={
        'subject': 'My issue',
        'content': 'Details here',
        'created_at': '2025-12-23',
        'userPlan': 'Free'
    },
    headers={'X-Trace-ID': trace_id}
)

result = response.json()
print(f"Trace ID: {result['trace_id']}")
print(f"Duration: {result['duration_ms']}ms")
print(f"Quality Score: {result['response']['quality_score']}")

# Later: retrieve metrics for this trace
metrics = requests.get('http://localhost:8000/monitoring/metrics').json()
print(f"System success rate: {metrics['metrics']['success_rate']}%")
```

### 4. Bulk Batch Processing

```bash
#!/bin/bash
# Process multiple questions and track results

questions='[
  {"id": "q1", "query": "How do I reset my password?"},
  {"id": "q2", "query": "What is your pricing?"},
  {"id": "q3", "query": "Do you have a mobile app?"}
]'

response=$(curl -X POST http://localhost:8000/workflow/answer-questions \
  -H "Content-Type: application/json" \
  -d "{\"Questions\": $questions}")

echo "$response" | jq '.Answers[] | {id: .id, answer_length: (.answer | length)}'
```

### 5. Performance Analysis

```python
#!/usr/bin/env python3
# analyze_performance.py

import requests
import time

def analyze_performance():
    # Get current metrics
    metrics_resp = requests.get('http://localhost:8000/monitoring/metrics')
    metrics = metrics_resp.json()['metrics']
    
    perf_resp = requests.get('http://localhost:8000/monitoring/agent-performance')
    perf = perf_resp.json()['agent_performance']
    
    # Analyze results
    print("📊 Performance Report")
    print("=" * 50)
    print(f"Uptime: {metrics['uptime_seconds']:.1f}s")
    print(f"Total Requests: {metrics['total_requests']}")
    print(f"Success Rate: {metrics['success_rate']:.1f}%")
    print(f"Avg Response: {metrics['avg_request_duration_ms']:.1f}ms")
    print(f"Avg Confidence: {metrics['avg_confidence_score']:.2f}")
    print(f"Avg Quality: {metrics['avg_quality_score']:.2f}")
    
    print("\n🔧 Agent Performance")
    print("-" * 50)
    for agent, stats in perf.items():
        print(f"{agent:15} avg: {stats['avg_latency_ms']:7.1f}ms "
              f"(min: {stats['min_latency_ms']:6.1f}ms, "
              f"max: {stats['max_latency_ms']:7.1f}ms, "
              f"p95: {stats['p95_latency_ms']:7.1f}ms)")
    
    # Find bottleneck
    slowest_agent = max(perf.items(), key=lambda x: x[1]['avg_latency_ms'])
    print(f"\n⚠️  Slowest Agent: {slowest_agent[0]} "
          f"({slowest_agent[1]['avg_latency_ms']:.1f}ms avg)")

if __name__ == '__main__':
    analyze_performance()
```

### 6. Alert Integration

```python
#!/usr/bin/env python3
# alert_handler.py - Send alerts to external system

import requests
import json

def check_and_notify():
    metrics_resp = requests.get('http://localhost:8000/monitoring/metrics')
    data = metrics_resp.json()
    
    alerts = data.get('recent_alerts', [])
    
    for alert in alerts:
        if alert['severity'] == 'critical':
            # Send to Slack
            slack_message = {
                "text": f"🚨 {alert['type']}",
                "attachments": [{
                    "color": "danger",
                    "text": alert['message'],
                    "ts": alert['timestamp']
                }]
            }
            # requests.post(SLACK_WEBHOOK_URL, json=slack_message)
            print(json.dumps(slack_message, indent=2))
```

### 7. Circuit Breaker Monitoring

```bash
#!/bin/bash
# monitor_circuit_breakers.sh

while true; do
  echo "Checking circuit breakers..."
  
  status=$(curl -s http://localhost:8000/monitoring/circuit-breakers)
  
  echo "$status" | jq '.circuit_breakers | to_entries[] | 
    select(.value.state == "open") | 
    {
      agent: .key,
      state: .value.state,
      failures: .value.failure_count,
      alert: "⚠️  OPEN - Service degraded"
    }'
  
  echo "$status" | jq '.circuit_breakers | to_entries[] | 
    select(.value.state == "half_open") | 
    {
      agent: .key,
      state: .value.state,
      status: "Testing recovery..."
    }'
  
  sleep 30
done
```

### 8. Load Testing with Monitoring

```python
#!/usr/bin/env python3
# load_test.py

import asyncio
import aiohttp
import time
from datetime import datetime

async def load_test(concurrent_requests=10, duration_seconds=60):
    """Run load test and monitor metrics"""
    
    start_time = time.time()
    request_count = 0
    
    async def make_request(session):
        nonlocal request_count
        try:
            async with session.post(
                'http://localhost:8000/workflow/run',
                json={
                    'subject': f'Test {request_count}',
                    'content': 'Test content',
                    'created_at': '2025-12-23'
                }
            ) as resp:
                request_count += 1
                return await resp.json()
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration_seconds:
            # Spawn concurrent requests
            tasks = [make_request(session) for _ in range(concurrent_requests)]
            results = await asyncio.gather(*tasks)
            
            # Print progress
            elapsed = time.time() - start_time
            rate = request_count / elapsed
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Requests: {request_count}, Rate: {rate:.2f} req/s")
            
            # Check metrics every 10 seconds
            if int(elapsed) % 10 == 0:
                # metrics = await get_metrics()
                pass
            
            await asyncio.sleep(1)
    
    # Final report
    print(f"\n✅ Load test complete")
    print(f"Total requests: {request_count}")
    print(f"Duration: {time.time() - start_time:.1f}s")
    print(f"Throughput: {request_count / (time.time() - start_time):.2f} req/s")

if __name__ == '__main__':
    asyncio.run(load_test(concurrent_requests=5, duration_seconds=60))
```

### 9. Quality Assurance Dashboard

```html
<!-- dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Support AI - Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>System Monitoring Dashboard</h1>
    
    <div id="metrics"></div>
    <div id="agents"></div>
    <div id="alerts"></div>
    
    <script>
    async function updateMetrics() {
        const resp = await fetch('/monitoring/metrics');
        const data = await resp.json();
        
        document.getElementById('metrics').innerHTML = `
            <h2>System Metrics</h2>
            <p>Success Rate: ${data.metrics.success_rate.toFixed(1)}%</p>
            <p>Avg Response: ${data.metrics.avg_request_duration_ms.toFixed(1)}ms</p>
            <p>Confidence Score: ${data.metrics.avg_confidence_score.toFixed(2)}</p>
            <p>Total Requests: ${data.metrics.total_requests}</p>
        `;
        
        // Update alerts
        const alerts = data.recent_alerts || [];
        document.getElementById('alerts').innerHTML = `
            <h2>Active Alerts (${alerts.length})</h2>
            ${alerts.map(a => `
                <div style="color: ${a.severity === 'critical' ? 'red' : 'orange'}">
                    ${a.type}: ${a.message}
                </div>
            `).join('')}
        `;
    }
    
    // Update every 5 seconds
    setInterval(updateMetrics, 5000);
    updateMetrics();
    </script>
</body>
</html>
```

### 10. Automated Incident Response

```python
#!/usr/bin/env python3
# incident_responder.py

import requests
import time
import subprocess

def check_and_respond():
    """Automatically respond to incidents"""
    
    while True:
        try:
            # Check circuit breakers
            cb_resp = requests.get('http://localhost:8000/monitoring/circuit-breakers')
            cbs = cb_resp.json()['circuit_breakers']
            
            # Check for open circuits
            for agent, status in cbs.items():
                if status['state'] == 'open':
                    print(f"🚨 {agent} circuit is OPEN!")
                    
                    # Automatic mitigation
                    if agent == 'retriever':
                        print("  → Restarting database connection...")
                        # subprocess.run(['systemctl', 'restart', 'chromadb'])
                    
                    # Notify team
                    print("  → Sending alert to team...")
                    # send_slack_alert(f"Circuit {agent} is open", critical=True)
            
            # Check error rate
            metrics_resp = requests.get('http://localhost:8000/monitoring/metrics')
            metrics = metrics_resp.json()['metrics']
            
            if metrics['success_rate'] < 90:
                print(f"⚠️  Success rate dropped to {metrics['success_rate']:.1f}%")
                # Trigger investigation
                
        except Exception as e:
            print(f"Error in incident responder: {e}")
        
        time.sleep(30)  # Check every 30 seconds

if __name__ == '__main__':
    check_and_respond()
```

## Deployment Checklist

- [ ] All observability modules installed and imported
- [ ] Circuit breaker thresholds configured for environment
- [ ] Alert thresholds adjusted for SLA requirements
- [ ] Monitoring dashboard deployed
- [ ] Log aggregation service connected
- [ ] Alert routing configured (Slack, PagerDuty, etc.)
- [ ] Baseline metrics established
- [ ] On-call runbooks updated with trace ID usage
- [ ] Team trained on monitoring tools
- [ ] Performance targets documented

## Support

For issues or questions:
1. Check `OBSERVABILITY.md` for detailed documentation
2. Review `QUICK_REFERENCE.md` for API examples
3. Check logs with your trace ID: `grep trace_id logs.json`
4. Use `/monitoring/*` endpoints for real-time data
