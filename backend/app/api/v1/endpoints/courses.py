from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse

router = APIRouter()

@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_in: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    course = Course(
        title=course_in.title.strip(),
        description=course_in.description.strip() if course_in.description else None,
        user_id=current_user.id
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course

@router.get("/", response_model=list[CourseResponse])
async def get_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Course).filter(Course.user_id == current_user.id))
    courses = result.scalars().all()
    return courses

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Course).filter(Course.id == course_id, Course.user_id == current_user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course

@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    course_in: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Course).filter(Course.id == course_id, Course.user_id == current_user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if course_in.title is not None:
        course.title = course_in.title.strip()
    if course_in.description is not None:
        course.description = course_in.description.strip()

    await db.commit()
    await db.refresh(course)
    return course

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Course).filter(Course.id == course_id, Course.user_id == current_user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    await db.delete(course)
    await db.commit()
    return None
