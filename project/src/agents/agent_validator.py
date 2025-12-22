import json
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel
from pydantic import BaseModel


class ValidationResult(str, Enum):
    VALID = "valid"
    NEEDS_MORE_INFO = "needs_more_info"
    INVALID = "invalid"
    ESCALATE = "escalate_to_human"


class ValidationResponse(BaseModel):
    """Pydantic model for validation response"""
    is_valid: bool
    validation_status: str
    missing_details: List[str]
    escalation_reason: Optional[str] = None
    message_to_client: Optional[str] = None
    confidence_score: float


class TicketValidator:
    def __init__(self):
        """Initialize the TicketValidator with Mistral model via pydantic_ai"""
        self.agent = Agent(
            model=MistralModel("mistral-small-latest"),
            output_type=ValidationResponse,  # Use result_type, not output_type
            system_prompt=self._get_instructions()  # Use system_prompt, not instructions
        )
        self.logger = logging.getLogger(__name__)
        self.validation_rules = self._get_validation_rules()

    def _get_instructions(self) -> str:
        """Load validation instructions from file"""
        readme_text = Path("project/src/config/prompts/agent_validator.md").read_text(encoding="utf-8")
        return readme_text

    def _get_validation_rules(self) -> Dict[str, List[str]]:
        """Define validation rules for each ticket category"""
        return {
            "Technical": [
                "error_message",
                "steps_to_reproduce", 
                "system_environment",
                "timestamp_of_issue"
            ],
            "Billing": [
                "invoice_number",
                "charge_amount",
                "transaction_date",
                "payment_method"
            ],
            "Access": [
                "username_or_email",
                "error_received",
                "device_browser_info",
                "time_of_failure"
            ],
            "General": [
                "clear_question",
                "context_background",
                "specific_requirements"
            ],
            "Refund": [
                "order_number",
                "purchase_date",
                "reason_for_refund",
                "refund_amount"
            ]
        }

    async def validate(self, ticket_text: str, analysis_result: Optional[Dict] = None) -> Dict[str, Any]:
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
            
            # Prepare input for the agent
            input_data = {
                "ticket": ticket_text,
                "analysis": analysis_result or {},
                "validation_rules": self.validation_rules
            }
            
            # Run validation - pydantic_ai.run() is async
            response = await self.agent.run(json.dumps(input_data, ensure_ascii=False))
            
            # Get the structured data from response
            validation_result = response.output.model_dump()
            
            # Add metadata
            validation_result["validated_at"] = datetime.now().isoformat()
            validation_result["ticket_length"] = len(ticket_text)
            
            if analysis_result:
                validation_result["category"] = analysis_result.get("category", "Unknown")
                validation_result["urgency"] = analysis_result.get("urgency", "Medium")
            
            # Validate the result structure
            self._validate_result(validation_result)
            
            # Determine final status
            validation_result["final_status"] = self._determine_final_status(validation_result)
            
            self.logger.info(f"Validation complete: {validation_result['validation_status']}")
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return self._create_default_response(ticket_text, str(e))

    def _create_default_response(self, ticket_text: str, error_msg: str) -> Dict[str, Any]:
        """Create a default response when validation fails"""
        return {
            "is_valid": False,
            "validation_status": ValidationResult.ESCALATE.value,
            "missing_details": ["Unable to process ticket automatically"],
            "escalation_reason": f"Validation error: {error_msg}",
            "message_to_client": "Your ticket is being reviewed by our support team.",
            "confidence_score": 0.0,
            "validated_at": datetime.now().isoformat(),
            "ticket_length": len(ticket_text),
            "final_status": "ESCALATED"
        }

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate that the result has all required fields with correct types"""
        required_fields = [
            "is_valid",
            "validation_status",
            "missing_details",
            "escalation_reason",
            "message_to_client",
            "confidence_score"
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
        
        # Optional fields - can be None or str
        if result["escalation_reason"] is not None and not isinstance(result["escalation_reason"], str):
            raise ValueError(f"Field 'escalation_reason' must be str or None, got {type(result['escalation_reason'])}")
        
        if result["message_to_client"] is not None and not isinstance(result["message_to_client"], str):
            raise ValueError(f"Field 'message_to_client' must be str or None, got {type(result['message_to_client'])}")
        
        # Numeric field
        if not isinstance(result["confidence_score"], (int, float)):
            raise ValueError(f"Field 'confidence_score' must be int or float, got {type(result['confidence_score'])}")
        
        # Validate status
        valid_statuses = [s.value for s in ValidationResult]
        if result["validation_status"] not in valid_statuses:
            raise ValueError(f"Invalid validation_status: {result['validation_status']}")
        
        # Validate confidence score
        if not 0 <= result["confidence_score"] <= 1:
            raise ValueError(f"confidence_score must be between 0 and 1, got {result['confidence_score']}")
        
        return True

    def _determine_final_status(self, validation_result: Dict[str, Any]) -> str:
        """Determine the final status based on validation results"""
        if not validation_result.get("is_valid", False):
            if validation_result.get("escalation_reason"):
                return "ESCALATED"
            elif validation_result.get("missing_details"):
                return "NEEDS_INFO"
            else:
                return "INVALID"
        return "APPROVED"

    def get_validation_report(self, validation_result: Dict[str, Any]) -> str:
        """Generate a human-readable validation report"""
        status_emoji = {
            "APPROVED": "✅",
            "NEEDS_INFO": "⚠️",
            "INVALID": "❌",
            "ESCALATED": "🚨"
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
        
        if validation_result.get('escalation_reason'):
            report += f"\n        Escalation Reason: {validation_result['escalation_reason']}\n"
        
        if validation_result.get('message_to_client'):
            report += f"\n        Message to Client:\n        {validation_result['message_to_client']}\n"
        
        report += f"\n        {'=' * 40}\n        "
        
        return report