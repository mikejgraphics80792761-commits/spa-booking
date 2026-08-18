"""Invite serializers."""
from rest_framework import serializers

from .models import Invite


class InviteCreateSerializer(serializers.Serializer):
    """Validates input for the create endpoint."""

    email = serializers.EmailField()

    def create(self, validated_data: dict) -> Invite:
        """Persist and return a new Invite instance."""
        return Invite.objects.create(email=validated_data["email"])


class InviteAcceptSerializer(serializers.Serializer):
    """Validates input for the accept endpoint."""

    token = serializers.CharField(max_length=64)
    email = serializers.EmailField()
