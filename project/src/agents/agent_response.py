import json
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel
from pydantic import BaseModel


class ResponseOutput(BaseModel):
    """Pydantic model for the response agent output"""
    response_text: str
    response_tone: str  # "professional", "friendly", "empathetic"
    includes_solution: bool
    includes_next_steps: bool
    includes_contact_info: bool
    language: str
    response_type: str  # "solution", "escalation_notice", "clarification_request"


class ResponseGenerator:
    """
    5th Agent: Generates formal, professional responses to clients.
    Takes ticket analysis and RAG results to create appropriate client-facing messages.
    """

    def __init__(self):
        """Initialize the ResponseGenerator with Mistral model"""
        self.agent = Agent(
            model=MistralModel("mistral-small-latest"),
            output_type=ResponseOutput,
            system_prompt=self._get_instructions()
        )
        self.logger = logging.getLogger(__name__)

    def _get_instructions(self) -> str:
        """Load response generation instructions from file"""
        readme_text = Path("project/src/config/prompts/agent_response.md").read_text(encoding="utf-8")
        return readme_text

    async def generate_response(
        self,
        ticket_analysis: Dict[str, Any],
        rag_results: Optional[Dict[str, Any]] = None,
        confidence_evaluation: Optional[Dict[str, Any]] = None,
        original_ticket: Optional[Dict[str, Any]] = None,
        response_type: str = "solution"
    ) -> Dict[str, Any]:
        """
        Generate a formal response to the client
        
        Args:
            ticket_analysis: Analysis results from QueryAnalyzer
            rag_results: Results from RAG agent (optional)
            confidence_evaluation: Results from confidence evaluator (optional)
            original_ticket: Original ticket data (optional)
            response_type: Type of response (solution, escalation_notice, clarification_request)
            
        Returns:
            Dict containing the generated response and metadata
        """
        try:
            self.logger.info(f"Starting response generation (type: {response_type})...")
            
            # Prepare response context
            response_context = {
                "ticket_analysis": ticket_analysis,
                "rag_results": rag_results or {},
                "confidence_evaluation": confidence_evaluation or {},
                "original_ticket": original_ticket or {},
                "response_type": response_type
            }
            
            # Create response generation prompt
            response_prompt = self._create_response_prompt(response_context)
            
            # Run response generation
            response = await self.agent.run(response_prompt)
            
            # Get the structured result
            response_result = response.output.model_dump()
            
            # Add metadata
            response_result["generated_at"] = datetime.now().isoformat()
            response_result["response_type"] = response_type
            response_result["ticket_category"] = ticket_analysis.get("category", "Unknown")
            response_result["ticket_language"] = ticket_analysis.get("language", "English")
            
            # Validate the result
            self._validate_result(response_result)
            
            # Ensure response quality
            response_result["is_complete"] = self._validate_response_completeness(response_result)
            response_result["quality_score"] = self._calculate_quality_score(response_result)
            
            self.logger.info(
                f"Response generation complete. "
                f"Type: {response_type}, Quality: {response_result['quality_score']:.1%}"
            )
            
            return response_result
            
        except Exception as e:
            self.logger.error(f"Response generation failed: {str(e)}")
            return self._create_default_response(response_type)

    def _create_response_prompt(self, context: Dict[str, Any]) -> str:
        """Create a structured prompt for response generation"""
        
        response_type = context.get("response_type", "solution")
        
        prompt = f"""
        Generate a formal, professional client response based on the following information:
        
        TICKET ANALYSIS:
        {json.dumps(context['ticket_analysis'], ensure_ascii=False, indent=2, default=str)}
        
        RAG KNOWLEDGE BASE RESULTS:
        {json.dumps(context['rag_results'], ensure_ascii=False, indent=2, default=str)}
        
        CONFIDENCE EVALUATION:
        {json.dumps(context['confidence_evaluation'], ensure_ascii=False, indent=2, default=str)}
        
        ORIGINAL TICKET:
        {json.dumps(context['original_ticket'], ensure_ascii=False, indent=2, default=str)}
        
        RESPONSE TYPE: {response_type.upper()}
        
        Generate a response following the instructions provided in your system prompt.
        Ensure the response is appropriate for the response type and customer language preference.
        """
        return prompt

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate that the result has all required fields"""
        required_fields = [
            "response_text",
            "response_tone",
            "includes_solution",
            "includes_next_steps",
            "includes_contact_info",
            "language",
            "response_type"
        ]
        
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate response text is not empty
        if not result["response_text"] or len(result["response_text"].strip()) < 10:
            raise ValueError("Response text must be at least 10 characters")
        
        # Validate response tone
        valid_tones = ["professional", "friendly", "empathetic"]
        if result["response_tone"] not in valid_tones:
            raise ValueError(f"Invalid response tone: {result['response_tone']}")
        
        # Validate boolean fields
        for field in ["includes_solution", "includes_next_steps", "includes_contact_info"]:
            if not isinstance(result[field], bool):
                raise ValueError(f"Field '{field}' must be boolean")
        
        # Validate response type
        valid_types = ["solution", "escalation_notice", "clarification_request", "out_of_scope"]
        if result["response_type"] not in valid_types:
            raise ValueError(f"Invalid response type: {result['response_type']}")
        
        return True

    def _validate_response_completeness(self, response_result: Dict[str, Any]) -> bool:
        """Validate that the response is complete based on its type"""
        response_type = response_result.get("response_type", "solution")
        
        if response_type == "solution":
            # Solution responses should include solution and next steps
            return response_result.get("includes_solution", False)
        elif response_type == "escalation_notice":
            # Escalation notices should include contact info and explanation
            return response_result.get("includes_contact_info", False)
        elif response_type == "clarification_request":
            # Clarification requests should ask for more info
            return len(response_result.get("response_text", "")) > 20
        
        return True

    def _calculate_quality_score(self, response_result: Dict[str, Any]) -> float:
        """Calculate a quality score for the generated response (0.0 to 1.0)"""
        score = 0.0
        max_points = 0
        
        # Check response length (0.2 points)
        response_len = len(response_result.get("response_text", ""))
        if response_len >= 100:
            score += 0.2
            max_points += 0.2
        elif response_len >= 50:
            score += 0.1
            max_points += 0.2
        
        # Check includes solution (0.25 points)
        if response_result.get("includes_solution"):
            score += 0.25
        max_points += 0.25
        
        # Check includes next steps (0.25 points)
        if response_result.get("includes_next_steps"):
            score += 0.25
        max_points += 0.25
        
        # Check includes contact info (0.15 points)
        if response_result.get("includes_contact_info"):
            score += 0.15
        max_points += 0.15
        
        # Check response tone appropriateness (0.15 points)
        if response_result.get("response_tone") in ["professional", "empathetic"]:
            score += 0.15
        max_points += 0.15
        
        # Normalize to 0.0-1.0 range
        return (score / max_points) if max_points > 0 else 0.0

    def _create_default_response(self, response_type: str) -> Dict[str, Any]:
        """Create a default response when generation fails"""
        
        if response_type == "escalation_notice":
            default_text = (
                "Thank you for contacting our support team. Your ticket has been escalated to a senior support specialist "
                "who will provide you with a comprehensive response. We appreciate your patience and will get back to you shortly."
            )
        elif response_type == "clarification_request":
            default_text = (
                "Thank you for reaching out. To better assist you, could you please provide additional details about your issue? "
                "This will help us offer you a more accurate solution."
            )
        elif response_type == "out_of_scope":
            default_text = (
                "Thank you for contacting us. Your question appears to be outside the scope of our support services. "
                "If you have questions about our product or service, please feel free to rephrase your question."
            )
        else:
            default_text = (
                "Thank you for contacting our support team. We are working on your request "
                "and will provide you with a solution as soon as possible."
            )
        
        return {
            "response_text": default_text,
            "response_tone": "professional",
            "includes_solution": False,
            "includes_next_steps": True,
            "includes_contact_info": True,
            "language": "English",
            "response_type": response_type,
            "generated_at": datetime.now().isoformat(),
            "ticket_category": "Unknown",
            "ticket_language": "English",
            "is_complete": False,
            "quality_score": 0.4
        }

    def get_response_preview(self, response_result: Dict[str, Any]) -> str:
        """Generate a preview/summary of the generated response"""
        preview = f"""
        📧 CLIENT RESPONSE PREVIEW
        {'=' * 60}
        
        Response Type: {response_result.get('response_type', 'Unknown').upper()}
        Tone: {response_result.get('response_tone', 'Unknown').title()}
        Language: {response_result.get('language', 'Unknown').title()}
        Quality Score: {response_result.get('quality_score', 0):.1%}
        
        {'─' * 60}
        
        {response_result.get('response_text', 'No response text')}
        
        {'─' * 60}
        
        Response Contains:
        ✓ Solution: {'Yes' if response_result.get('includes_solution') else 'No'}
        ✓ Next Steps: {'Yes' if response_result.get('includes_next_steps') else 'No'}
        ✓ Contact Info: {'Yes' if response_result.get('includes_contact_info') else 'No'}
        
        Status: {'✅ Complete' if response_result.get('is_complete') else '⚠️  Incomplete'}
        
        {'=' * 60}
        """
        return preview
