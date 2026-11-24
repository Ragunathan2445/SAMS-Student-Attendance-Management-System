from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import School, Student, Teacher

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/school")
def school_info(db: Session = Depends(get_db)):
    school = db.scalar(select(School).limit(1))
    if school is None:
        return {"name": "School", "configured": False}
    return {
        "configured": True,
        "name": school.name,
        "code": school.code,
        "tagline": school.tagline,
        "about": school.about,
        "highlights": [h for h in (school.highlights or "").split("\n") if h.strip()],
        "address": school.address,
        "phone": school.phone,
        "email": school.email,
        "website": school.website,
        "established_year": school.established_year,
        "affiliation": school.affiliation,
        "principal_name": school.principal_name,
        "stats": {
            "students": db.scalar(select(func.count(Student.id)).where(Student.status == "active")),
            "teachers": db.scalar(select(func.count(Teacher.id)).where(Teacher.is_active.is_(True))),
        },
    }
