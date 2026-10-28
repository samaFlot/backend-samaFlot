from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from comptes.permissions import EstResponsable
from comptes.models import Agent
from comptes.utils import generer_mot_de_passe, envoyer_identifiants
from .models import Vehicule
from .serializers import (
    VehiculeSerializer, VehiculeCreateSerializer, VehiculeUpdateSerializer, VehiculeDetailSerializer,
    AgentListSerializer, AgentCreateSerializer, AgentUpdateSerializer,
)
from signalements.models import Signalement


class VehiculeViewSet(viewsets.ModelViewSet):
    permission_classes = [EstResponsable]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        # On récupère uniquement les véhicules appartenant
        # au Responsable actuellement connecté.
        qs = Vehicule.objects.filter(responsable=self.request.user.responsable).order_by("-date_creation")
        # On regarde si un statut a été envoyé dans l'URL.
        statut = self.request.query_params.get("statut")
        # On regarde si une recherche a été envoyée dans l'URL.
        recherche = self.request.query_params.get("recherche")
        if statut:
            # on garde uniquement les véhicules ayant ce statut
            qs = qs.filter(statut=statut)
        if recherche:
            # on cherche ce texte dans l'immatriculation.
            qs = qs.filter(immatriculation__icontains=recherche)

        # On retourne la liste finale des véhicules.
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VehiculeDetailSerializer
        if self.action == "create":
            return VehiculeCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return VehiculeUpdateSerializer
        return VehiculeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        #si ce n'est pas valide, déclenche une erreur tout de suite.
        serializer.is_valid(raise_exception=True)
        #tu ajoutes une information au moment de la création : le Responsable a qui appartient le vehicule
        serializer.save(responsable=request.user.responsable)
        return Response(VehiculeSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(VehiculeSerializer(serializer.instance).data)

    @action(detail=True, methods=["post"], url_path="bon-etat")
    def bon_etat(self, request, pk=None):
        vehicule = self.get_object()

        # Le véhicule doit être à vérifier
        if vehicule.etat_technique != Vehicule.EtatTechnique.A_VERIFIER:
            return Response(
                {
                    "detail": "Le véhicule doit être à vérifier avant de pouvoir être remis en bon état."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupérer l'identifiant du signalement
        signalement_id = request.data.get("signalement_id")

        if not signalement_id:
            return Response(
                {"detail": "Le signalement_id est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupérer le signalement
        try:
            signalement = Signalement.objects.get(id=signalement_id)
        except Signalement.DoesNotExist:
            return Response(
                {"detail": "Signalement introuvable."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Vérifier que le signalement concerne bien ce véhicule
        if signalement.mission.vehicule != vehicule:
            return Response(
                {
                    "detail": "Ce signalement ne concerne pas ce véhicule."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Le signalement doit encore être à traiter
        if signalement.statut != Signalement.Statut.A_TRAITER:
            return Response(
                {
                    "detail": "Ce signalement n'est plus à traiter."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Remettre le véhicule en bon état
        vehicule.etat_technique = Vehicule.EtatTechnique.BON_ETAT
        vehicule.save()

        # Marquer le signalement comme traité
        signalement.statut = Signalement.Statut.TRAITE
        signalement.save()

        return Response(
            {
                "detail": "Le véhicule est maintenant en bon état et le signalement a été traité."
            },
            status=status.HTTP_200_OK
        )


class AgentViewSet(viewsets.ModelViewSet):
    permission_classes = [EstResponsable]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = Agent.objects.filter(responsable=self.request.user.responsable).select_related("utilisateur")
        disponible = self.request.query_params.get("disponible")
        recherche = self.request.query_params.get("recherche")
        if disponible is not None:
            qs = qs.filter(disponible=(disponible.lower() == "true"))
        if recherche:
            qs = qs.filter(
                Q(utilisateur__last_name__icontains=recherche) |
                Q(utilisateur__first_name__icontains=recherche)
            )
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AgentCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return AgentUpdateSerializer
        return AgentListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"responsable": request.user.responsable})
        serializer.is_valid(raise_exception=True)
        agent = serializer.save()
        return Response(AgentListSerializer(agent).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        agent = serializer.save()
        return Response(AgentListSerializer(agent).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.utilisateur.delete()  # supprime le CustomUser, l'Agent suit par cascade
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="reinitialiser-acces")
    def reinitialiser_acces(self, request, pk=None):
        agent = self.get_object()
        nouveau_mot_de_passe = generer_mot_de_passe()
        agent.utilisateur.set_password(nouveau_mot_de_passe)
        agent.utilisateur.save()
        envoyer_identifiants(
            agent.utilisateur.email,
            agent.utilisateur.first_name,
            nouveau_mot_de_passe,
            is_reset=True,
        )
        return Response({"message": "Nouveaux identifiants envoyés par email."})
