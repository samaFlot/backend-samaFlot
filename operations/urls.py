from rest_framework.routers import DefaultRouter
from .views import DemandeChargementViewSet, MissionViewSet, creer_demande_depuis_n8n
from django.urls import path

router = DefaultRouter()
router.register(r"demandes-chargement", DemandeChargementViewSet, basename="demande-chargement")
router.register(r"missions", MissionViewSet, basename="mission")


urlpatterns = [ 
    path( 
        "demandes-chargement/n8n/", creer_demande_depuis_n8n, name="creer-demande-depuis-n8n", 
        ), 
    ] 
urlpatterns += router.urls




#GET    /api/operations/demandes-chargement/
#POST   /api/operations/demandes-chargement/
#GET    /api/operations/demandes-chargement/{id}/
#POST   /api/operations/demandes-chargement/{id}/annuler/

#GET    /api/operations/missions/
#POST   /api/operations/missions/
#GET    /api/operations/missions/{id}/
#POST   /api/operations/missions/{id}/demarrer/   (Agent uniquement)
#POST   /api/operations/missions/{id}/terminer/   (Agent uniquement)