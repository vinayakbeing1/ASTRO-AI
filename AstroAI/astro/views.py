"""
AstroAI API Views

This module contains REST API views for the astrology application,
providing endpoints for workflow execution and analysis.
"""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from astro.serializers import WorkflowInSer

# from astro.services.graphs.question_graph import run_question_graph
from astro.services.graphs.parent_graph import run_chat_turn
from astro.services.graphs.timeline_graph import run_timeline_graph
from utils.select_dasha import filter_dasha_by_horizon
from .models import create_or_update_user_profile, UserProfile
from astro.services.graphs.remedies_graph import run_remedies_graph

# from astro.services.astrology.astro import current_annual_chart
from jhora.panchanga import drik
from astro.services.astrology.astro import get_current_transit_data


class AstrologyWorkflowView(APIView):
    """
    API endpoint for executing astrology analysis workflows.

    Accepts a question and processes it through the complete astrology
    analysis pipeline including question interpretation, chart analysis,
    and structured response generation.
    """

    def post(self, request):
        """
        Execute astrology workflow analysis.

        Args:
            request: HTTP request containing question and optional birth data

        Returns:
            JSON response with structured astrology analysis
        """
        serializer = WorkflowInSer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        # user = User.objects.get(id=26)
        # create_or_update_user_profile(User, user.profile, True)
        user = User.objects.get(id=26)

        chat_reply = run_chat_turn(
            "please suggest ",
            user,
        )
        print(chat_reply)
        # result = run_question_graph(question=validated_data["question"], user=user)
        return Response(
            {
                "message": chat_reply,
            },
            status=status.HTTP_200_OK,
        )
