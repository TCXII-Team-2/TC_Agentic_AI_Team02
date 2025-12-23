"""
End-to-end workflow test chaining all agents on a single ticket.
Pipeline:
1) Analyze ticket -> 2) Validate completeness -> 3) RAG retrieve
4) Confidence evaluation -> 5) Response generation
"""
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

# Ensure local imports work when running directly
sys.path.append(str(Path(__file__).parent.parent))

from agents.agent_analyzer import QueryAnalyzer, Ticket
from agents.agent_validator import TicketValidator
from agents.evaluation_agent import RAGRetriever
from agents.agent_confidence import ConfidenceEvaluator
from agents.agent_response import ResponseGenerator


async def run_full_workflow():
    # Multiple sample tickets to exercise different paths
    scenarios = [
        Ticket(
            id="TCK-WF-001",
            subject="Unable to reset my password",
            content=(
                "I tried resetting my password but never received the email. "
                "It has been failing since yesterday and I am locked out."
            ),
            created_at=date(2025, 2, 5),
            userPlan="Premium",
        ),
        Ticket(
            id="TCK-WF-002",
            subject="Charged twice on my invoice",
            content=(
                "I was billed twice for the same month. Invoice INV-2025-0021 shows two charges of $49.99. "
                "Please refund the duplicate."
            ),
            created_at=date(2025, 2, 6),
            userPlan="Standard",
        ),
        Ticket(
            id="TCK-WF-003",
            subject="App crashes on launch",
            content=(
                "Every time I open the desktop app it crashes immediately with error code 0xDEADBEEF. "
                "I reinstalled but it still happens."
            ),
            created_at=date(2025, 2, 7),
            userPlan="Premium",
        ),
        Ticket(
            id="TCK-WF-004",
            subject="Besoin d’aide pour la facturation",
            content=(
                "Je ne comprends pas la dernière facture, il y a des frais supplémentaires. "
                "Pouvez-vous expliquer les montants facturés ?"
            ),
            created_at=date(2025, 2, 8),
            userPlan="Free",
        ),
    ]

    analyzer = QueryAnalyzer()
    validator = TicketValidator()
    retriever = RAGRetriever()
    confidence_agent = ConfidenceEvaluator()
    responder = ResponseGenerator()

    for ticket in scenarios:
        print("\n🚀 Running full agent workflow...\n" + "=" * 70)
        print(f"Ticket: {ticket.subject} ({ticket.id})")

        # 1) Analyze
        analysis = await analyzer.analyze_query(ticket)
        print("🔎 Analysis result:")
        print(json.dumps(analysis, indent=2, ensure_ascii=False))

        # 2) Validate
        validation = await validator.validate(ticket, analysis)
        print("\n✅ Validation result:")
        print(json.dumps(validation, indent=2, ensure_ascii=False))

        if not validation.get("is_valid"):
            print("\n⚠️ Ticket deemed incomplete. Message to client:")
            msg = validation.get("message_to_client", "Please provide more details.") or "Please provide more details."
            lines = msg.splitlines()
            deduped_lines = []
            for line in lines:
                if not deduped_lines or deduped_lines[-1].strip() != line.strip():
                    deduped_lines.append(line)
            print("\n".join(deduped_lines))
            continue

        # 3) RAG retrieval
        rag_results = await retriever.retrieve(query=ticket.content, n_results=5, min_confidence=0.0)
        print("\n📚 RAG retrieval:")
        print(json.dumps(rag_results, indent=2, ensure_ascii=False)[:1000])

        # 4) Confidence evaluation
        confidence = await confidence_agent.evaluate_confidence(
            ticket_analysis=analysis,
            rag_results=rag_results,
            original_ticket=ticket.model_dump(),
        )
        print("\n🎯 Confidence evaluation:")
        print(json.dumps(confidence, indent=2, ensure_ascii=False))

        # Decide response type based on confidence
        if confidence.get("should_escalate"):
            response_type = "escalation_notice"
        elif confidence.get("suggested_action") == "request_clarification":
            response_type = "clarification_request"
        else:
            response_type = "solution"

        # 5) Generate client response
        response = await responder.generate_response(
            ticket_analysis=analysis,
            rag_results=rag_results,
            confidence_evaluation=confidence,
            original_ticket=ticket.model_dump(),
            response_type=response_type,
        )
        print("\n✉️  Final client response:")
        print(json.dumps(response, indent=2, ensure_ascii=False))

        # Optional previews/reports
        print("\n--- Reports ---")
        print(retriever.get_retrieval_report(rag_results))
        print(confidence_agent.get_confidence_report(confidence))
        print(responder.get_response_preview(response))


if __name__ == "__main__":
    asyncio.run(run_full_workflow())
