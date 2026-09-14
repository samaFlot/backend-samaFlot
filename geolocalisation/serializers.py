from rest_framework import serializers
from flotte.models import Vehicule
from .models import DernierePosition


class PositionEnvoyeeSerializer(serializers.Serializer):
    # mais on garde Serializer simple
    # ici pour pouvoir personnaliser la validation ET parce qu'on ne veut PAS
    # exposer date_envoi comme un champ à saisir (il est toujours automatique)

    vehicule = serializers.PrimaryKeyRelatedField(queryset=Vehicule.objects.all())
    # PrimaryKeyRelatedField : l'app Tracker envoie juste un id de véhicule
    # (ex. 3), et DRF va chercher l'objet Vehicule correspondant automatiquement —
    # avec une erreur 400 propre si cet id n'existe pas

    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_vehicule(self, value):
        # DRF appelle automatiquement validate_<nom_du_champ> avant de continuer,
        # ici uniquement pour vérifier le champ "vehicule"
        agent = self.context["agent"]
        # self.context["agent"] : transmis manuellement depuis la vue (voir plus
        # bas dans EnvoyerPositionView) — le serializer ne devine jamais qui est
        # connecté tout seul, il faut toujours le lui donner explicitement
        if value.responsable_id != agent.responsable_id:
            # Sécurité indispensable : le véhicule arrive comme un ID envoyé par
            # le client (l'app Tracker) — sans cette vérification, un Agent
            # pourrait techniquement envoyer une fausse position pour le véhicule
            # d'une AUTRE entreprise, juste en devinant/testant des ids
            raise serializers.ValidationError("Ce véhicule n'appartient pas à votre entreprise.")
        return value

    def create(self, validated_data):
        vehicule = validated_data["vehicule"]

        # update_or_create() renvoie toujours un TUPLE : (objet, booléen).
        # Le booléen indique si l'objet a été CRÉÉ (True) ou juste MIS À JOUR
        # (False) — ici on ne s'en sert pas, d'où le "_" (convention Python pour
        # "je récupère cette valeur mais je ne m'en sers pas")
        position, _ = DernierePosition.objects.update_or_create(
            #on verifie si le vehicule a une foi envoyer une positon
            #si oui on fait update de sa position sinon on cree la position
            vehicule=vehicule,
            defaults={
                "latitude": validated_data["latitude"],
                "longitude": validated_data["longitude"],
            },
        )

        return vehicule
        # On retourne le véhicule (pas la position) — pratique pour que la vue
        # puisse afficher son immatriculation dans sa réponse


class VehiculePositionSerializer(serializers.ModelSerializer):
    # Ce serializer part du modèle Vehicule car l'écran
    # "Suivi des véhicules" affiche une LISTE DE VÉHICULES, chacun avec sa position 

    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    date_envoi = serializers.SerializerMethodField()
    # SerializerMethodField plutôt que source="derniere_position.latitude" :
    # un accès direct planterait si le véhicule n'a AUCUNE position encore envoyée 
    # la méthode personnalisée permet de gérer ce cas proprement

    class Meta:
        model = Vehicule
        fields = ["id", "immatriculation", "statut", "latitude", "longitude", "date_envoi"]

    def get_latitude(self, obj):
        # get_<nom_du_champ> : DRF appelle cette méthode pour CHAQUE véhicule (obj) de la liste, 
        # afin de remplir la valeur du champ "latitude"
        return obj.derniere_position.latitude if hasattr(obj, "derniere_position") else None
        # hasattr(obj, "derniere_position") : "est-ce que ce véhicule a une DernierePosition liée ?"
        # AVANT d'essayer d'y accéder pour tout véhicule jamais localisé.

    def get_longitude(self, obj):
        return obj.derniere_position.longitude if hasattr(obj, "derniere_position") else None

    def get_date_envoi(self, obj):
        return obj.derniere_position.date_envoi if hasattr(obj, "derniere_position") else None