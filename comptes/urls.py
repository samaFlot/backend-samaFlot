# comptes/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView, ProfilView, ResponsableViewSet
from rest_framework.routers import DefaultRouter

#routeur qui va gérer automatiquement les routes de mes ViewSets
router = DefaultRouter()
#enregistre une nouvelle ressource appelée responsables, et la vue qui va la gérer est ResponsableViewSet
#router peut créer automatiquement les URLs correspondantes.
router.register(r"responsables", ResponsableViewSet, basename="responsable")

urlpatterns = [
    path("connexion/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("connexion/rafraichir/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profil/", ProfilView.as_view(), name="profil"),
]
#Ajouter à ma liste de routes toutes les routes créées automatiquement par le router.
urlpatterns += router.urls