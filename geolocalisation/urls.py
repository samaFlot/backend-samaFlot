from django.urls import path
from .views import EnvoyerPositionView, SuiviVehiculesView

urlpatterns = [
    path("positions/", EnvoyerPositionView.as_view(), name="envoyer-position"),
    path("suivi/", SuiviVehiculesView.as_view(), name="suivi-vehicules"),
]