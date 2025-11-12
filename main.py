import os
import hashlib
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import (
    User, LoginRequest, ChangePasswordRequest,
    RoadmapStep, AssessmentResult, Progress, Resume,
    ALLOWED_QUALIFICATIONS,
)

app = FastAPI(title="Lernify Road API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Helpers
# ---------------------------

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def to_str_id(doc: Dict[str, Any]):
    if doc and doc.get("_id"):
        doc["id"] = str(doc.pop("_id"))
    return doc


# ---------------------------
# Seed roadmaps (idempotent)
# ---------------------------
SEED_ROADMAPS: Dict[str, List[RoadmapStep]] = {
    "frontend": [
        RoadmapStep(order=1, title="HTML & CSS Basics", description="Learn HTML structure and CSS styling.", videos=[
            "https://www.youtube.com/watch?v=G3e-cpL7ofc",
            "https://www.youtube.com/watch?v=mU6anWqZJcc",
        ], questions=[
            {"q": "What tag defines a hyperlink?", "options": ["<a>", "<link>", "<href>"], "answerIndex": 0},
            {"q": "Which property changes text color?", "options": ["font", "color", "text"], "answerIndex": 1},
        ]),
        RoadmapStep(order=2, title="JavaScript Fundamentals", description="Variables, functions, DOM.", videos=[
            "https://www.youtube.com/watch?v=PkZNo7MFNFg",
        ], questions=[
            {"q": "Which declares a block-scoped variable?", "options": ["var", "let", "function"], "answerIndex": 1},
            {"q": "DOM stands for?", "options": ["Document Object Model", "Data Object Method", "Display Object Map"], "answerIndex": 0},
        ]),
        RoadmapStep(order=3, title="React Basics", description="Components, state, props.", videos=[
            "https://www.youtube.com/watch?v=bMknfKXIFA8",
        ], questions=[
            {"q": "State is used to?", "options": ["Style components", "Manage dynamic data", "Route pages"], "answerIndex": 1},
        ]),
    ],
    "backend": [
        RoadmapStep(order=1, title="Programming & Git", description="Language basics and version control.", videos=[
            "https://www.youtube.com/watch?v=SWYqp7iY_Tc",
        ], questions=[
            {"q": "git commit does?", "options": ["Send to remote", "Save snapshot", "Create branch"], "answerIndex": 1},
        ]),
        RoadmapStep(order=2, title="Node.js & Express", description="APIs, routing, middleware.", videos=[
            "https://www.youtube.com/watch?v=L72fhGm1tfE",
        ], questions=[
            {"q": "Express is?", "options": ["DB", "Framework", "Language"], "answerIndex": 1},
        ]),
        RoadmapStep(order=3, title="Databases", description="SQL/NoSQL basics.", videos=[
            "https://www.youtube.com/watch?v=E-1xI85Zog8",
        ], questions=[
            {"q": "NoSQL example?", "options": ["MongoDB", "MySQL", "PostgreSQL"], "answerIndex": 0},
        ]),
    ],
    "ai-ml": [
        RoadmapStep(order=1, title="Python & Numpy", description="Python essentials, arrays.", videos=[
            "https://www.youtube.com/watch?v=_uQrJ0TkZlc",
        ], questions=[
            {"q": "Numpy is used for?", "options": ["Web", "Arrays & math", "OS"], "answerIndex": 1},
        ]),
        RoadmapStep(order=2, title="Pandas & Data", description="Dataframes, cleaning.", videos=[
            "https://www.youtube.com/watch?v=vmEHCJofslg",
        ], questions=[
            {"q": "Pandas DataFrame is?", "options": ["2D table", "1D list", "3D cube"], "answerIndex": 0},
        ]),
        RoadmapStep(order=3, title="ML Basics", description="Supervised vs unsupervised.", videos=[
            "https://www.youtube.com/watch?v=Gv9_4yMHFhI",
        ], questions=[
            {"q": "Supervised uses?", "options": ["Labels", "No data", "Only images"], "answerIndex": 0},
        ]),
    ],
}


def ensure_roadmaps_seeded():
    if db is None:
        return
    for domain, steps in SEED_ROADMAPS.items():
        existing = db.roadmap.find_one({"domain": domain})
        if not existing:
            db.roadmap.insert_one({
                "domain": domain,
                "steps": [s.model_dump() for s in steps]
            })


ensure_roadmaps_seeded()


# ---------------------------
# Health
# ---------------------------
@app.get("/")
def read_root():
    return {"message": "Lernify Road Backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    return response


# ---------------------------
# Auth
# ---------------------------
@app.post("/auth/register")
def register(user: User):
    if user.qualification not in ALLOWED_QUALIFICATIONS:
        raise HTTPException(status_code=403, detail="Only IT-related students can register")
    if db.user.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = user.model_dump()
    doc["password_hash"] = hash_password(doc.pop("password_hash"))
    user_id = db.user.insert_one(doc).inserted_id
    saved = db.user.find_one({"_id": user_id}, {"password_hash": 0})
    return {"user": to_str_id(saved)}


@app.post("/auth/login")
def login(payload: LoginRequest):
    user = db.user.find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user.pop("password_hash", None)
    return {"user": to_str_id(user)}


@app.post("/auth/change-password")
def change_password(payload: ChangePasswordRequest):
    try:
        _id = ObjectId(payload.user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    user = db.user.find_one({"_id": _id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("password_hash") != hash_password(payload.old_password):
        raise HTTPException(status_code=401, detail="Old password incorrect")
    db.user.update_one({"_id": _id}, {"$set": {"password_hash": hash_password(payload.new_password)}})
    return {"message": "Password updated"}


# ---------------------------
# Profile
# ---------------------------
@app.get("/profile/{user_id}")
def get_profile(user_id: str):
    try:
        _id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    user = db.user.find_one({"_id": _id}, {"password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": to_str_id(user)}


class UpdateProfile(BaseModel):
    first_name: str
    last_name: str
    phone: str
    qualification: str
    avatar_url: str | None = None


@app.put("/profile/{user_id}")
def update_profile(user_id: str, payload: UpdateProfile):
    try:
        _id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    updates = payload.model_dump()
    if updates.get("qualification") not in ALLOWED_QUALIFICATIONS:
        raise HTTPException(status_code=400, detail="Invalid qualification")
    db.user.update_one({"_id": _id}, {"$set": updates})
    user = db.user.find_one({"_id": _id}, {"password_hash": 0})
    return {"user": to_str_id(user)}


# ---------------------------
# Roadmaps
# ---------------------------
@app.get("/roadmaps")
def list_domains():
    domains = [d["domain"] for d in db.roadmap.find({}, {"domain": 1, "_id": 0})]
    return {"domains": domains}


@app.get("/roadmaps/{domain}")
def get_roadmap(domain: str):
    rm = db.roadmap.find_one({"domain": domain})
    if not rm:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"domain": domain, "steps": rm.get("steps", [])}


# ---------------------------
# Assessments and Progress
# ---------------------------
class SubmitAssessment(BaseModel):
    user_id: str
    domain: str
    step_order: int
    answers: List[int]


@app.get("/progress/{user_id}/{domain}")
def get_progress(user_id: str, domain: str):
    prog = db.progress.find_one({"user_id": user_id, "domain": domain})
    if not prog:
        prog = Progress(user_id=user_id, domain=domain, completed_steps=[], scores={}).model_dump()
        db.progress.insert_one(prog)
    return {"progress": to_str_id(prog)}


@app.post("/assessments/submit")
def submit_assessment(payload: SubmitAssessment):
    rm = db.roadmap.find_one({"domain": payload.domain})
    if not rm:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    steps = rm.get("steps", [])
    step = next((s for s in steps if s.get("order") == payload.step_order), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    # Gatekeeping: ensure previous step completed
    prog = db.progress.find_one({"user_id": payload.user_id, "domain": payload.domain})
    if not prog:
        prog = Progress(user_id=payload.user_id, domain=payload.domain, completed_steps=[], scores={}).model_dump()
        db.progress.insert_one(prog)
    if payload.step_order > 1 and (payload.step_order - 1) not in prog.get("completed_steps", []):
        raise HTTPException(status_code=403, detail="Complete previous step first")

    correct_indexes = [q.get("answerIndex") for q in step.get("questions", [])]
    score = sum(1 for i, ans in enumerate(payload.answers) if i < len(correct_indexes) and ans == correct_indexes[i])
    total = len(correct_indexes)
    passed = score >= max(1, int(0.6 * total))  # 60% pass

    result = AssessmentResult(
        user_id=payload.user_id,
        domain=payload.domain,
        step_order=payload.step_order,
        score=score,
        total=total,
        passed=passed,
    ).model_dump()
    db.assessmentresult.insert_one(result)

    if passed:
        db.progress.update_one(
            {"user_id": payload.user_id, "domain": payload.domain},
            {
                "$addToSet": {"completed_steps": payload.step_order},
                "$set": {f"scores.{payload.step_order}": score}
            },
            upsert=True,
        )

    return {"result": result, "message": "Passed" if passed else "Failed"}


@app.get("/dashboard/{user_id}")
def dashboard(user_id: str):
    results = list(db.assessmentresult.find({"user_id": user_id}))
    for r in results:
        to_str_id(r)
    progresses = list(db.progress.find({"user_id": user_id}))
    for p in progresses:
        to_str_id(p)
    return {
        "assessments": results,
        "progress": progresses,
    }


# ---------------------------
# Resume
# ---------------------------
@app.post("/resume")
def upsert_resume(payload: Resume):
    existing = db.resume.find_one({"user_id": payload.user_id})
    data = payload.model_dump()
    if existing:
        db.resume.update_one({"_id": existing["_id"]}, {"$set": data})
        stored = db.resume.find_one({"_id": existing["_id"]})
    else:
        new_id = db.resume.insert_one(data).inserted_id
        stored = db.resume.find_one({"_id": new_id})
    return {"resume": to_str_id(stored)}


@app.get("/resume/{user_id}")
def get_resume(user_id: str):
    res = db.resume.find_one({"user_id": user_id})
    if not res:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"resume": to_str_id(res)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
