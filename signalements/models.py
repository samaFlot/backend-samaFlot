from django.db import models
from operations.models import Mission


class Signalement(models.Model):

    class Statut(models.TextChoices):
        A_TRAITER = "A_TRAITER", "À traiter"
        TRAITE = "TRAITE", "Traité"
        IGNORE = "IGNORE", "Ignoré"

    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name="signalements"
    )

    type_probleme = models.CharField(max_length=255)

    description = models.TextField()

    photo = models.ImageField(
        upload_to="signalements/",
        blank=True,
        null=True
    )

    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.A_TRAITER
    )

    date_creation = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Signalement #{self.id}"
