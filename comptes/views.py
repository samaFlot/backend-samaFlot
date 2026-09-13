# comptes/views.py
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import CustomTokenObtainPairSerializer, UserProfileSerializer

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Responsable
from .permissions import EstAdmin
from .utils import generer_mot_de_passe, envoyer_identifiants
from .serializers import (
    ResponsableListSerializer, ResponsableCreateSerializer, ResponsableDetailSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# profil de l'utilisateur. Un utilisateur connecter peut voir son profil et peut le modifier.
# le token JWT permet de savoir quel utilisateur est connecté
class ProfilView(RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user



class ResponsableViewSet(viewsets.ModelViewSet):
    permission_classes = [EstAdmin]
    #Récupérer les responsables + leur utilisateur associé, puis les classer du plus récemment créé au plus ancien
    queryset = Responsable.objects.select_related("utilisateur").order_by("-utilisateur__date_joined")
    http_method_names = ["get", "post"]  # on bloque PUT/PATCH/DELETE : pas prévus sur ce modèle

    def get_serializer_class(self):
        if self.action == "create":
            return ResponsableCreateSerializer
        elif self.action == "retrieve":
            return ResponsableDetailSerializer
        return ResponsableListSerializer

    def create(self, request, *args, **kwargs):
        #Récupérer les données envoyées
        #get_serializer, cette méthode va chercher le serializer correspondant à l'action actuelle
        serializer = self.get_serializer(data=request.data)
        #Vérifier les données si c'est valide
        serializer.is_valid(raise_exception=True)
        #Créer le Responsable
        responsable = serializer.save()

        # On utilise un AUTRE serializer pour construire la réponse qu'on va envoyer au frontend,
        reponse_serializer = ResponsableDetailSerializer(responsable)
        # Prépare les informations HTTP supplémentaires à mettre dans la réponse après une création réussie
        headers = self.get_success_headers(reponse_serializer.data)
        return Response(reponse_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    #Cette méthode sert à récupérer la liste des Responsables en appliquant éventuellement des filtres.
    #Django appelle cette méthode quand il a besoin de récupérer les Responsables.
    def get_queryset(self):
        #récupère le queryset que tu as défini plus haut
        qs = super().get_queryset()
        #Ici Django regarde les paramètres présents dans l'URL.
        statut = self.request.query_params.get("statut")
        recherche = self.request.query_params.get("recherche")
        #Si l'utilisateur a fourni un statut, garde seulement les Responsables ayant ce statut.
        if statut:
            qs = qs.filter(statut_compte=statut)
        #Si l'utilisateur a fourni un texte de recherche
        if recherche:
            qs = qs.filter(
                Q(nom_entreprise__icontains=recherche) |
                Q(utilisateur__last_name__icontains=recherche) |
                Q(utilisateur__email__icontains=recherche)
            )
        return qs

    @action(detail=True, methods=["post"])
    def activer(self, request, pk=None):
        #Récupère le Responsable correspondant à l'identifiant
        responsable = self.get_object()
        # On change le statut métier du Responsable.
        responsable.statut_compte = "ACTIF"
        # On enregistre cette modification dans la base de données.
        responsable.save()
        # On active aussi le compte utilisateur Django associé.
        # Cela permet au Responsable de pouvoir se connecter.
        responsable.utilisateur.is_active = True
        # On enregistre également cette modification.
        responsable.utilisateur.save()
        # On renvoie au frontend le nouveau statut.
        return Response({"statut_compte": "ACTIF"})

    @action(detail=True, methods=["post"])
    def desactiver(self, request, pk=None):
        responsable = self.get_object()
        responsable.statut_compte = "DESACTIVE"
        responsable.save()
        responsable.utilisateur.is_active = False
        responsable.utilisateur.save()
        return Response({"statut_compte": "DESACTIVE"})

    @action(detail=True, methods=["post"], url_path="reinitialiser-acces")
    def reinitialiser_acces(self, request, pk=None):
        # Récupère le Responsable concerné.
        responsable = self.get_object()
        # Génère un nouveau mot de passe aléatoire.
        nouveau_mot_de_passe = generer_mot_de_passe()
        # Définit ce nouveau mot de passe sur le compte utilisateur.
        responsable.utilisateur.set_password(nouveau_mot_de_passe)
        # Sauvegarde le nouveau mot de passe hashé.
        responsable.utilisateur.save()
        # Envoie le nouveau mot de passe par email.
        envoyer_identifiants(
            responsable.utilisateur.email,
            responsable.utilisateur.first_name,
            nouveau_mot_de_passe,
            is_reset=True,
        )
        return Response({"message": "Nouveaux identifiants envoyés par email."})
