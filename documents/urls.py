from rest_framework.routers import DefaultRouter

from .views import DocumentVehiculeViewSet


router = DefaultRouter()

router.register(
    "",
    DocumentVehiculeViewSet,
    basename="documents"
)

urlpatterns = router.urls