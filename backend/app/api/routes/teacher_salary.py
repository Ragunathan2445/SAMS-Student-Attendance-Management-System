from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_permission
from app.db.session import get_db
from app.models import School
from app.services import pdf_service, salary_service

router = APIRouter(prefix="/teacher/salary", tags=["Salary"])


@router.get("")
def salary_list(user: CurrentUser = Depends(require_permission("salary.view.own")), db: Session = Depends(get_db)):
    return {"salaries": salary_service.list_salaries(db, user.teacher)}


@router.get("/{salary_id}")
def salary_detail(salary_id: int, user: CurrentUser = Depends(require_permission("salary.view.own")),
                  db: Session = Depends(get_db)):
    return salary_service.get_salary(db, user.teacher, salary_id)[1]


@router.get("/{salary_id}/slip")
def salary_slip(salary_id: int, user: CurrentUser = Depends(require_permission("salary.view.own")),
                db: Session = Depends(get_db)):
    _, data = salary_service.get_salary(db, user.teacher, salary_id)
    t = user.teacher
    pdf = pdf_service.salary_slip_pdf(
        school=db.scalar(select(School).limit(1)), salary=data,
        teacher={"full_name": t.full_name, "employee_code": t.employee_code, "designation": t.designation},
    )
    month = data["salary_month"][:7]
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="salary-slip-{t.employee_code}-{month}.pdf"'})
