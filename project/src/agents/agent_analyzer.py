"""from agno.agent import Agent
from dotenv import load_dotenv, find_dotenv
from src.models.agent_analyzer import gemini_model

load_dotenv(find_dotenv())


agent_analyzer = Agent(
    name="query-analyzer",
    model=gemini_model,
    
    
)"""

import os
import json
from typing import Dict, Any, Optional
import logging
from models.agent_analyzer import gemini_model
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel
from pathlib import Path
from datetime import date



from mistralai import Mistral
from pydantic import BaseModel
from agno.models.mistral import MistralChat
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

mistral = MistralModel("mistral-small-latest")

class AnalysisResult(BaseModel):
    summary: str
    keywords: list
    category: str
    urgency: str
    language: str
    sentiment: str

class Ticket(BaseModel):
    content: str
    id: Optional[str] = None
    subject: str
    created_at: date
    userPlan: Optional[str] = None
    

class QueryAnalyzer:

    def __init__(self):
        self.agent = Agent(
            name="query_analyzer",
            model=mistral,    
            output_type=AnalysisResult,
            instructions=self._get_instructions()
        )
        self.logger = logging.getLogger(__name__)

    def _get_instructions(self) -> str:
        # Load instructions from a file or define them here
        readme_text = Path("project/src/config/prompts/agent_analyzer.md").read_text(encoding="utf-8")
        return readme_text
    

    async def analyze_query(self, ticket: Ticket) -> Dict[str, Any]:
        try:
            querry = f"""Analyze the following support ticket and provide a structured JSON response with the requested fields in the instructions.
            Make sure the JSON is properly formatted and adheres to the specified structure.
            And Make you sure you follow exactly the instructions you were given.:
            here is the ticket content:
            Subject: {ticket.subject}
            Content: {ticket.content}
            Created At: {ticket.created_at}
            User Plan: {ticket.userPlan if ticket.userPlan else 'N/A'}
            """
            self.logger.info(f"Analyzing ticket: {querry[:100]}...")
            
            # Use the agent to analyze the ticket
            response = await self.agent.run(querry)

            analysis_result = response.output.model_dump() 

            # Validate the result structure
            self._validate_analysis(analysis_result)
            
            self.logger.info(f"Analysis complete: {analysis_result['category']} - {analysis_result['urgency']}")
            return analysis_result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {response.content}")
            raise ValueError(f"Invalid JSON response from analyzer: {str(e)}")
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise
    
    def _validate_analysis(self, analysis: Dict[str, Any]) -> bool:

        required_fields = {
            "summary": str,
            "keywords": list,
            "category": str,
            "urgency": str,
            "language": str,
            "sentiment": str,
        }


        # Check all required fields exist
        for field, field_type in required_fields.items():
            if field not in analysis:
                raise ValueError(f"Missing required field: {field}")
            
            if not isinstance(analysis[field], field_type):
                raise ValueError(f"Field {field} must be {field_type.__name__}, got {type(analysis[field]).__name__}")
        
        # Validate category
        valid_categories = ["Technical", "Billing", "Access", "General", "Refund", "Onboarding", "Other"]
        if analysis["category"] not in valid_categories:
            raise ValueError(f"Invalid category: {analysis['category']}. Must be one of {valid_categories}")
        
        # Validate urgency
        valid_urgency = ["Low", "Medium", "High", "Critical"]
        if analysis["urgency"] not in valid_urgency:
            raise ValueError(f"Invalid urgency: {analysis['urgency']}. Must be one of {valid_urgency}")
        
        # Validate keywords (3-5)
        if len(analysis["keywords"]) < 3 or len(analysis["keywords"]) > 5:
            raise ValueError(f"Keywords must be 5-9 items, got {len(analysis['keywords'])}")
        
        return True
    
    async def batch_analyze(self, tickets: list) -> list:
        results = []
        for ticket in tickets:
            try:
                analysis = await self.analyze_query(ticket)
                results.append(analysis)
            except Exception as e:
                self.logger.error(f"Failed to analyze ticket: {str(e)}")
                results.append(None)  # Or handle as needed
        
        return results
    
    def get_analysis_report(self, analysis: Dict[str, Any]) -> str:
        report = f"""
        📋 TICKET ANALYSIS REPORT
        {'=' * 40}
        
        📝 Summary: {analysis['summary']}
        
        🔑 Keywords: {', '.join(analysis['keywords'])}
        
        🏷️  Category: {analysis['category']}
        ⚠️  Urgency: {analysis['urgency']}
        
        🌐 Language: {analysis['language']}
        😊 Sentiment: {analysis['sentiment']}
        
        
        {'=' * 40}
        """
        return report