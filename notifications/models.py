from django.db import models
from comptes.models import Responsable
from operations.models import Mission


class Notification(models.Model):
    class Type(models.TextChoices):
        MISSION_DEMARREE = "MISSION_DEMARREE", "Mission démarrée"
        MISSION_TERMINEE = "MISSION_TERMINEE", "Mission terminée"

    responsable = models.ForeignKey(
        Responsable,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    type = models.CharField(
        max_length=50,
        choices=Type.choices
    )

    titre = models.CharField(max_length=255)

    message = models.TextField()

    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True
    )

    lu = models.BooleanField(default=False)

    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre