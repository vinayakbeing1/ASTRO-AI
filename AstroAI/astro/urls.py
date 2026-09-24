"""
URL configuration for AstroAI application.

This module defines URL patterns for the astrology API endpoints
and view mappings.
"""

from django.urls import path

from .api import api
from .views import AstrologyWorkflowView

urlpatterns = [
    path("workflow/run/", AstrologyWorkflowView.as_view(), name="astrology-workflow"),
    path("api/", api.urls),
]
