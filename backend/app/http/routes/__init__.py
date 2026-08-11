"""Aaroh product routes."""

from .dsa_activity import router as dsa_activity_router
from .preparation_goal import router as preparation_goal_router

__all__ = ["dsa_activity_router", "preparation_goal_router"]
