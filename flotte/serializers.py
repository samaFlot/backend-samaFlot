# flotte/serializers.py
from rest_framework import serializers
from comptes.models import Agent, CustomUser
from .models import Vehicule
from comptes.utils import generer_mot_de_passe, envoyer_identifiants


# --- Véhicules ---

#transformer un objet Vehicule en données json
class VehiculeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicule
        fields = ["id", "immatriculation", "type_vehicule", "poids", "hauteur", "largeur",
                  "statut", "date_creation"]

# valide les données lors de la creation d'un vehicule
class VehiculeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicule
        #fields représente les champs du véhicule que le serializer va prendre en compte
        fields = ["id", "immatriculation", "type_vehicule", "poids", "hauteur", "largeur"]
        # pas de champ "statut" : reste DISPONIBLE par défaut

#ce serializer va vérifier et traiter les données envoyées lors de la modification d'un vehicule
class VehiculeUpdateSerializer(serializers.ModelSerializer):
    #imposes les statuts que le Responsable peut envoyer dans une modification
    statut = serializers.ChoiceField(
        choices=[(Vehicule.Statut.DISPONIBLE, "Disponible"), (Vehicule.Statut.EN_PANNE, "En panne")],
        #statut n'est pas obligatoire
        required=False,
    )

    class Meta:
        model = Vehicule
        #Les champs modifiables
        fields = ["id", "immatriculation", "type_vehicule", "poids", "hauteur", "largeur", "statut"]

    def validate_statut(self, value):
        #si le véhicule est EN_MISSION on ne peut pas modifier son statut
        if self.instance and self.instance.statut == Vehicule.Statut.EN_MISSION:
            raise serializers.ValidationError(
                "Impossible de modifier le statut d'un véhicule actuellement en mission."
            )
        return value


# --- Agents ---

#transformer un objet Agent en données JSON
class AgentListSerializer(serializers.ModelSerializer):
    #On utilise serializers.CharField dans le serializer pour dire comment une donnée doit être reçue ou représentée par l'API
    nom = serializers.CharField(source="utilisateur.last_name")
    prenom = serializers.CharField(source="utilisateur.first_name")
    email = serializers.EmailField(source="utilisateur.email")
    telephone = serializers.CharField(source="utilisateur.telephone")

    class Meta:
        model = Agent
        #Quand j'affiche un Agent, je veux envoyer uniquement ces informations
        fields = ["id", "nom", "prenom", "email", "telephone", "disponible"]


class AgentCreateSerializer(serializers.Serializer):
    nom = serializers.CharField(max_length=150)
    prenom = serializers.CharField(max_length=150)
    telephone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    # pas de champ mot_de_passe : généré automatiquement et envoyé par email

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value

    def create(self, validated_data):
        #self.context représente les informations supplémentaires qu'on donne au serializer depuis la vue
        #ici on récupère le responsable qu'on a donné au serialize
        responsable = self.context["responsable"]
        mot_de_passe = generer_mot_de_passe()

        user = CustomUser.objects.create_user(
            email=validated_data["email"],
            password=mot_de_passe,
            first_name=validated_data["prenom"],
            last_name=validated_data["nom"],
            telephone=validated_data["telephone"],
            role=CustomUser.Role.AGENT,
        )
        agent = Agent.objects.create(utilisateur=user, responsable=responsable)

        envoyer_identifiants(user.email, validated_data["prenom"], mot_de_passe)
        return agent

#On utilise Serializer simple parce que les informations à modifier se trouvent dans CustomUser, et non directement dans le modèle Agent
class AgentUpdateSerializer(serializers.Serializer):
    nom = serializers.CharField(max_length=150, required=False)
    prenom = serializers.CharField(max_length=150, required=False)
    telephone = serializers.CharField(max_length=20, required=False)
    email = serializers.EmailField(required=False)

    def update(self, instance, validated_data):
        #Récupérer le CustomUser
        user = instance.utilisateur
        for champ, attr in [
            ("nom", "last_name"),
            ("prenom", "first_name"),
            ("telephone", "telephone"),
            ("email", "email"),
        ]:
            if champ in validated_data:
                #setattr sert a modifier un attribut d'un objet.
                # on dit: Dans user, mets la nouvelle valeur dans le champ indiqué par attr
                setattr(user, attr, validated_data[champ])
        #on sauvegarde
        user.save()
        #on retourne l'utilisateur modifier
        return instance