from __future__ import annotations

import asyncio
import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Ensure project src is importable
import sys
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_SRC = CURRENT_DIR.parent
REPO_ROOT = PROJECT_SRC.parent.parent  # .../TC_Agentic_AI_Team02
sys.path.append(str(PROJECT_SRC))

# Import agents
from agents.agent_analyzer import QueryAnalyzer, Ticket as AnalyzerTicket
from agents.agent_validator import TicketValidator
from agents.evaluation_agent import RAGRetriever
from agents.agent_confidence import ConfidenceEvaluator
from agents.agent_response import ResponseGenerator

app = FastAPI(title="Support Workflow API", version="1.0.0")


class TicketIn(BaseModel):
    id: Optional[str] = None
    subject: str
    content: str
    created_at: date
    userPlan: Optional[str] = None


class WorkflowResponse(BaseModel):
    analysis: Dict[str, Any]
    validation: Dict[str, Any]
    rag: Dict[str, Any]
    confidence: Dict[str, Any]
    response: Dict[str, Any]


# ---- Jury bulk Q&A schema ----
class QuestionItem(BaseModel):
    id: str
    query: str


class QuestionsIn(BaseModel):
    Questions: List[QuestionItem]


class AnswerItem(BaseModel):
    id: str
    answer: str


class AnswersOut(BaseModel):
    Team: str
    Answers: List[AnswerItem]


@app.on_event("startup")
async def startup_event():
    # Instantiate long-lived agent objects once
    app.state.analyzer = QueryAnalyzer()
    app.state.validator = TicketValidator()
    # Ensure Chroma path is absolute for API runtime
    chroma_path = str((REPO_ROOT / "chromadb").resolve())
    app.state.retriever = RAGRetriever(db_path=chroma_path)
    app.state.confidence = ConfidenceEvaluator()
    app.state.responder = ResponseGenerator()
    app.state.team_name = os.getenv("TEAM_NAME", "TEAM 02")


def _dedupe_lines(text: str) -> str:
    lines = (text or "").splitlines()
    deduped: List[str] = []
    for line in lines:
        if not deduped or deduped[-1].strip() != line.strip():
            deduped.append(line)
    return "\n".join(deduped)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/workflow/run", response_model=WorkflowResponse)
async def run_workflow(ticket: TicketIn) -> JSONResponse:
    try:
        # Map to analyzer ticket model
        a_ticket = AnalyzerTicket(
            id=ticket.id,
            subject=ticket.subject,
            content=ticket.content,
            created_at=ticket.created_at,
            userPlan=ticket.userPlan,
        )

        analyzer: QueryAnalyzer = app.state.analyzer
        validator: TicketValidator = app.state.validator
        retriever: RAGRetriever = app.state.retriever
        confidence_agent: ConfidenceEvaluator = app.state.confidence
        responder: ResponseGenerator = app.state.responder

        # 1) Analyze
        analysis = await analyzer.analyze_query(a_ticket)

        # 2) Validate
        validation = await validator.validate(a_ticket, analysis)
        if not validation.get("is_valid"):
            # Check if out-of-scope
            if validation.get("validation_status") == "out_of_scope":
                msg = "Thank you for contacting us. Your question appears to be outside the scope of our support services. If you have questions about our product or service, please feel free to rephrase your question."
                return JSONResponse(
                    status_code=200,
                    content={
                        "analysis": analysis,
                        "validation": validation,
                        "rag": {},
                        "confidence": {},
                        "response": {
                            "response_text": msg,
                            "response_type": "out_of_scope",
                            "language": analysis.get("language", "English"),
                        },
                    },
                )
            # Short-circuit with a clarification response
            msg = validation.get("message_to_client") or "Please provide more details."
            validation["message_to_client"] = _dedupe_lines(msg)
            return JSONResponse(
                status_code=200,
                content={
                    "analysis": analysis,
                    "validation": validation,
                    "rag": {},
                    "confidence": {},
                    "response": {
                        "response_text": validation["message_to_client"],
                        "response_type": "clarification_request",
                        "language": analysis.get("language", "English"),
                    },
                },
            )

        # 3) RAG retrieval
        rag_results = await retriever.retrieve(query=ticket.content, n_results=5, min_confidence=0.0)

        # 4) Confidence evaluation
        confidence = await confidence_agent.evaluate_confidence(
            ticket_analysis=analysis,
            rag_results=rag_results,
            original_ticket=a_ticket.model_dump(),
        )

        # 5) Decide response type and generate response
        if confidence.get("suggested_action") == "out_of_scope":
            rtype = "out_of_scope"
        elif confidence.get("should_escalate"):
            rtype = "escalation_notice"
        elif confidence.get("suggested_action") == "request_clarification":
            rtype = "clarification_request"
        else:
            rtype = "solution"

        response = await responder.generate_response(
            ticket_analysis=analysis,
            rag_results=rag_results,
            confidence_evaluation=confidence,
            original_ticket=a_ticket.model_dump(),
            response_type=rtype,
        )

        return JSONResponse(
            status_code=200,
            content={
                "analysis": analysis,
                "validation": validation,
                "rag": rag_results,
                "confidence": confidence,
                "response": response,
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {e}")


@app.post("/workflow/answer-questions", response_model=AnswersOut)
async def answer_questions(payload: QuestionsIn) -> JSONResponse:
    """
    Accepts bulk questions in the specified jury JSON format and returns
    answers in the required output format.
    """
    try:
        analyzer: QueryAnalyzer = app.state.analyzer
        validator: TicketValidator = app.state.validator
        retriever: RAGRetriever = app.state.retriever
        confidence_agent: ConfidenceEvaluator = app.state.confidence
        responder: ResponseGenerator = app.state.responder
        team_name: str = app.state.team_name

        answers: List[Dict[str, str]] = []

        for q in payload.Questions:
            try:
                # Build synthetic ticket from question
                a_ticket = AnalyzerTicket(
                    id=q.id,
                    subject=f"Question {q.id}",
                    content=q.query,
                    created_at=date.today(),
                    userPlan="Free",
                )

                # 1) Analyze
                analysis = await analyzer.analyze_query(a_ticket)

                # 2) Validate
                validation = await validator.validate(a_ticket, analysis)
                if not validation.get("is_valid"):
                    # Check if out-of-scope
                    if validation.get("validation_status") == "out_of_scope":
                        msg = "Thank you for contacting us. Your question appears to be outside the scope of our support services. If you have questions about our product or service, please feel free to rephrase your question."
                        answers.append({"id": q.id, "answer": msg})
                        continue
                    msg = validation.get("message_to_client") or "Please provide more details."
                    answers.append({"id": q.id, "answer": _dedupe_lines(msg)})
                    continue

                # 3) RAG retrieval
                rag_results = await retriever.retrieve(query=q.query, n_results=5, min_confidence=0.0)

                # 4) Confidence evaluation
                confidence = await confidence_agent.evaluate_confidence(
                    ticket_analysis=analysis,
                    rag_results=rag_results,
                    original_ticket=a_ticket.model_dump(),
                )

                # 5) Decide response type and generate response
                if confidence.get("suggested_action") == "out_of_scope":
                    rtype = "out_of_scope"
                elif confidence.get("should_escalate"):
                    rtype = "escalation_notice"
                elif confidence.get("suggested_action") == "request_clarification":
                    rtype = "clarification_request"
                else:
                    rtype = "solution"

                response = await responder.generate_response(
                    ticket_analysis=analysis,
                    rag_results=rag_results,
                    confidence_evaluation=confidence,
                    original_ticket=a_ticket.model_dump(),
                    response_type=rtype,
                )

                answers.append({"id": q.id, "answer": response.get("response_text", "")})
                
            except Exception as e:
                # Log error but continue with next question
                import logging
                logging.error(f"Failed to process question {q.id}: {str(e)}")
                answers.append({
                    "id": q.id, 
                    "answer": "We encountered an error processing your question. Please try rephrasing or contact support directly."
                })
                continue

        return JSONResponse(status_code=200, content={"Team": team_name, "Answers": answers})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk Q&A failed: {e}")


# --- Knowledge Base Management ---

KB_DIR = REPO_ROOT / "knowledge_base"
FILL_DB_SCRIPT = REPO_ROOT / "src" / "pipelines" / "fill_db2.py"


def _ensure_kb_dir():
    KB_DIR.mkdir(parents=True, exist_ok=True)


def _run_fill_db_sync() -> None:
    # Run using repo root as cwd so relative paths in script work
    proc = subprocess.run(
        [sys.executable, str(FILL_DB_SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"fill_db2.py failed: {proc.stderr}")


@app.post("/admin/knowledge/upload")
async def upload_markdown(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    trigger_rebuild: bool = Form(True),
) -> Dict[str, Any]:
    try:
        _ensure_kb_dir()
        saved: List[str] = []
        for f in files:
            if not f.filename.lower().endswith(".md"):
                raise HTTPException(status_code=400, detail="Only .md files are accepted")
            target = KB_DIR / f.filename
            data = await f.read()
            target.write_bytes(data)
            saved.append(str(target))

        if trigger_rebuild:
            background_tasks.add_task(_run_fill_db_sync)

        return {"saved": saved, "rebuild_triggered": trigger_rebuild}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@app.post("/admin/knowledge/rebuild")
async def rebuild_kb(background_tasks: BackgroundTasks, async_run: bool = True) -> Dict[str, Any]:
    try:
        if async_run:
            background_tasks.add_task(_run_fill_db_sync)
            return {"status": "rebuild started"}
        # synchronous
        _run_fill_db_sync()
        return {"status": "rebuild completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rebuild failed: {e}")


# Optional: local run helper (uvicorn)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
