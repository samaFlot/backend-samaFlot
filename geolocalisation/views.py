from rest_framework import generics, status
from rest_framework.response import Response
from comptes.permissions import EstAgent, EstResponsable
from flotte.models import Vehicule
from .serializers import PositionEnvoyeeSerializer, VehiculePositionSerializer


class EnvoyerPositionView(generics.CreateAPIView):
    """Utilisé par SamaFlott Tracker (Agent) pour transmettre une position, toutes les ~10s."""
    # generics.CreateAPIView : vue générique DRF qui gère UNIQUEMENT le POST —
    # cet endpoint ne fait qu'une chose (recevoir une position), pas besoin de
    # la complexité d'un ViewSet qui gère plusieurs actions

    permission_classes = [EstAgent]
    # Seul un Agent (donc l'app Tracker, connectée avec un compte Agent) peut
    # appeler cet endpoint

    serializer_class = PositionEnvoyeeSerializer

    def create(self, request, *args, **kwargs):
        # On redéfinit create() pour pouvoir passer le contexte "agent" au serializer
        serializer = self.get_serializer(
            data=request.data, context={"agent": request.user.agent}
        )
        
        serializer.is_valid(raise_exception=True)
        # Déclenche validate_vehicule() du serializer — si le véhicule n'appartient
        # pas à cette entreprise, la requête s'arrête avec un 400 clair
        vehicule = serializer.save()
        # .save() appelle automatiquement .create() du serializer

        return Response(
            {"message": "Position mise à jour.", "vehicule": vehicule.immatriculation},
            status=status.HTTP_200_OK,
            # 200 (pas 201 "Created") : sémantiquement plus juste maintenant,
            # puisqu'on ne crée jamais vraiment une NOUVELLE ressource après le
            # premier appel — on met à jour la même ligne encore et encore.
            # 201 aurait été trompeur ici (ça sous-entend "quelque chose de neuf
            # vient d'être créé", ce qui n'est vrai qu'au tout premier envoi)
        )


class SuiviVehiculesView(generics.ListAPIView):
    """Utilisé côté Web par le Responsable — écran Suivi des véhicules."""
    # generics.ListAPIView : vue générique qui gère uniquement le GET (une liste)

    permission_classes = [EstResponsable]
    serializer_class = VehiculePositionSerializer

    def get_queryset(self):
        return Vehicule.objects.filter(
            responsable=self.request.user.responsable
        ).select_related("derniere_position")
        # Filtre les véhicules du Responsable connecté
        # select_related("derniere_position") : précharge cette relation en une seule requête SQL