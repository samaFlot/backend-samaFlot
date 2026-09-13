# operations/models.py
from django.db import models
from comptes.models import Responsable, Agent
from flotte.models import Vehicule


class DemandeChargement(models.Model):
    class Statut(models.TextChoices):
        PREVU = "PREVU", "Prévu"
        TRAITE = "TRAITE", "Traité"
        ANNULEE = "ANNULEE", "Annulée"

    responsable = models.ForeignKey(Responsable, on_delete=models.CASCADE, related_name="demandes_chargement")
    demandeur = models.CharField(max_length=255)
    nombre_vehicules_demandes = models.PositiveIntegerField()
    date_chargement = models.DateField()
    heure_chargement = models.TimeField()
    point_depart = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PREVU)
    date_creation = models.DateTimeField(auto_now_add=True)

    #@property permet d’ajouter au modèle une valeur calculée à partir des données qui existent déjà, sans créer un champ supplémentaire dans la base.
    @property
    def nombre_missions_creees(self):
        #on calcule le nombre de missions qui ont ete creer pour cette demmande et on exclue les missions annulees
        return self.missions.exclude(statut=Mission.Statut.ANNULEE).count()

    #Cette propriété permet de verifier si on a encore le droit de créer une mission pour cette demande ?
    @property
    def peut_creer_mission(self):
        #La demande doit encore être prévue et Il faut qu'il reste encore des véhicules à affecter
        return self.statut == self.Statut.PREVU and self.nombre_missions_creees < self.nombre_vehicules_demandes

    #on verifie si toutes les missions liées à cette demande sont terminées et on met automatiquement le statut de la demande a traiter.
    def verifier_completion(self):
        """Si toutes les missions non-annulées sont Terminée, passe la demande à Traité."""
        missions_actives = self.missions.exclude(statut=Mission.Statut.ANNULEE)
        #S'il existe au moins une mission active et que toutes les missions actives sont terminées
        #all() signifie est-ce que toutes les valeurs sont vraies ? et si c'est le cas ca retourne true
        if missions_actives.exists() and all(
            m.statut == Mission.Statut.TERMINEE for m in missions_actives
        ):
            self.statut = self.Statut.TRAITE
            self.save()

    def __str__(self):
        return f"{self.demandeur} — {self.point_depart} → {self.destination}"


class Mission(models.Model):
    class Statut(models.TextChoices):
        PREVU = "PREVU", "Prévu"
        EN_COURS = "EN_COURS", "En cours"
        TERMINEE = "TERMINEE", "Terminée"
        ANNULEE = "ANNULEE", "Annulée"

    demande_chargement = models.ForeignKey(
        DemandeChargement, on_delete=models.CASCADE, related_name="missions"
    )
    vehicule = models.ForeignKey(Vehicule, on_delete=models.SET_NULL, related_name="missions",null=True,blank=True)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, related_name="missions",null=True,blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PREVU)
    date_fin_prevue = models.DateTimeField()
    date_creation = models.DateTimeField(auto_now_add=True)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_terminee = models.DateTimeField(null=True, blank=True)
    date_annulee = models.DateTimeField(null=True, blank=True)

    @property
    def date_debut_prevue(self):
        """Combine la date/heure de chargement de la demande liée en un seul datetime."""
        import datetime
        from django.utils import timezone
        return timezone.make_aware(
            datetime.datetime.combine(
                self.demande_chargement.date_chargement,
                self.demande_chargement.heure_chargement,
            )
        )

    def chevauche(self, autre_debut, autre_fin):
        """vérifie si la période de cette mission chevauche une autre période et retourne true si c'est le cas."""
        return self.date_debut_prevue < autre_fin and self.date_fin_prevue > autre_debut

    def __str__(self):
        return f"Mission #{self.id} — {self.vehicule.immatriculation}"
