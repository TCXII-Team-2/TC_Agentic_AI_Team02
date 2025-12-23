import json
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel
from pydantic import BaseModel


class ConfidenceResult(BaseModel):
    """Pydantic model for confidence evaluation response"""
    confidence_score: float  # 0.0 to 1.0
    confidence_level: str  # "low", "medium", "high"
    should_escalate: bool
    escalation_reason: Optional[str] = None
    recommendation: str
    rag_reliability: str  # "reliable", "moderate", "unreliable"
    suggested_action: str  # "auto_respond", "escalate", "request_clarification"


class ConfidenceEvaluator:
    """
    4th Agent: Evaluates the confidence level of RAG agent output.
    Determines whether to escalate to human agents or proceed with auto-response.
    """

    def __init__(self):
        """Initialize the ConfidenceEvaluator with Mistral model"""
        self.agent = Agent(
            model=MistralModel("mistral-small-latest"),
            output_type=ConfidenceResult,
            system_prompt=self._get_instructions()
        )
        self.logger = logging.getLogger(__name__)

    def _get_instructions(self) -> str:
        """Load confidence evaluation instructions from file"""
        readme_text = Path("project/src/config/prompts/agent_confidence.md").read_text(encoding="utf-8")
        return readme_text

    async def evaluate_confidence(
        self,
        ticket_analysis: Dict[str, Any],
        rag_results: Dict[str, Any],
        original_ticket: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate the confidence level of RAG agent output
        
        Args:
            ticket_analysis: Analysis results from QueryAnalyzer
            rag_results: Results from the RAG agent (retriever)
            original_ticket: Optional original ticket data
            
        Returns:
            Dict containing confidence evaluation with recommended action
        """
        try:
            self.logger.info("Starting confidence evaluation...")
            
            # Prepare evaluation context
            evaluation_context = {
                "ticket_analysis": ticket_analysis,
                "rag_results": rag_results,
                "original_ticket": original_ticket or {}
            }
            
            # Create evaluation prompt
            evaluation_prompt = self._create_evaluation_prompt(evaluation_context)
            
            # Run confidence evaluation
            response = await self.agent.run(evaluation_prompt)
            
            # Get the structured result
            confidence_result = response.output.model_dump()
            
            # Add metadata
            confidence_result["evaluated_at"] = datetime.now().isoformat()
            confidence_result["evaluation_type"] = "rag_output_confidence"
            
            # Validate the result
            self._validate_result(confidence_result)
            
            # Determine final action
            confidence_result["final_action"] = self._determine_final_action(confidence_result)
            
            self.logger.info(
                f"Confidence evaluation complete: "
                f"Score={confidence_result['confidence_score']:.2%}, "
                f"Action={confidence_result['final_action']}"
            )
            
            return confidence_result
            
        except Exception as e:
            self.logger.error(f"Confidence evaluation failed: {str(e)}")
            return self._create_default_response()

    def _create_evaluation_prompt(self, context: Dict[str, Any]) -> str:
        """Create a structured prompt for confidence evaluation"""
        prompt = f"""
        Evaluate the confidence level of the RAG search results based on the following context:
        
        TICKET ANALYSIS:
        {json.dumps(context['ticket_analysis'], ensure_ascii=False, indent=2, default=str)}

        RAG SEARCH RESULTS:
        {json.dumps(context['rag_results'], ensure_ascii=False, indent=2, default=str)}

        ORIGINAL TICKET:
        {json.dumps(context['original_ticket'], ensure_ascii=False, indent=2, default=str)}
        
        Based on this information, provide your confidence evaluation following the instructions.
        """
        return prompt

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate that the result has all required fields"""
        required_fields = [
            "confidence_score",
            "confidence_level",
            "should_escalate",
            "recommendation",
            "rag_reliability",
            "suggested_action"
        ]
        
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate confidence score is between 0 and 1
        confidence = result["confidence_score"]
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            raise ValueError(f"Confidence score must be between 0 and 1, got {confidence}")
        
        # Validate confidence level
        valid_levels = ["low", "medium", "high"]
        if result["confidence_level"] not in valid_levels:
            raise ValueError(f"Invalid confidence level: {result['confidence_level']}")
        
        # Validate should_escalate is boolean
        if not isinstance(result["should_escalate"], bool):
            raise ValueError(f"Field 'should_escalate' must be bool")
        
        # Validate rag_reliability
        valid_reliability = ["reliable", "moderate", "unreliable"]
        if result["rag_reliability"] not in valid_reliability:
            raise ValueError(f"Invalid RAG reliability: {result['rag_reliability']}")
        
        # Validate suggested_action
        valid_actions = ["auto_respond", "escalate", "request_clarification", "out_of_scope"]
        if result["suggested_action"] not in valid_actions:
            raise ValueError(f"Invalid suggested action: {result['suggested_action']}")
        
        return True

    def _determine_final_action(self, confidence_result: Dict[str, Any]) -> str:
        """Determine the final action based on confidence evaluation"""
        suggested = confidence_result.get("suggested_action", "")
        
        if suggested == "out_of_scope":
            return "OUT_OF_SCOPE"
        elif confidence_result.get("should_escalate"):
            return "ESCALATE_TO_HUMAN"
        elif suggested == "request_clarification":
            return "REQUEST_CLARIFICATION"
        else:
            return "PROCEED_WITH_AUTO_RESPONSE"

    def _create_default_response(self) -> Dict[str, Any]:
        """Create a default response when evaluation fails"""
        return {
            "confidence_score": 0.0,
            "confidence_level": "low",
            "should_escalate": True,
            "escalation_reason": "Evaluation failed due to unexpected error",
            "recommendation": "Escalate to human agent for manual review",
            "rag_reliability": "unreliable",
            "suggested_action": "escalate",
            "final_action": "ESCALATE_TO_HUMAN",
            "evaluated_at": datetime.now().isoformat(),
            "evaluation_type": "rag_output_confidence"
        }

    def get_confidence_report(self, confidence_result: Dict[str, Any]) -> str:
        """Generate a human-readable confidence report"""
        action_emoji = {
            "ESCALATE_TO_HUMAN": "🔴",
            "REQUEST_CLARIFICATION": "🟡",
            "PROCEED_WITH_AUTO_RESPONSE": "🟢"
        }
        
        emoji = action_emoji.get(confidence_result.get("final_action", ""), "⚪")
        
        report = f"""
        {emoji} CONFIDENCE EVALUATION REPORT
        {'=' * 50}
        
        Confidence Score: {confidence_result.get('confidence_score', 0):.1%}
        Confidence Level: {confidence_result.get('confidence_level', 'Unknown').upper()}
        
        RAG Reliability: {confidence_result.get('rag_reliability', 'Unknown').upper()}
        Should Escalate: {'Yes' if confidence_result.get('should_escalate') else 'No'}
        
        Recommended Action: {confidence_result.get('suggested_action', 'Unknown').upper()}
        Final Action: {confidence_result.get('final_action', 'UNKNOWN')}
        
        Recommendation:
        {confidence_result.get('recommendation', 'No recommendation')}
        """
        
        if confidence_result.get('escalation_reason'):
            report += f"\n        Escalation Reason:\n        {confidence_result['escalation_reason']}\n"
        
        report += f"\n        {'=' * 50}\n        "
        
        return report
