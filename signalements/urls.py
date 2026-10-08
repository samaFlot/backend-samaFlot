from rest_framework.routers import DefaultRouter

from .views import SignalementViewSet


router = DefaultRouter()

router.register("",SignalementViewSet,basename="signalement")

urlpatterns = router.urls