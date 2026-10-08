from datetime import date, timedelta

from django.db import models
from flotte.models import Vehicule


class DocumentVehicule(models.Model):

    class Statut(models.TextChoices):
        VALIDE = "VALIDE", "Valide"
        EXPIRE_BIENTOT = "EXPIRE_BIENTOT", "Expire bientôt"
        EXPIRE = "EXPIRE", "Expiré"

    vehicule = models.ForeignKey(
        Vehicule,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    type_document = models.CharField(max_length=100)

    numero_document = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    date_emission = models.DateField()

    date_expiration = models.DateField()

    fichier = models.FileField(
        upload_to="documents_vehicules/"
    )

    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.VALIDE
    )

    date_creation = models.DateTimeField(auto_now_add=True)

    def calculer_statut(self):
        aujourd_hui = date.today()

        if self.date_expiration < aujourd_hui:
            return self.Statut.EXPIRE

        if self.date_expiration <= aujourd_hui + timedelta(days=30):
            return self.Statut.EXPIRE_BIENTOT

        return self.Statut.VALIDE

    def save(self, *args, **kwargs):
        self.statut = self.calculer_statut()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.type_document} - {self.vehicule.immatriculation}"