from django.db import models
from flotte.models import Vehicule


class DernierePosition(models.Model):
    vehicule = models.OneToOneField(
        Vehicule, on_delete=models.CASCADE, related_name="derniere_position"
    )

    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    # DecimalField, pas FloatField : les float en Python/SQL font des erreurs
    # d'arrondi binaire (ex. 0.1 + 0.2 ≠ 0.3 exactement) — inacceptable pour
    # des coordonnées GPS où la précision compte. DecimalField stocke la valeur
    # exacte telle qu'écrite. 6 décimales = précision d'environ 11 cm au sol

    date_envoi = models.DateTimeField(auto_now=True)
    # auto_now=True : Django met À JOUR ce champ automatiquement à CHAQUE fois
    # que .save() est appelé sur cet objet — pas besoin de le gérer nous-mêmes.
    # C'est différent de auto_now_add (qu'on utilisait pour date_creation ailleurs),
    # qui ne se remplit qu'UNE fois, à la création, et ne change plus jamais.
    # Ici on veut l'inverse : à chaque nouvelle position reçue, cette date DOIT
    # changer pour refléter "quand cette position a été reçue pour la dernière fois"

    def __str__(self):
        return f"{self.vehicule.immatriculation} — {self.date_envoi}"
        # Affichage lisible dans l'admin Django, plutôt que "DernierePosition object (1)"