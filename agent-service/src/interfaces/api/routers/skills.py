"""Procedural-memory (skills) CRUD endpoints (memory.md Phase 7.3).

Mounted under ``/agent`` in main.py → routes resolve to ``/agent/skills/*``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config.settings import MEMORY_USER_ID
from interfaces.dto.requests import SkillCreate, SkillUpdate
from memory.procedural import ProceduralMemory

router = APIRouter(prefix="/skills", tags=["skills"])


def _procedural(user_id: str) -> ProceduralMemory:
    return ProceduralMemory(user_id=user_id or MEMORY_USER_ID)


@router.get("/")
async def list_skills(user_id: str = MEMORY_USER_ID):
    return {"skills": _procedural(user_id).list_all()}


@router.post("/")
async def create_skill(skill: SkillCreate, user_id: str = MEMORY_USER_ID):
    skill_id = _procedural(user_id).add(
        name=skill.name,
        description=skill.description,
        template=skill.template,
        skill_type=skill.skill_type,
    )
    return {"status": "created", "skill_id": skill_id}


@router.put("/{skill_id}")
async def update_skill(skill_id: str, skill: SkillUpdate, user_id: str = MEMORY_USER_ID):
    try:
        _procedural(user_id).update(skill_id, skill.name, skill.description, skill.template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated"}


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, user_id: str = MEMORY_USER_ID):
    _procedural(user_id).delete(skill_id)
    return {"status": "deleted"}
