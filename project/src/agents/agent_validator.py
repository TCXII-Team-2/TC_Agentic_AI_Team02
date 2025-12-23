import json
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel
from pydantic import BaseModel
from datetime import date

# Default category rules in case prompt output is thin or missing
DEFAULT_RULES: Dict[str, List[str]] = {
    "Technical": ["error_message", "steps_to_reproduce", "system_environment", "timestamp_of_issue"],
    "Billing": ["invoice_number", "charge_amount", "transaction_date", "payment_method"],
    "Access": ["username_or_email", "error_received", "device_browser_info", "time_of_failure"],
    "General": ["clear_question", "context_background", "specific_requirements"],
    "Refund": ["order_number", "purchase_date", "reason_for_refund", "refund_amount"],
}

class Ticket(BaseModel):
    content: str
    id: Optional[str] = None
    subject: str
    created_at: date
    userPlan: Optional[str] = None
class ValidationResult(str, Enum):
    VALID = "valid"
    NEEDS_MORE_INFO = "needs_more_info"
    OUT_OF_SCOPE = "out_of_scope"


class ValidationResponse(BaseModel):
    """Pydantic model for validation response"""
    is_valid: bool
    validation_status: str
    message_to_client: Optional[str] = None
    missing_details: List[str] = []
    confidence_score: float = 0.0
    escalation_reason: Optional[str] = None


class TicketValidator:
    def __init__(self):
        """Initialize the TicketValidator with Mistral model via pydantic_ai"""
        self.agent = Agent(
            model=MistralModel("mistral-small-latest"),
            output_type=ValidationResponse,  # Use result_type, not output_type
            system_prompt=self._get_instructions()  # Use system_prompt, not instructions
        )
        self.logger = logging.getLogger(__name__)
        self.validation_rules = DEFAULT_RULES

    def _get_instructions(self) -> str:
        """Load validation instructions from file"""
        readme_text = Path("project/src/config/prompts/agent_validator.md").read_text(encoding="utf-8")
        return readme_text

    

    async def validate(self, ticket_text: Any, analysis_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate a support ticket for completeness
        
        Args:
            ticket_text: The ticket content to validate
            analysis_result: Optional analysis results from QueryAnalyzer
            
        Returns:
            Dict containing validation results with required fields
        """
        try:
            self.logger.info("Starting ticket validation...")
            # Support both Ticket-like objects and raw text
            if hasattr(ticket_text, "subject") and hasattr(ticket_text, "content"):
                user_plan = getattr(ticket_text, "userPlan", None) or "N/A"
                created_at = getattr(ticket_text, "created_at", None)
                ticket_str = (
                    f"Subject: {ticket_text.subject}\n"
                    f"Content: {ticket_text.content}\n"
                    f"Created At: {created_at}\n"
                    f"User Plan: {user_plan}\n"
                )
            else:
                ticket_str = str(ticket_text)
            # Prepare input for the agent
            input_data = {
                "ticket": ticket_str,
                "analysis": analysis_result or {},
                "rules": self.validation_rules,
            }
            
            # Run validation - pydantic_ai.run() is async
            response = await self.agent.run(json.dumps(input_data, ensure_ascii=False))
            
            # Get the structured data from response
            validation_result = response.output.model_dump()
            
            # Check if analyzer flagged insufficient keywords
            if analysis_result and analysis_result.get("insufficient_keywords"):
                validation_result["is_valid"] = False
                validation_result["validation_status"] = ValidationResult.NEEDS_MORE_INFO.value
                validation_result["missing_details"] = ["More specific information needed - query is too vague"]
                validation_result["message_to_client"] = "Thank you for reaching out. Your query needs more details to provide an accurate response. Please provide more specific information about your issue."
            
            # Add metadata
            validation_result["validated_at"] = datetime.now().isoformat()
            validation_result.setdefault("missing_details", [])
            validation_result.setdefault("confidence_score", self._estimate_confidence(validation_result))
            validation_result.setdefault("escalation_reason", None)
            validation_result.setdefault("category", (analysis_result or {}).get("category"))
            validation_result.setdefault("urgency", (analysis_result or {}).get("urgency"))
            validation_result.setdefault("language", (analysis_result or {}).get("language"))
            
            
            # Validate the result structure
            self._validate_result(validation_result)
            
            # Determine final status
            validation_result["final_status"] = self._determine_final_status(validation_result)
            
            self.logger.info(f"Validation complete: {validation_result['validation_status']}")
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return self._create_default_response()

    def _create_default_response(self) -> Dict[str, Any]:
        """Create a default response when validation fails"""
        return {
            "is_valid": False,
            "validation_status": ValidationResult.NEEDS_MORE_INFO.value,
            "message_to_client": "Your ticket is too vague. Please provide more details.",
            "missing_details": [],
            "escalation_reason": None,
            "confidence_score": 0.0,
            "validated_at": datetime.now().isoformat(),
            "final_status": "INVALID"
        }

    def _estimate_confidence(self, result: Dict[str, Any]) -> float:
        """Heuristic confidence: lower if missing details, higher if valid."""
        if not result.get("is_valid"):
            missing = len(result.get("missing_details", []))
            return max(0.05, 0.6 - 0.1 * missing)
        return 0.9

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate that the result has all required fields with correct types"""
        required_fields = [
            "is_valid",
            "validation_status",
            "missing_details",
            "message_to_client",
        ]

        # Check all required fields exist
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate types
        if not isinstance(result["is_valid"], bool):
            raise ValueError(f"Field 'is_valid' must be bool, got {type(result['is_valid'])}")
        
        if not isinstance(result["validation_status"], str):
            raise ValueError(f"Field 'validation_status' must be str, got {type(result['validation_status'])}")
        
        if not isinstance(result["missing_details"], list):
            raise ValueError(f"Field 'missing_details' must be list, got {type(result['missing_details'])}")
        
        if result["message_to_client"] is not None and not isinstance(result["message_to_client"], str):
            raise ValueError(f"Field 'message_to_client' must be str or None, got {type(result['message_to_client'])}")
        
        # Validate status
        valid_statuses = [s.value for s in ValidationResult]
        if result["validation_status"] not in valid_statuses:
            raise ValueError(f"Invalid validation_status: {result['validation_status']}")
        
        
        return True

    def _determine_final_status(self, validation_result: Dict[str, Any]) -> str:
        """Determine the final status based on validation results"""
        if not validation_result.get("is_valid", False):
            if validation_result.get("missing_details"):
                return "NEEDS_INFO"
        return "APPROVED"

    def get_validation_report(self, validation_result: Dict[str, Any]) -> str:
        """Generate a human-readable validation report"""
        status_emoji = {
            "APPROVED": "✅",
            "NEEDS_INFO": "⚠️",
        }
        
        emoji = status_emoji.get(validation_result.get("final_status", ""), "📋")
        
        report = f"""
        {emoji} VALIDATION REPORT
        {'=' * 40}
        
        Status: {validation_result.get('final_status', 'UNKNOWN')}
        Confidence: {validation_result.get('confidence_score', 0):.2%}
        
        Category: {validation_result.get('category', 'Unknown')}
        Urgency: {validation_result.get('urgency', 'Medium')}
        
        Valid: {'Yes' if validation_result.get('is_valid') else 'No'}
        """
        
        if validation_result.get('missing_details'):
            report += f"\n        Missing Details:\n"
            for detail in validation_result['missing_details']:
                report += f"        - {detail}\n"
        
        if validation_result.get('message_to_client'):
            report += f"\n        Message to Client:\n        {validation_result['message_to_client']}\n"
        
        report += f"\n        {'=' * 40}\n        "
        
        return report