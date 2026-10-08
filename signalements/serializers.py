from rest_framework import serializers

from .models import Signalement


class SignalementSerializer(serializers.ModelSerializer):

    class Meta:
        model = Signalement
        fields = [
            "id",
            "mission",
            "type_probleme",
            "description",
            "photo",
            "statut",
            "date_creation",
        ]
        read_only_fields = [
            "id",
            "statut",
            "date_creation",
        ]

    def validate_mission(self, mission):
        agent = self.context["request"].user.agent

        if mission.agent != agent:
            raise serializers.ValidationError(
                "Vous ne pouvez pas créer un signalement pour cette mission."
            )

        if mission.statut != mission.Statut.EN_COURS:
            raise serializers.ValidationError(
                "Un signalement peut uniquement être créé pendant une mission en cours."
            )

        return mission