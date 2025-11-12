"""
Database Schemas for Lernify Road

Each Pydantic model represents a collection in MongoDB (collection name is the lowercase class name).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, constr

# ---------------------------
# USER AND AUTH
# ---------------------------

ALLOWED_QUALIFICATIONS = [
    "B.Tech CSE",
    "B.Tech IT",
    "B.Sc IT",
    "BCA",
    "MCA",
    "M.Sc CS",
    "Diploma in CS/IT",
]

class User(BaseModel):
    first_name: constr(strip_whitespace=True, min_length=2) = Field(...)
    last_name: constr(strip_whitespace=True, min_length=2) = Field(...)
    email: EmailStr
    phone: constr(pattern=r"^[0-9]{10}$") = Field(..., description="10-digit phone number")
    qualification: constr(strip_whitespace=True) = Field(..., description="Must be IT-related qualification")
    password_hash: str
    role: str = Field("student")
    avatar_url: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=6)

class ChangePasswordRequest(BaseModel):
    user_id: str
    old_password: constr(min_length=6)
    new_password: constr(min_length=6)

# ---------------------------
# ROADMAP AND ASSESSMENT
# ---------------------------

class RoadmapStep(BaseModel):
    order: int
    title: str
    description: str
    videos: List[str] = []  # YouTube URLs
    questions: List[Dict[str, Any]] = []  # [{question, options:[], answerIndex}]

class AssessmentResult(BaseModel):
    user_id: str
    domain: str
    step_order: int
    score: int
    total: int
    passed: bool

class Progress(BaseModel):
    user_id: str
    domain: str
    completed_steps: List[int] = []
    scores: Dict[str, int] = {}  # key: step_order as str -> score

# ---------------------------
# RESUME
# ---------------------------

class Resume(BaseModel):
    user_id: str
    summary: constr(min_length=20)
    skills: List[constr(min_length=2)]
    education: List[Dict[str, str]]  # [{degree, institution, year}]
    experience: List[Dict[str, str]]  # [{role, company, duration, details}]
    projects: List[Dict[str, str]]  # [{name, tech, link, details}]
    contact: Dict[str, str]  # {email, phone, linkedin, github}
