from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── 1. user_profile ─ singleton USER.md + global settings ─────────────────────
class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True)  # always 1
    content_md = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    # When true, reflection-proposed memory updates are applied immediately
    # without surfacing a proposal card. Skill proposals stay gated regardless.
    auto_accept_memory = Column(Boolean, nullable=False, default=False)


# ── 2. agents ─────────────────────────────────────────────────────────────────
class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False, default="worker")  # manager | worker
    specialization = Column(Text, default="")
    soul = Column(Text, default="")
    status = Column(String, default="idle")  # idle | thinking | working | done | error
    status_msg = Column(Text, nullable=True)
    status_updated_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)
    deleted = Column(Boolean, default=False)


# ── 3. agent_memory ─ append-only versions of each agent's MEMORY.md ──────────
class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    content_md = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    source = Column(String, default="initial")  # initial | manual_edit | proposal_accepted
    source_proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_memory_version"),
    )


# ── 4. agent_skills ───────────────────────────────────────────────────────────
class AgentSkill(Base):
    __tablename__ = "agent_skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    description = Column(Text, default="")
    trigger_keywords = Column(Text, default="[]")  # JSON-encoded list
    frontmatter_yaml = Column(Text, default="")
    instructions_md = Column(Text, default="")
    source = Column(String, default="manual")  # manual | proposal_accepted
    source_proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    deleted = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("agent_id", "slug", name="uq_agent_skill_slug"),
    )


# ── 5. agent_sessions ─ structured transcript; FTS5 mirror is built in raw SQL
class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    trigger = Column(String, default="chat")  # chat | cron | manager_route
    cron_job_id = Column(Integer, ForeignKey("cron_jobs.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    transcript_json = Column(Text, default="[]")
    started_at = Column(DateTime, default=utcnow)
    ended_at = Column(DateTime, nullable=True)
    token_input = Column(Integer, default=0)
    token_output = Column(Integer, default=0)


# ── 6. cron_jobs ──────────────────────────────────────────────────────────────
class CronJob(Base):
    __tablename__ = "cron_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    nl_schedule = Column(Text, nullable=False)
    cron_expr = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    skill_id = Column(Integer, ForeignKey("agent_skills.id"), nullable=True)
    output_target = Column(String, default="ui_only")  # telegram | ui_only | both
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    deleted = Column(Boolean, default=False)


# ── 7. cron_runs ──────────────────────────────────────────────────────────────
class CronRun(Base):
    __tablename__ = "cron_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cron_job_id = Column(Integer, ForeignKey("cron_jobs.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=True)
    status = Column(String, default="running")  # running | success | failed
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    output_excerpt = Column(Text, default="")
    error = Column(Text, nullable=True)


# ── 8. tasks ──────────────────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    task_type = Column(String, nullable=True, index=True)  # classified by reflection; drives skill-proposal trigger
    status = Column(String, default="open")  # open | in_progress | done | failed
    result = Column(Text, nullable=True)
    origin = Column(String, default="manual")  # manual | manager | cron
    cron_job_id = Column(Integer, ForeignKey("cron_jobs.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    deleted = Column(Boolean, default=False)


# ── 9. proposals ─ self-improving loop output, gated by user accept/reject ────
class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=True)
    kind = Column(String, nullable=False)  # memory_update | new_skill
    current_snapshot = Column(Text, default="")
    proposed_snapshot = Column(Text, nullable=False)
    rationale = Column(Text, default="")
    status = Column(String, default="pending")  # pending | accepted | rejected
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class UserProfileOut(BaseModel):
    id: int
    content_md: str
    version: int
    updated_at: datetime
    auto_accept_memory: bool = False
    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    content_md: Optional[str] = None
    auto_accept_memory: Optional[bool] = None


class AgentOut(BaseModel):
    id: int
    name: str
    slug: str
    role: str
    specialization: str
    soul: str
    status: str
    status_msg: Optional[str] = None
    status_updated_at: datetime
    created_at: datetime
    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    name: str
    specialization: str = ""
    soul: str = ""


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    specialization: Optional[str] = None
    soul: Optional[str] = None
    status: Optional[str] = None
    status_msg: Optional[str] = None


class AgentMemoryOut(BaseModel):
    id: int
    agent_id: int
    content_md: str
    version: int
    source: str
    source_proposal_id: Optional[int] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class AgentMemoryUpdate(BaseModel):
    content_md: str


class AgentSkillOut(BaseModel):
    id: int
    agent_id: int
    name: str
    slug: str
    description: str
    trigger_keywords: str
    frontmatter_yaml: str
    instructions_md: str
    source: str
    source_proposal_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AgentSkillCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    frontmatter_yaml: str = ""
    instructions_md: str = ""


class AgentSkillUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    trigger_keywords: Optional[list[str]] = None
    frontmatter_yaml: Optional[str] = None
    instructions_md: Optional[str] = None


class AgentSessionOut(BaseModel):
    id: int
    agent_id: int
    trigger: str
    cron_job_id: Optional[int] = None
    task_id: Optional[int] = None
    transcript_json: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    token_input: int
    token_output: int
    model_config = {"from_attributes": True}


class CronJobOut(BaseModel):
    id: int
    agent_id: int
    name: str
    nl_schedule: str
    cron_expr: str
    prompt: str
    skill_id: Optional[int] = None
    output_target: str
    enabled: bool
    created_at: datetime
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class CronJobCreate(BaseModel):
    agent_id: int
    name: str
    nl_schedule: str
    prompt: str
    skill_id: Optional[int] = None
    output_target: str = "ui_only"


class CronJobUpdate(BaseModel):
    name: Optional[str] = None
    nl_schedule: Optional[str] = None
    prompt: Optional[str] = None
    skill_id: Optional[int] = None
    output_target: Optional[str] = None
    enabled: Optional[bool] = None


class CronRunOut(BaseModel):
    id: int
    cron_job_id: int
    session_id: Optional[int] = None
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    output_excerpt: str
    error: Optional[str] = None
    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    agent_id: int
    title: str
    description: str
    task_type: Optional[str] = None
    status: str
    result: Optional[str] = None
    origin: str
    cron_job_id: Optional[int] = None
    session_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    agent_id: int
    title: str
    description: str = ""
    origin: str = "manual"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    result: Optional[str] = None


class ProposalOut(BaseModel):
    id: int
    agent_id: int
    session_id: Optional[int] = None
    kind: str
    current_snapshot: str
    proposed_snapshot: str
    rationale: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
