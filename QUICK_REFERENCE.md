# Quick Reference: Error Handling & Observability

## Key Features Added

### 1. **Circuit Breaker Protection**
- Automatic failure detection (3 failures threshold)
- Graceful request rejection when circuit OPEN
- Auto-recovery after 60 seconds
- Applied to all 5 agents (analyzer, validator, retriever, confidence, responder)

### 2. **Intelligent Fallbacks**
- RAG retriever returns empty results on failure (doesn't crash workflow)
- Bulk Q&A endpoint continues processing on individual failures
- Graceful degradation instead of complete failures

### 3. **Structured Logging**
- All logs in JSON format
- Trace ID propagation across all requests
- Automatic X-Trace-ID header in all responses
- Custom fields support for contextual logging

### 4. **End-to-End Tracing**
- Each request gets unique trace ID
- 5 spans per request (one per agent)
- Includes execution time, status, and metadata
- Available in response: `"trace_id": "...", "duration_ms": 2450.5`

### 5. **Comprehensive Metrics**
- Request count, error rate, success rate
- Per-agent latency (avg/min/max/P95)
- Quality scores (confidence, response quality)
- API token usage tracking

### 6. **Alert System**
- High error rate (>10%) → Critical
- Slow responses (>5000ms avg) → Warning
- Low confidence (<0.5 avg) → Warning
- Alerts included in metrics endpoint

## New API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check with success rate |
| `POST /workflow/run` | Main workflow (with monitoring) |
| `POST /workflow/answer-questions` | Bulk Q&A with error resilience |
| `GET /monitoring/metrics` | Overall system metrics |
| `GET /monitoring/agent-performance` | Per-agent latency stats |
| `GET /monitoring/quality` | Confidence & quality scores |
| `GET /monitoring/circuit-breakers` | Circuit breaker status |

## Code Examples

### Check System Health

```bash
curl http://localhost:8000/monitoring/metrics
```

### Process Ticket with Trace ID

```bash
curl -X POST http://localhost:8000/workflow/run \
  -H "Content-Type: application/json" \
  -H "X-Trace-ID: my-request-123" \
  -d '{
    "subject": "Password reset",
    "content": "I forgot my password",
    "created_at": "2025-12-23",
    "userPlan": "Free"
  }'
```

Response includes:
```json
{
  "trace_id": "my-request-123",
  "duration_ms": 2450.5,
  "analysis": {...},
  "validation": {...},
  "rag": [...],
  "confidence": {...},
  "response": {...}
}
```

### Monitor Agent Performance

```bash
curl http://localhost:8000/monitoring/agent-performance
```

Response:
```json
{
  "agent_performance": {
    "analyzer": {
      "call_count": 245,
      "avg_latency_ms": 320.5,
      "min_latency_ms": 250.0,
      "max_latency_ms": 800.0,
      "p95_latency_ms": 650.0
    },
    "confidence": {
      "call_count": 200,
      "avg_latency_ms": 450.2,
      ...
    }
  }
}
```

### Check Circuit Breaker Status

```bash
curl http://localhost:8000/monitoring/circuit-breakers
```

Response:
```json
{
  "circuit_breakers": {
    "analyzer": {"state": "closed", "failure_count": 0, "success_count": 245},
    "validator": {"state": "closed", "failure_count": 0, "success_count": 245},
    "retriever": {"state": "half_open", "failure_count": 3, "success_count": 200},
    "confidence": {"state": "closed", "failure_count": 0, "success_count": 200},
    "responder": {"state": "closed", "failure_count": 0, "success_count": 200}
  }
}
```

## Configuration

### Adjusting Circuit Breaker Thresholds

Edit [project/src/api/main.py](project/src/api/main.py#L40-L48):

```python
circuit_breakers = {
    'analyzer': CircuitBreaker(max_failures=3, timeout=60, name='analyzer'),
    # max_failures: number of consecutive failures before opening
    # timeout: seconds to wait before attempting recovery
}
```

### Customizing Alert Thresholds

In `monitoring.py`, modify `AlertManager` thresholds:

```python
thresholds = {
    'error_rate_percent': 10,  # Alert if > 10% errors
    'response_time_ms': 5000,  # Alert if avg response > 5s
    'confidence_score': 0.5,   # Alert if avg confidence < 0.5
}
```

## Key Files

| File | Purpose |
|------|---------|
| [project/src/utils/logging_config.py](project/src/utils/logging_config.py) | Structured logging, trace IDs |
| [project/src/utils/circuit_breaker.py](project/src/utils/circuit_breaker.py) | Circuit breaker pattern, retries |
| [project/src/utils/monitoring.py](project/src/utils/monitoring.py) | Metrics collection, alerting |
| [project/src/api/main.py](project/src/api/main.py) | API integration of all features |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Comprehensive documentation |

## Benefits

🛡️ **Resilience**: System continues working even when agents fail  
📊 **Visibility**: Complete view of system behavior and performance  
🚨 **Alerting**: Proactive notification of issues  
🔍 **Debugging**: Trace IDs link logs across entire request  
⚡ **Performance**: Per-agent latency tracking for optimization  
💡 **Intelligence**: Data-driven insights for improvements  

## Testing Observability

### Simulate Agent Failure

The circuit breaker will track consecutive failures and eventually OPEN the circuit:

```bash
# Send requests that cause failures
for i in {1..5}; do
  curl -X POST http://localhost:8000/workflow/run \
    -H "Content-Type: application/json" \
    -d '{"subject": "test", "content": "test", "created_at": "2025-12-23"}'
done

# Check circuit breaker status
curl http://localhost:8000/monitoring/circuit-breakers
# Should show agent with state: "open"
```

### Monitor Real-Time Metrics

```bash
while true; do
  curl -s http://localhost:8000/monitoring/metrics | jq '.metrics | {success_rate, avg_request_duration_ms, avg_confidence_score}'
  sleep 5
done
```

## Production Readiness Checklist

✅ Circuit breakers on all agents  
✅ Intelligent fallbacks and graceful degradation  
✅ Structured logging with trace IDs  
✅ End-to-end request tracing  
✅ Comprehensive metrics collection  
✅ Alert system for critical conditions  
✅ Per-agent performance monitoring  
✅ Bulk processing error resilience  
✅ Health check endpoint  
✅ Documented best practices  

Your system is production-ready! 🚀
