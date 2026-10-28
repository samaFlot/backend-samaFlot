from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound

from .models import DocumentVehicule
from .serializers import DocumentVehiculeSerializer


class DocumentVehiculeViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentVehiculeSerializer

    def get_queryset(self):
        responsable = self.request.user.responsable

        return DocumentVehicule.objects.filter(
            vehicule__responsable=responsable
        )

    @action(detail=True, methods=["get"])
    def telecharger(self, request, pk=None):
        document = self.get_object()

        if not document.fichier:
            raise NotFound("Aucun fichier associé à ce document.")

        return FileResponse(
            document.fichier.open("rb"),
            as_attachment=True,
            filename=document.fichier.name.split("/")[-1],
        )