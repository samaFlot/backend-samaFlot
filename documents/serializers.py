from rest_framework import serializers

from .models import DocumentVehicule


class DocumentVehiculeSerializer(serializers.ModelSerializer):

    class Meta:
        model = DocumentVehicule
        fields = [
            "id",
            "vehicule",
            "type_document",
            "numero_document",
            "date_emission",
            "date_expiration",
            "fichier",
            "statut",
            "date_creation",
        ]
        read_only_fields = [
            "id",
            "statut",
            "date_creation",
        ]

    def validate_vehicule(self, vehicule):
        responsable = self.context["request"].user.responsable

        if vehicule.responsable != responsable:
            raise serializers.ValidationError(
                "Vous ne pouvez pas gérer les documents de ce véhicule."
            )

        return vehicule