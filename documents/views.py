from rest_framework import viewsets

from .models import DocumentVehicule
from .serializers import DocumentVehiculeSerializer


class DocumentVehiculeViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentVehiculeSerializer

    def get_queryset(self):
        responsable = self.request.user.responsable

        return DocumentVehicule.objects.filter(
            vehicule__responsable=responsable
        )