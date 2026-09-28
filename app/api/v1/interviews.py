"""Interview lifecycle, question delivery, and answer evaluation."""
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import current_user
from app.services.store import INTERVIEWS, JDS, REPORTS, RESUMES

router = APIRouter(prefix="/interview", tags=["interviews"])
QUESTION_BANK = [
    ("Explain how a retrieval-augmented generation system works.", "RAG", "intermediate", ["retrieval", "generation", "grounding"]),
    ("How do you choose chunk size and overlap for a document retrieval pipeline?", "RAG", "intermediate", ["chunking", "context", "evaluation"]),
    ("Why add a reranker after vector search, and how would you evaluate it?", "RAG", "advanced", ["reranking", "ndcg", "recall"]),
    ("How would you prevent hallucinations in an LLM application?", "LLM", "advanced", ["grounding", "citations", "evaluation"]),
    ("Describe a project you built and the tradeoffs you made.", "projects", "foundational", ["ownership", "tradeoffs", "impact"]),
    ("How would you design a reliable API service that handles growing traffic?", "system design", "advanced", ["scaling", "availability", "observability"]),
    ("How do you test and deploy a Python web service?", "Python", "intermediate", ["testing", "deployment", "monitoring"]),
    ("Tell me about a time you received difficult feedback.", "behavioral", "foundational", ["reflection", "action", "outcome"]),
]


class CreateInterview(BaseModel):
    interview_type: str = Field(default="technical", max_length=40)
    resume_id: str | None = None
    jd_id: str | None = None
    difficulty: str = Field(default="intermediate", pattern="^(foundational|intermediate|advanced)$")
    question_count: int = Field(default=5, ge=1, le=20)


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)


def _owned(interview_id: str, user_id: str) -> dict:
    interview = INTERVIEWS.get(interview_id)
    if interview is None or interview["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def _question(interview: dict) -> dict | None:
    idx = interview["current_index"]
    if idx >= len(interview["selected_questions"]):
        return None
    return interview["selected_questions"][idx]


def _report(interview: dict) -> dict:
    answers = interview["answers"]
    scores = [a["evaluation"]["score"] for a in answers]
    score = round(sum(scores) / len(scores), 1) if scores else 0
    return {"id": secrets.token_urlsafe(16), "interview_id": interview["id"], "user_id": interview["user_id"],
            "score": score, "strengths": sorted({c for a in answers for c in a["evaluation"]["covered_concepts"]}),
            "improvement_areas": sorted({c for a in answers for c in a["evaluation"]["missing_concepts"]}),
            "recommendations": ["Practice explaining your reasoning with specific examples."],
            "completed_at": datetime.now(UTC).isoformat()}


@router.post("/create", status_code=201)
def create_interview(payload: CreateInterview, user: dict = Depends(current_user)) -> dict:
    if payload.resume_id and (payload.resume_id not in RESUMES or RESUMES[payload.resume_id]["user_id"] != user["id"]):
        raise HTTPException(status_code=404, detail="Resume not found")
    if payload.jd_id and (payload.jd_id not in JDS or JDS[payload.jd_id]["user_id"] != user["id"]):
        raise HTTPException(status_code=404, detail="Job description not found")
    jd_skills = JDS.get(payload.jd_id or "", {}).get("required_skills", [])
    questions = list(QUESTION_BANK)
    if jd_skills:
        questions.sort(key=lambda q: 0 if any(s.lower() in (q[1] + " " + q[0]).lower() for s in jd_skills) else 1)
    count = min(payload.question_count, len(questions))
    interview_id = secrets.token_urlsafe(16)
    record = {"id": interview_id, "user_id": user["id"], "interview_type": payload.interview_type,
              "difficulty": payload.difficulty, "status": "draft", "resume_id": payload.resume_id,
              "jd_id": payload.jd_id, "question_count": count,
              "selected_questions": [{"id": f"q{i+1}", "question": q[0], "topic": q[1], "difficulty": q[2], "expected_concepts": q[3]} for i, q in enumerate(questions[:count])],
              "current_index": 0, "answers": [], "asked_question_ids": [], "started_at": None, "created_at": datetime.now(UTC).isoformat()}
    INTERVIEWS[interview_id] = record
    return {k: v for k, v in record.items() if k not in {"selected_questions", "answers"}}


@router.post("/{interview_id}/start")
def start_interview(interview_id: str, user: dict = Depends(current_user)) -> dict:
    interview = _owned(interview_id, user["id"])
    if interview["status"] == "completed":
        raise HTTPException(status_code=409, detail="Interview is already complete")
    interview["status"] = "in_progress"
    interview["started_at"] = interview["started_at"] or datetime.now(UTC).isoformat()
    question = _question(interview)
    if question and question["id"] not in interview["asked_question_ids"]:
        interview["asked_question_ids"].append(question["id"])
    return {"interview_id": interview_id, "status": interview["status"], "question": question}


@router.get("/{interview_id}/question")
def get_question(interview_id: str, user: dict = Depends(current_user)) -> dict:
    interview = _owned(interview_id, user["id"])
    if interview["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="Start the interview before requesting a question")
    question = _question(interview)
    if question is None:
        raise HTTPException(status_code=404, detail="No more questions; retrieve the report")
    if question["id"] not in interview["asked_question_ids"]:
        interview["asked_question_ids"].append(question["id"])
    return {"interview_id": interview_id, "question": question}


@router.post("/{interview_id}/answer")
def submit_answer(interview_id: str, payload: AnswerRequest, user: dict = Depends(current_user)) -> dict:
    interview = _owned(interview_id, user["id"])
    if interview["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="Interview is not in progress")
    question = _question(interview)
    if question is None:
        raise HTTPException(status_code=409, detail="There is no unanswered question")
    words = set(payload.answer.lower().replace("/", " ").replace("-", " ").split())
    covered = [c for c in question["expected_concepts"] if any(part in words for part in c.lower().split())]
    missing = [c for c in question["expected_concepts"] if c not in covered]
    score = min(5, max(1, 1 + len(covered)))
    evaluation = {"score": score, "covered_concepts": covered, "missing_concepts": missing,
                  "feedback": "Good coverage; support your points with concrete examples." if score >= 4 else "Add more detail about " + (", ".join(missing) or "your reasoning") + "."}
    interview["answers"].append({"question_id": question["id"], "question": question["question"],
                                 "answer": payload.answer, "evaluation": evaluation,
                                 "answered_at": datetime.now(UTC).isoformat()})
    interview["current_index"] += 1
    next_question = _question(interview)
    if next_question is None:
        interview["status"] = "completed"
        report = _report(interview)
        REPORTS[interview_id] = report
    else:
        interview["asked_question_ids"].append(next_question["id"])
        report = None
    return {"evaluation": evaluation, "next_question": next_question,
            "status": interview["status"], "report": report}
