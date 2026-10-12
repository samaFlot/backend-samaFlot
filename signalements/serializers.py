from rest_framework import serializers

from .models import Signalement


class SignalementSerializer(serializers.ModelSerializer):
    vehicule = serializers.SerializerMethodField()
    mission_details = serializers.SerializerMethodField()

    class Meta:
        model = Signalement
        fields = [
            "id",
            "mission",
            "mission_details",
            "vehicule",
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
            "mission_details",
            "vehicule",
        ]

    def get_mission_details(self, obj):
        mission = obj.mission
        agent = mission.agent
        utilisateur = agent.utilisateur

        return {
            "id": mission.id,
            "statut": mission.statut,
            "date_fin_prevue": (
                mission.demande_chargement.date_fin_prevue.isoformat()
                if mission.demande_chargement.date_fin_prevue
                else None
            ),
            "agent": {
                "id": agent.id,
                "prenom": utilisateur.first_name,
                "nom": utilisateur.last_name,
                "photo": (
                    utilisateur.photo.url
                    if utilisateur.photo
                    else None
                ),
                "telephone": utilisateur.telephone,
                "disponible": agent.disponible,
            },
        }

    def get_vehicule(self, obj):
        vehicule = obj.mission.vehicule

        return {
            "id": vehicule.id,
            "immatriculation": vehicule.immatriculation,
            "type_vehicule": vehicule.type_vehicule,
            "statut": vehicule.statut,
            "etat_technique": vehicule.etat_technique,
        }

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