from fastapi import APIRouter

from app.api.v1 import auth, deals, health, offers, suppliers

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(suppliers.router)
api_router.include_router(offers.router)
api_router.include_router(deals.router)
