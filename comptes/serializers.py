from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

# comptes/serializers.py sert à transformer les données Python/Django en données JSON que ton frontend React peut recevoir, et inversement pour certains formulaires.

#On récupère le serializer JWT fourni par SimpleJWT
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
#On importe les serializers de Django REST Framework.
from rest_framework import serializers
#On importe nos modèles
from .models import CustomUser, Responsable, Agent
from .utils import generer_mot_de_passe, envoyer_identifiants

#Personnaliser la réponse de connexion JWT
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    #SimpleJWT vérifie si les information sont correct
    def validate(self, attrs):
        #Vérifie les informations de connexion reçues et retourne le resultat
        data = super().validate(attrs)
        #self.user correspond à l'utilisateur qui vient de se connecter.
        user = self.user

        data["role"] = user.role
        data["email"] = user.email
        data["nom"] = user.last_name
        data["prenom"] = user.first_name
        data["photo"] = user.photo.url if user.photo else None

        if user.role == CustomUser.Role.RESPONSABLE:
            responsable = user.responsable
            data["nom_entreprise"] = responsable.nom_entreprise
            data["statut_compte"] = responsable.statut_compte

        elif user.role == CustomUser.Role.AGENT:
            agent = user.agent
            data["responsable_id"] = agent.responsable_id
            data["nom_entreprise"] = agent.responsable.nom_entreprise
            data["disponible"] = agent.disponible

        return data


#on veut transformer le modèle CustomUser en JSON
#ModelSerializer est pratique parce qu'il sait automatiquement travailler avec les champs du modèle
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "email", "first_name", "last_name", "telephone", "photo", "role", "adresse"]
        read_only_fields = ["role"]

    # Appelée seulement quand un email est envoyé
    def validate_email(self, value):
        utilisateur = self.instance

        # Un email inchangé est toujours accepté
        if value == utilisateur.email:
            return value

        # Seul l'admin peut changer son email
        if utilisateur.role != CustomUser.Role.ADMIN:
            raise serializers.ValidationError(
                "Vous ne pouvez pas modifier votre email."
            )

        return value


#créer un serializer basé sur le modèle Responsable
class ResponsableListSerializer(serializers.ModelSerializer):
    #créer un champ qui s'appelle nom, mais sa valeur doit venir de utilisateur.last_name
    nom = serializers.CharField(source="utilisateur.last_name")
    prenom = serializers.CharField(source="utilisateur.first_name")
    email = serializers.EmailField(source="utilisateur.email")
    telephone = serializers.CharField(source="utilisateur.telephone")
    adresse = serializers.CharField(source="utilisateur.adresse")
    photo = serializers.ImageField(source="utilisateur.photo", read_only=True)
    date_creation = serializers.DateTimeField(source="utilisateur.date_joined")

    class Meta:
        model = Responsable
        fields = ["id", "nom_entreprise", "nom", "prenom", "email", "telephone", "adresse",
                  "photo", "statut_compte", "date_creation"]


#Un Responsable est composé de données provenant de deux modèles donc on va nous meme contrôler la création
class ResponsableCreateSerializer(serializers.Serializer):
    #On utilise serializers.CharField dans le serializer pour dire comment une donnée doit être reçue.
    nom_entreprise = serializers.CharField(max_length=255)
    nom = serializers.CharField(max_length=150)
    prenom = serializers.CharField(max_length=150)
    telephone = serializers.CharField(max_length=20)
    adresse = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    photo = serializers.ImageField(required=False, allow_null=True)

    #DRF appelle automatiquement cette méthode lorsqu'il doit valider
    def validate_email(self, value):
        #on verifie Est-ce qu'un utilisateur existe déjà avec cet email
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value

    #creation d'un responsable
    def create(self, validated_data):
        mot_de_passe = generer_mot_de_passe()

        #on crée l'utilisateur principal
        user = CustomUser.objects.create_user(
            email=validated_data["email"],
            password=mot_de_passe,
            first_name=validated_data["prenom"],
            last_name=validated_data["nom"],
            telephone=validated_data["telephone"],
            adresse=validated_data["adresse"],
            role=CustomUser.Role.RESPONSABLE,
        )

        if validated_data.get("photo"):
            user.photo = validated_data["photo"]
            user.save()

        #ensuite on crée le Responsable
        responsable = Responsable.objects.create(
            utilisateur=user,
            nom_entreprise=validated_data["nom_entreprise"],
        )

        #envoi de l'email
        envoyer_identifiants(user.email, validated_data["prenom"], mot_de_passe)
        return responsable

class ResponsableUpdateSerializer(serializers.Serializer):
    nom_entreprise = serializers.CharField(max_length=255)
    nom = serializers.CharField(max_length=150)
    prenom = serializers.CharField(max_length=150)
    telephone = serializers.CharField(max_length=20)
    adresse = serializers.CharField(max_length=255)
    email = serializers.EmailField()

    # Vérifier que l'email n'est pas déjà utilisé par quelqu'un d'autre
    def validate_email(self, value):
        utilisateur = self.instance.utilisateur

        if CustomUser.objects.filter(email=value).exclude(pk=utilisateur.pk).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")

        return value

    # Enregistrer les modifications
    def update(self, responsable, validated_data):
        utilisateur = responsable.utilisateur

        # Le nom de l'entreprise est dans le modèle Responsable
        responsable.nom_entreprise = validated_data["nom_entreprise"]
        responsable.save()

        # Les autres informations sont dans le compte utilisateur
        utilisateur.last_name = validated_data["nom"]
        utilisateur.first_name = validated_data["prenom"]
        utilisateur.telephone = validated_data["telephone"]
        utilisateur.adresse = validated_data["adresse"]
        utilisateur.email = validated_data["email"]
        utilisateur.save()

        return responsable


class ResponsableDetailSerializer(ResponsableListSerializer):
    class Meta(ResponsableListSerializer.Meta):
        pass


class ChangePasswordSerializer(serializers.Serializer):
    ancien_mot_de_passe = serializers.CharField(write_only=True)
    nouveau_mot_de_passe = serializers.CharField(write_only=True)
    confirmation = serializers.CharField(write_only=True)

    # Vérifier que l'ancien mot de passe est bon
    def validate_ancien_mot_de_passe(self, value):
        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError(
                "L'ancien mot de passe est incorrect."
            )

        return value

    # Appliquer les règles de sécurité de Django (longueur, mot de passe trop courant...)
    def validate_nouveau_mot_de_passe(self, value):
        user = self.context["request"].user

        try:
            validate_password(value, user)
        except DjangoValidationError as erreur:
            raise serializers.ValidationError(list(erreur.messages))

        return value

    # Vérifications qui comparent plusieurs champs
    def validate(self, attrs):
        if attrs["nouveau_mot_de_passe"] != attrs["confirmation"]:
            raise serializers.ValidationError(
                {"confirmation": "Les deux mots de passe ne correspondent pas."}
            )

        if attrs["nouveau_mot_de_passe"] == attrs["ancien_mot_de_passe"]:
            raise serializers.ValidationError(
                {
                    "nouveau_mot_de_passe": (
                        "Le nouveau mot de passe doit être différent de l'ancien."
                    )
                }
            )

        return attrs

    # Enregistrer le nouveau mot de passe (hashé par set_password)
    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["nouveau_mot_de_passe"])
        user.save(update_fields=["password"])
        return user