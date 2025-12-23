# Pipeline Error Handling, Monitoring & Observability

## Overview

The system now includes comprehensive error handling, circuit breaker patterns, and end-to-end observability with structured logging, metrics collection, and alerting capabilities.

## 1. Error Handling & Resilience

### Circuit Breaker Pattern

Each agent (analyzer, validator, retriever, confidence, responder) is protected by a circuit breaker that:

- **Tracks Failures**: Records consecutive failures up to `max_failures` threshold (default: 3)
- **Open State**: Rejects requests when failure threshold is exceeded
- **Half-Open State**: After `timeout` seconds (default: 60s), allows one test request
- **Recovery**: Returns to CLOSED state on successful test request

```python
# Example: Circuit breaker in workflow
confidence = await circuit_breakers['confidence'].call_async(
    confidence_agent.evaluate_confidence,
    ticket_analysis=analysis,
    rag_results=rag_results,
    original_ticket=a_ticket.model_dump(),
)
```

### Intelligent Fallbacks

- **RAG Retrieval Fallback**: If retriever fails, returns empty results and continues workflow
- **Request Continuation**: Individual question failures in bulk endpoint don't break entire batch
- **Graceful Degradation**: System returns partial results rather than complete failures

```python
try:
    rag_results = await circuit_breakers['retriever'].call_async(...)
except Exception as e:
    logger.error(f"RAG Retriever failed: {str(e)}")
    rag_results = []  # Fallback to empty
```

### Retry Logic

Decorators for automatic retry with exponential backoff:

```python
@retry_with_backoff(max_retries=3, backoff_factor=1.0)
async def some_operation():
    # Automatically retried up to 3 times with exponential backoff
    pass
```

## 2. Structured Logging with Trace IDs

### Features

- **Trace IDs**: Unique identifier per request for end-to-end request tracking
- **Context Variables**: Thread-safe trace ID propagation across async operations
- **JSON Output**: Structured logs for easy parsing and monitoring

### Trace ID Middleware

Automatically injected into all HTTP requests:

```
X-Trace-ID: 550e8400-e29b-41d4-a716-446655440000
```

### Logging Example

```python
logger.info(f"[{trace_id}] Analysis complete: {len(analysis.get('keywords', []))} keywords")
# Output: {"timestamp": "2025-12-23T10:30:45.123456", "level": "INFO", "trace_id": "550e8400...", ...}
```

## 3. Metrics & Performance Monitoring

### Collected Metrics

#### Request Metrics
- `request_count`: Total requests processed
- `error_count`: Failed requests
- `success_count`: Successful requests
- `success_rate`: Percentage of successful requests
- `avg_request_duration_ms`: Average response time

#### Agent Latencies (per-agent tracking)
- Call count for each agent
- Min/avg/max/P95 latency per agent
- Agents: analyzer, validator, rag_retriever, confidence, response

#### Quality Metrics
- `avg_confidence_score`: Average confidence evaluation score (0.0-1.0)
- `avg_quality_score`: Average response quality score (0.0-1.0)

#### Cost Tracking
- `total_tokens_used`: Cumulative API tokens
- `api_calls_count`: Number of API calls

### Accessing Metrics

```bash
# Overall metrics summary
GET /monitoring/metrics

# Per-agent performance
GET /monitoring/agent-performance

# Quality metrics
GET /monitoring/quality

# Circuit breaker status
GET /monitoring/circuit-breakers
```

### Example Metric Response

```json
{
  "uptime_seconds": 3600.45,
  "total_requests": 250,
  "successful_requests": 245,
  "failed_requests": 5,
  "success_rate": 98.0,
  "avg_request_duration_ms": 2450.5,
  "total_tokens_used": 125000,
  "api_calls_count": 500,
  "avg_confidence_score": 0.82,
  "avg_quality_score": 0.87,
  "agent_metrics": {
    "analyzer": {
      "avg_latency_ms": 320.5,
      "min_latency_ms": 250.0,
      "max_latency_ms": 800.0,
      "call_count": 250
    }
  }
}
```

## 4. End-to-End Tracing

### Trace Structure

Each request creates a trace containing spans for:
1. **analyze_query** (analyzer agent)
2. **validate** (validator agent)
3. **retrieve** (RAG retriever agent)
4. **evaluate_confidence** (confidence agent)
5. **generate_response** (response agent)

Each span includes:
- Execution duration
- Success/failure status
- Relevant metadata (result counts, scores, errors)

### Span Information

```python
tracer.add_span(
    name='analyze_query',
    component='analyzer',
    duration=0.325,  # seconds
    status='success',
    keywords_count=8
)
```

## 5. Alerting System

### Alert Types

| Alert Type | Severity | Condition |
|-----------|----------|-----------|
| HIGH_ERROR_RATE | Critical | Error rate > 10% |
| HIGH_RESPONSE_TIME | Warning | Avg response > 5000ms |
| LOW_CONFIDENCE | Warning | Avg confidence < 0.5 |

### Customizing Thresholds

```python
alert_manager = AlertManager(thresholds={
    'error_rate_percent': 10,
    'response_time_ms': 5000,
    'confidence_score': 0.5,
})
```

### Accessing Alerts

Alerts are returned in metrics endpoint and logged:

```bash
GET /monitoring/metrics

# Response includes:
{
  "recent_alerts": [
    {
      "type": "HIGH_ERROR_RATE",
      "severity": "critical",
      "message": "Error rate 15.5% exceeds threshold 10%",
      "timestamp": "2025-12-23T10:45:30.123456"
    }
  ]
}
```

## 6. Workflow Integration

### Request Flow with Observability

```
1. Middleware: Inject trace_id
   ↓
2. /workflow/run endpoint: Create tracer
   ↓
3. Each agent execution:
   - Try: Call with circuit breaker
   - Record: Agent latency metric
   - Trace: Add span with duration/status
   - On failure: Log error, attempt fallback
   ↓
4. Final response:
   - Record: Request metrics
   - Check: Alert thresholds
   - Return: trace_id in response header + body
```

### Workflow Response Example

```json
{
  "analysis": {...},
  "validation": {...},
  "rag": [...],
  "confidence": {...},
  "response": {...},
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "duration_ms": 2450.5
}
```

## 7. Database Resilience

The RAG retriever is protected by:
- **Circuit breaker**: Fails gracefully after 3 consecutive failures
- **Fallback strategy**: Returns empty results instead of crashing workflow
- **Retry logic**: Automatic retry with exponential backoff on transient failures

## 8. Bulk Processing Robustness

The `/workflow/answer-questions` endpoint ensures:
- **Per-question error handling**: Individual failures don't stop batch
- **Graceful fallback**: Failed questions get standard error message
- **Logging**: All failures are logged with context
- **Partial success**: Returns all successful + error responses

```python
for q in payload.Questions:
    try:
        # Process question
        answers.append({"id": q.id, "answer": result})
    except Exception as e:
        # Log and continue
        logger.error(f"Failed to process question {q.id}: {str(e)}")
        answers.append({"id": q.id, "answer": "Error processing question"})
```

## 9. Monitoring Dashboard Data

Recommended metrics to track on dashboards:

### Real-Time Monitoring
- Current request rate (req/s)
- Error rate (%)
- P95 response latency (ms)
- Active circuit breaker states

### Health Indicators
- Success rate (target: >95%)
- Avg confidence score (target: >0.7)
- Avg response quality (target: >0.8)

### Resource Usage
- Total API tokens consumed
- Cost per request
- Uptime percentage

## 10. Logging Best Practices

### Structured Context

```python
logger.info(
    f"[{trace_id}] Query analyzed",
    extra={'custom_fields': {
        'keywords_count': 8,
        'language': 'English',
        'processing_time_ms': 320.5
    }}
)
```

### Error Logging with Full Context

```python
try:
    result = await some_operation()
except Exception as e:
    logger.error(
        f"[{trace_id}] Operation failed",
        extra={'custom_fields': {
            'error': str(e),
            'operation': 'rag_retrieval',
            'retry_attempt': 2
        }}
    )
```

## Usage Examples

### Getting Trace ID from Response

```bash
curl -X POST http://localhost:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "How do I reset?",
    "content": "I forgot my password",
    "created_at": "2025-12-23",
    "userPlan": "Free"
  }' \
  -H "X-Trace-ID: my-custom-trace-123"

# Response header contains: X-Trace-ID: my-custom-trace-123
# Response body includes: "trace_id": "my-custom-trace-123"
```

### Monitoring Circuit Breaker Health

```bash
curl http://localhost:8000/monitoring/circuit-breakers

# Response:
{
  "circuit_breakers": {
    "analyzer": {
      "state": "closed",
      "failure_count": 0,
      "success_count": 245
    },
    "confidence": {
      "state": "half_open",
      "failure_count": 3,
      "success_count": 242
    }
  }
}
```

### Tracking Agent Performance

```bash
curl http://localhost:8000/monitoring/agent-performance

# Find slowest agents and latency issues
```

## Summary

The enhanced pipeline provides:

✅ **Resilience**: Circuit breakers, fallbacks, automatic retries  
✅ **Observability**: Structured logging, trace IDs, end-to-end tracing  
✅ **Metrics**: Comprehensive performance and quality tracking  
✅ **Alerting**: Automatic alerts on critical thresholds  
✅ **Robustness**: Fault-tolerant bulk processing, graceful degradation  

All components work together to ensure production-ready reliability and visibility into system behavior.
