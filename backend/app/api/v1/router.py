from fastapi import APIRouter

from app.api.v1.endpoints import (
    assessments,
    auth,
    citations,
    courses,
    evaluation,
    health,
    learner,
    materials,
    search,
    topics,
    tutor,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(evaluation.router, tags=["providers", "evaluation"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(courses.router, prefix="/courses", tags=["courses"])
api_router.include_router(materials.router, tags=["materials"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(tutor.router, tags=["tutor"])
api_router.include_router(citations.router, tags=["citations"])
api_router.include_router(assessments.router, tags=["assessments"])
api_router.include_router(learner.router, tags=["learner"])
api_router.include_router(topics.router, tags=["topics"])
