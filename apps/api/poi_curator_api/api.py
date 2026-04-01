from fastapi import APIRouter

from poi_curator_api.routes.admin import router as admin_router
from poi_curator_api.routes.public import router as public_router

api_router = APIRouter()
api_router.include_router(public_router)
api_router.include_router(admin_router)
