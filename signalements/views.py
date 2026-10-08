from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Signalement
from .serializers import SignalementSerializer
from notifications.models import Notification


class SignalementViewSet(viewsets.ModelViewSet):
    serializer_class = SignalementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        utilisateur = self.request.user

        # Agent : uniquement ses propres signalements
        if utilisateur.role == "AGENT":
            return Signalement.objects.filter(
                mission__agent=utilisateur.agent
            )

        # Responsable : uniquement les signalements de ses véhicules
        if utilisateur.role == "RESPONSABLE":
            return Signalement.objects.filter(
                mission__vehicule__responsable=utilisateur.responsable
            )

        return Signalement.objects.none()

    def create(self, request, *args, **kwargs):
        # Seul un agent peut créer un signalement
        if request.user.role != "AGENT":
            return Response(
                {"detail": "Seul un agent peut créer un signalement."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Valider les données du signalement
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Créer le signalement
        signalement = serializer.save()

        # Récupérer la mission concernée
        mission = signalement.mission

        # Récupérer le véhicule de la mission
        vehicule = mission.vehicule

        # Récupérer le responsable du véhicule
        responsable = vehicule.responsable

        # Créer automatiquement la notification
        Notification.objects.create(
            responsable=responsable,
            type=Notification.Type.SIGNALEMENT_CREE,
            titre="Nouveau signalement",
            message=(
                f"L'agent {request.user.first_name} "
                f"{request.user.last_name} a signalé un problème "
                f"sur le véhicule {vehicule.immatriculation}."
            ),
            mission=mission,
            signalement=signalement,
        )

        headers = self.get_success_headers(serializer.data)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "La modification d'un signalement n'est pas autorisée."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {"detail": "La modification d'un signalement n'est pas autorisée."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "La suppression d'un signalement n'est pas autorisée."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @action(detail=True, methods=["post"])
    def ignorer(self, request, pk=None):
        signalement = self.get_object()

        # Seul le responsable peut ignorer un signalement
        if request.user.role != "RESPONSABLE":
            return Response(
                {"detail": "Seul le responsable peut ignorer un signalement."},
                status=status.HTTP_403_FORBIDDEN
            )

        if signalement.statut != Signalement.Statut.A_TRAITER:
            return Response(
                {"detail": "Ce signalement ne peut plus être ignoré."},
                status=status.HTTP_400_BAD_REQUEST
            )

        signalement.statut = Signalement.Statut.IGNORE
        signalement.save()

        return Response(
            {"detail": "Le signalement a été ignoré."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def traiter(self, request, pk=None):
        signalement = self.get_object()

        if request.user.role != "RESPONSABLE":
            return Response(
                {"detail": "Seul le responsable peut traiter un signalement."},
                status=status.HTTP_403_FORBIDDEN
            )

        if signalement.statut != Signalement.Statut.A_TRAITER:
            return Response(
                {"detail": "Ce signalement ne peut plus être traité."},
                status=status.HTTP_400_BAD_REQUEST
            )

        vehicule = signalement.mission.vehicule

        vehicule.etat_technique = vehicule.EtatTechnique.A_VERIFIER
        vehicule.save()

        return Response(
            {
                "detail": (
                    "Le signalement est pris en charge. "
                    "Le véhicule doit être vérifié."
                )
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def remettre_en_bon_etat(self, request, pk=None):
        signalement = self.get_object()

        if request.user.role != "RESPONSABLE":
            return Response(
                {"detail": "Seul le responsable peut modifier l'état du véhicule."},
                status=status.HTTP_403_FORBIDDEN
            )

        if signalement.statut != Signalement.Statut.A_TRAITER:
            return Response(
                {"detail": "Ce signalement ne peut plus être traité."},
                status=status.HTTP_400_BAD_REQUEST
            )

        vehicule = signalement.mission.vehicule

        if vehicule.etat_technique != vehicule.EtatTechnique.A_VERIFIER:
            return Response(
                {"detail": "Le véhicule doit être à vérifier avant d'être remis en bon état."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Remettre le véhicule en bon état
        vehicule.etat_technique = vehicule.EtatTechnique.BON_ETAT
        vehicule.save()

        # Le signalement est maintenant réellement traité
        signalement.statut = Signalement.Statut.TRAITE
        signalement.save()

        return Response(
            {
                "detail": "Le véhicule a été remis en bon état et le signalement est traité."
            },
            status=status.HTTP_200_OK
        )