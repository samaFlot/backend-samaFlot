from rest_framework.routers import DefaultRouter
from .views import VehiculeViewSet, AgentViewSet

router = DefaultRouter()
router.register(r"vehicules", VehiculeViewSet, basename="vehicule")
router.register(r"agents", AgentViewSet, basename="agent")

urlpatterns = router.urls