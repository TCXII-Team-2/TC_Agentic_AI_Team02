import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: str
    name: str
    value: float
    labels: Dict[str, str]

class Metrics:
    """Metrics collection for monitoring."""
    
    def __init__(self):
        self.metrics: List[MetricPoint] = []
        self.start_time = time.time()
        
        # Counters
        self.request_count = 0
        self.error_count = 0
        self.success_count = 0
        
        # Timing
        self.request_durations: List[float] = []
        
        # Agent metrics
        self.agent_latencies: Dict[str, List[float]] = {
            'analyzer': [],
            'validator': [],
            'rag_retriever': [],
            'confidence': [],
            'response': []
        }
        
        # Quality metrics
        self.confidence_scores: List[float] = []
        self.response_quality_scores: List[float] = []
        
        # Cost tracking
        self.total_tokens_used = 0
        self.api_calls_count = 0
    
    def record_request(self, duration: float, success: bool = True, **labels) -> None:
        """Record a request metric."""
        self.request_count += 1
        self.request_durations.append(duration)
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        self.metrics.append(MetricPoint(
            timestamp=datetime.utcnow().isoformat(),
            name='request_duration_ms',
            value=duration * 1000,
            labels=labels
        ))
        
        logger.info(
            f"Request recorded - Duration: {duration*1000:.2f}ms, "
            f"Success: {success}, Total requests: {self.request_count}"
        )
    
    def record_agent_latency(self, agent_name: str, latency: float) -> None:
        """Record agent processing latency."""
        if agent_name in self.agent_latencies:
            self.agent_latencies[agent_name].append(latency)
        
        self.metrics.append(MetricPoint(
            timestamp=datetime.utcnow().isoformat(),
            name='agent_latency_ms',
            value=latency * 1000,
            labels={'agent': agent_name}
        ))
    
    def record_confidence_score(self, score: float) -> None:
        """Record confidence evaluation score."""
        self.confidence_scores.append(score)
        self.metrics.append(MetricPoint(
            timestamp=datetime.utcnow().isoformat(),
            name='confidence_score',
            value=score,
            labels={}
        ))
    
    def record_quality_score(self, score: float) -> None:
        """Record response quality score."""
        self.response_quality_scores.append(score)
        self.metrics.append(MetricPoint(
            timestamp=datetime.utcnow().isoformat(),
            name='response_quality_score',
            value=score,
            labels={}
        ))
    
    def record_token_usage(self, tokens: int) -> None:
        """Record API token usage."""
        self.total_tokens_used += tokens
        self.api_calls_count += 1
    
    def get_summary(self) -> Dict:
        """Get metrics summary."""
        avg_duration = sum(self.request_durations) / len(self.request_durations) if self.request_durations else 0
        uptime = time.time() - self.start_time
        
        agent_summaries = {}
        for agent, latencies in self.agent_latencies.items():
            if latencies:
                agent_summaries[agent] = {
                    'avg_latency_ms': sum(latencies) / len(latencies) * 1000,
                    'min_latency_ms': min(latencies) * 1000,
                    'max_latency_ms': max(latencies) * 1000,
                    'call_count': len(latencies)
                }
        
        return {
            'uptime_seconds': uptime,
            'total_requests': self.request_count,
            'successful_requests': self.success_count,
            'failed_requests': self.error_count,
            'success_rate': (self.success_count / self.request_count * 100) if self.request_count > 0 else 0,
            'avg_request_duration_ms': avg_duration * 1000,
            'total_tokens_used': self.total_tokens_used,
            'api_calls_count': self.api_calls_count,
            'avg_confidence_score': sum(self.confidence_scores) / len(self.confidence_scores) if self.confidence_scores else 0,
            'avg_quality_score': sum(self.response_quality_scores) / len(self.response_quality_scores) if self.response_quality_scores else 0,
            'agent_metrics': agent_summaries
        }

class Tracer:
    """End-to-end request tracing."""
    
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.spans: List[Dict] = []
        self.start_time = time.time()
    
    def add_span(self, name: str, component: str, duration: float, status: str = "success", **metadata) -> None:
        """Add a span to the trace."""
        span = {
            'trace_id': self.trace_id,
            'span_name': name,
            'component': component,
            'timestamp': datetime.utcnow().isoformat(),
            'duration_ms': duration * 1000,
            'status': status,
            **metadata
        }
        self.spans.append(span)
        
        logger.info(f"Span added - {name} ({component}): {duration*1000:.2f}ms [{status}]")
    
    def get_trace(self) -> Dict:
        """Get complete trace data."""
        total_duration = time.time() - self.start_time
        return {
            'trace_id': self.trace_id,
            'total_duration_ms': total_duration * 1000,
            'span_count': len(self.spans),
            'spans': self.spans
        }

class AlertManager:
    """Alert management for critical conditions."""
    
    def __init__(self, thresholds: Optional[Dict] = None):
        self.thresholds = thresholds or {
            'error_rate_percent': 10,  # Alert if >10% errors
            'response_time_ms': 5000,  # Alert if avg response time > 5s
            'confidence_score': 0.5,   # Alert if avg confidence < 0.5
        }
        self.alerts: List[Dict] = []
    
    def check_metrics(self, metrics_summary: Dict) -> List[Dict]:
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        
        # Check error rate
        error_rate = (metrics_summary.get('failed_requests', 0) / 
                     metrics_summary.get('total_requests', 1) * 100)
        if error_rate > self.thresholds['error_rate_percent']:
            alerts.append({
                'type': 'HIGH_ERROR_RATE',
                'severity': 'critical',
                'message': f"Error rate {error_rate:.2f}% exceeds threshold {self.thresholds['error_rate_percent']}%",
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Check response time
        avg_response = metrics_summary.get('avg_request_duration_ms', 0)
        if avg_response > self.thresholds['response_time_ms']:
            alerts.append({
                'type': 'HIGH_RESPONSE_TIME',
                'severity': 'warning',
                'message': f"Avg response time {avg_response:.2f}ms exceeds threshold {self.thresholds['response_time_ms']}ms",
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Check confidence
        avg_confidence = metrics_summary.get('avg_confidence_score', 1.0)
        if avg_confidence < self.thresholds['confidence_score']:
            alerts.append({
                'type': 'LOW_CONFIDENCE',
                'severity': 'warning',
                'message': f"Avg confidence score {avg_confidence:.2f} below threshold {self.thresholds['confidence_score']}",
                'timestamp': datetime.utcnow().isoformat()
            })
        
        self.alerts.extend(alerts)
        for alert in alerts:
            logger.warning(f"Alert: {alert['type']} - {alert['message']}")
        
        return alerts

# Global instances
_metrics: Optional[Metrics] = None
_alert_manager: Optional[AlertManager] = None

def get_metrics() -> Metrics:
    """Get or create global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics

def get_alert_manager() -> AlertManager:
    """Get or create global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
