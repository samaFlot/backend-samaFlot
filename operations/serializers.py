from rest_framework import serializers
from comptes.models import Agent
from flotte.models import Vehicule
from flotte.serializers import VehiculeSerializer
from flotte.serializers import AgentListSerializer
from .models import DemandeChargement, Mission
import datetime
from django.utils import timezone


# ============================================================
# Demandes de chargement
# ============================================================

class DemandeChargementListSerializer(serializers.ModelSerializer):
    """Utilisé pour la liste des demandes (écran cartes) et comme base du détail."""
    class Meta:
        model = DemandeChargement
        fields = ["id", "demandeur", "nombre_vehicules_demandes", "date_chargement",
                  "heure_chargement", "point_depart", "destination", "description",
                  "statut", "date_creation"]


class DemandeChargementCreateSerializer(serializers.ModelSerializer):
    """Utilisé uniquement pour la création manuelle par le Responsable."""
    class Meta:
        model = DemandeChargement
        fields = ["id", "demandeur", "nombre_vehicules_demandes", "date_chargement",
                  "heure_chargement", "point_depart", "destination", "description"]
        # Pas de champ "statut" ici : il vaut toujours PREVU par défaut (défini dans le modèle),
        # impossible pour le Responsable de le choisir à la création


class MissionResumeSerializer(serializers.ModelSerializer):
    """Version allégée d'une Mission, utilisée UNIQUEMENT dans le bloc
    'Missions créées' du détail d'une demande — pas pour l'écran Missions lui-même."""
    vehicule_immatriculation = serializers.CharField(source="vehicule.immatriculation")
    # source="vehicule.immatriculation" : va chercher ce champ en traversant la relation FK,
    # pour renvoyer un JSON plat côté frontend plutôt qu'un objet imbriqué
    agent_nom = serializers.CharField(source="agent.utilisateur.last_name")
    agent_prenom = serializers.CharField(source="agent.utilisateur.first_name")

    class Meta:
        model = Mission
        fields = ["id", "statut", "vehicule_immatriculation", "agent_nom", "agent_prenom"]


class DemandeChargementDetailSerializer(DemandeChargementListSerializer):
    """Hérite de la version liste, et ajoute ce qui n'est utile que sur l'écran de détail."""
    missions = MissionResumeSerializer(many=True, read_only=True)
    # many=True : une demande a PLUSIEURS missions potentielles, donc DRF sérialise une liste
    nombre_missions_creees = serializers.IntegerField(read_only=True)
    peut_creer_mission = serializers.BooleanField(read_only=True)
    # Ces deux champs viennent directement des @property du modèle — DRF sait les lire
    # comme des attributs normaux, sans savoir que ce sont des propriétés calculées

    class Meta(DemandeChargementListSerializer.Meta):
        fields = DemandeChargementListSerializer.Meta.fields + [
            "missions", "nombre_missions_creees", "peut_creer_mission"
        ]
        # On réutilise la liste de champs du parent, et on ajoute juste les nouveaux


# ============================================================
# Missions
# ============================================================

class MissionListSerializer(serializers.ModelSerializer):
    """Pour l'écran 'Liste des missions' — vue plate, une ligne par mission."""
    demandeur = serializers.CharField(source="demande_chargement.demandeur")
    point_depart = serializers.CharField(source="demande_chargement.point_depart")
    destination = serializers.CharField(source="demande_chargement.destination")
    date_chargement = serializers.DateField(source="demande_chargement.date_chargement")
    heure_chargement = serializers.TimeField(source="demande_chargement.heure_chargement")
    # Toutes ces infos viennent de la demande liée, pas de la mission elle-même —
    # cohérent avec la règle "les infos de chargement viennent de la demande, pas saisies à nouveau"
    vehicule_immatriculation = serializers.CharField(source="vehicule.immatriculation")
    agent_nom = serializers.CharField(source="agent.utilisateur.last_name")
    agent_prenom = serializers.CharField(source="agent.utilisateur.first_name")

    class Meta:
        model = Mission
        fields = ["id", "demandeur", "point_depart", "destination", "date_chargement",
                  "heure_chargement","date_fin_prevue", "vehicule_immatriculation", "agent_nom", "agent_prenom", "statut"]


class MissionDetailSerializer(serializers.ModelSerializer):
    """Pour l'écran 'Détail d'une mission' — objets imbriqués complets, pas juste des champs plats."""
    demande_chargement = DemandeChargementListSerializer(read_only=True)
    vehicule = VehiculeSerializer(read_only=True)
    agent = AgentListSerializer(read_only=True)
    # Ici on réutilise carrément les serializers déjà écrits ailleurs (VehiculeSerializer,
    # AgentListSerializer) plutôt que de dupliquer les champs un par un — évite la répétition

    class Meta:
        model = Mission
        fields = ["id", "demande_chargement", "vehicule", "agent", "statut",
                  "date_creation", "date_debut","date_fin_prevue", "date_terminee", "date_annulee"]

#Pourquoi j'ai choisi Serializer plutôt que ModelSerializer
#Parce que les champs qu'on reçoit du frontend (demande_chargement, vehicule, agent, date_fin_prevue — des IDs et une date) ne correspondent pas un-à-un à ce qu'on veut vraiment enregistrer sur Mission. Il y a une transformation à faire :
#On reçoit des IDs, mais on veut travailler avec les vrais objets (DemandeChargement, Vehicule, Agent) — c'est justement ce que fait PrimaryKeyRelatedField automatiquement (aller chercher l'objet correspondant à l'ID)
class MissionCreateSerializer(serializers.Serializer):
    """serializers.Serializer (pas ModelSerializer) : on ne veut recevoir QUE des IDs
    en entrée (demande_chargement, vehicule, agent), pas tous les champs du modèle Mission."""
    demande_chargement = serializers.PrimaryKeyRelatedField(queryset=DemandeChargement.objects.all())
    vehicule = serializers.PrimaryKeyRelatedField(queryset=Vehicule.objects.all())
    agent = serializers.PrimaryKeyRelatedField(queryset=Agent.objects.all())
    # PrimaryKeyRelatedField : le frontend envoie juste un id (ex. 5), DRF(avec PrimaryKeyRelatedField) va chercher
    # automatiquement l'objet correspondant dans le queryset(aller chercher l'objet correspondant à l'ID)
    date_fin_prevue = serializers.DateTimeField()

    #attrs représente toutes les données du serializer qui ont déjà été validées(validations de base des champs), regroupées dans un dictionnaire.
    #parfois, ton métier impose une règle supplémentaire que DRF ne peut pas connaître automatiquement.C'est là que tu écris cette fonction
    #donc on ajoute une validation personnalisée à la validation normale(ajouter les regles metiers).
    def validate(self, attrs):
        # validate() reçoit TOUS les champs ensemble, utile ici car
        # les règles dépendent de plusieurs champs à la fois (demande + véhicule + agent)
        responsable = self.context["responsable"]
        # self.context : dictionnaire passé manuellement depuis la vue,
        # ici pour connaître le Responsable connecté sans le faire deviner par le serializer
        demande = attrs["demande_chargement"]
        vehicule = attrs["vehicule"]
        agent = attrs["agent"]
        date_fin_prevue = attrs["date_fin_prevue"]

        # --- Sécurité : vérifier que tout appartient bien au même Responsable ---
        # Indispensable car demande/vehicule/agent arrivent comme des IDs envoyés par le
        # client — rien n'empêche techniquement d'envoyer l'id d'une ressource d'un AUTRE
        # Responsable si on ne vérifie pas explicitement ici
        if demande.responsable_id != responsable.id:
            raise serializers.ValidationError("Cette demande n'appartient pas à votre entreprise.")
        if vehicule.responsable_id != responsable.id:
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre entreprise.")
        if agent.responsable_id != responsable.id:
            raise serializers.ValidationError("Cet agent n'appartient pas à votre entreprise.")

        # --- Règles métier ---
        if demande.statut != DemandeChargement.Statut.PREVU:
            raise serializers.ValidationError(
                "Impossible de créer une mission : cette demande n'est plus au statut Prévu."
            )
        if not demande.peut_creer_mission:
            # Réutilise directement la @property du modèle
            raise serializers.ValidationError(
                "Le nombre de missions demandées pour cette demande a déjà été atteint."
            )
         # --- fabriquer une seule date + heure complète à partir des deux champs de DemandeChargement ---
        debut_prevu = timezone.make_aware(
            datetime.datetime.combine(demande.date_chargement, demande.heure_chargement)
        )

        if date_fin_prevue <= debut_prevu:
            raise serializers.ValidationError(
                "La date de fin prévue doit être après la date et l'heure de chargement."
            )

        # --- Vérification de chevauchement pour le véhicule ---
        missions_vehicule = Mission.objects.filter(
            vehicule=vehicule, statut__in=[Mission.Statut.PREVU, Mission.Statut.EN_COURS]
        )
        for mission in missions_vehicule:
            if mission.chevauche(debut_prevu, date_fin_prevue):
                raise serializers.ValidationError(
                    f"Ce véhicule est déjà affecté à une autre mission sur cette période "
                    f"(mission #{mission.id})."
                )

        # --- Vérification de chevauchement pour l'agent ---
        missions_agent = Mission.objects.filter(
            agent=agent, statut__in=[Mission.Statut.PREVU, Mission.Statut.EN_COURS]
        )
        for mission in missions_agent:
            if mission.chevauche(debut_prevu, date_fin_prevue):
                raise serializers.ValidationError(
                    f"Cet agent est déjà affecté à une autre mission sur cette période "
                    f"(mission #{mission.id})."
                )

        return attrs
        # Si on arrive jusqu'ici sans exception levée, toutes les règles sont respectées

    #appeler quand on cree une mission.
    #car serializers.Serializer ne sait pas comment enregistrer quoi que ce soit tout seul
    #Contrairement à ModelSerializer, qui devine automatiquement comment créer un objet à partir d'un modèle(parce qu'il connaît la classe du modèle via Meta.model)
    def create(self, validated_data):
        mission = Mission.objects.create(
            demande_chargement=validated_data["demande_chargement"],
            vehicule=validated_data["vehicule"],
            agent=validated_data["agent"],
            date_fin_prevue=validated_data["date_fin_prevue"],
            statut=Mission.Statut.PREVU,
        )
        return mission