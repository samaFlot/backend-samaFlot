# flotte/models.py
from django.db import models
from comptes.models import Responsable


class Vehicule(models.Model):
    class Statut(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        EN_MISSION = "EN_MISSION", "En mission"
        EN_PANNE = "EN_PANNE", "En panne"

    responsable = models.ForeignKey(Responsable, on_delete=models.CASCADE, related_name="vehicules")
    immatriculation = models.CharField(max_length=20, unique=True)
    type_vehicule = models.CharField(max_length=100)
    #help_text est simplement un texte d'aide associé au champ.
    #ex: Quand quelqu'un utilise ce champ, affiche-lui l'indication en kg
    poids = models.DecimalField(max_digits=8, decimal_places=2, help_text="en kg")
    hauteur = models.DecimalField(max_digits=5, decimal_places=2, help_text="en m")
    largeur = models.DecimalField(max_digits=5, decimal_places=2, help_text="en m")
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.DISPONIBLE)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.immatriculation
