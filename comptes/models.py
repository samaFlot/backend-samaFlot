# comptes/models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

#BaseUserManager est une classe Django qui permet de définir comment nos utilisateurs sont créés.
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        #Si aucun email n'est fourni, on bloque la création.
        if not email:
            raise ValueError("L'email est obligatoire")
        #Normaliser l'email
        email = self.normalize_email(email)
        #Créer l'objet utilisateur
        user = self.model(email=email, **extra_fields)
        #Hasher le mot de passe, set_password() le transforme en mot de passe hashé.
        user.set_password(password)
        #Sauvegarder et using=self._db indique à Django d'utiliser la connexion de base de données associée au manager.
        user.save(using=self._db)
        #Retourner l'utilisateur
        return user

    #Elle crée le compte administrateur Django
    def create_superuser(self, email, password=None, **extra_fields):
        #Cela indique que le compte peut accéder à l'administration Django.
        extra_fields.setdefault("is_staff", True)
        #Cela donne les permissions administrateur complètes
        extra_fields.setdefault("is_superuser", True)
        #On indique que ce compte possède le rôle ADMIN
        extra_fields.setdefault("role", CustomUser.Role.ADMIN)
        #On réutilise create_user() au lieu de répéter tout le code
        return self.create_user(email, password, **extra_fields)

#Django possède déjà un modèle utilisateur, En héritant de AbstractUser, tu utilises le système d'authentification de Django, mais adapter le modèle utilisateur
class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        RESPONSABLE = "RESPONSABLE", "Responsable"
        AGENT = "AGENT", "Agent"
        ADMIN = "ADMIN", "Administrateur SamaFlot"

    username = None  # on retire le username par défaut, nous ne voulons pas de username
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to="photos_profil/", blank=True, null=True)
    adresse = models.CharField(max_length=255,blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)

    #Le champ utilisé pour identifier l'utilisateur est email
    USERNAME_FIELD = "email"
    #Cette liste indique les champs supplémentaires demandés par createsuperuser
    REQUIRED_FIELDS = []  # email + password suffisent pour createsuperuser

    #Notre manager: CustomUser, utilise un manager personnalisé.
    objects = CustomUserManager()

    #Cela définit comment l'utilisateur sera affiché dans Django
    def __str__(self):
        return f"{self.email} ({self.role})"


class Responsable(models.Model):
    #Un compte utilisateur peut correspondre à un seul Responsable
    utilisateur = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="responsable"
    )
    nom_entreprise = models.CharField(max_length=255)
    statut_compte = models.CharField(
        max_length=20,
        choices=[("ACTIF", "Actif"), ("DESACTIVE", "Désactivé")],
        default="ACTIF",
    )

    def __str__(self):
        return self.nom_entreprise


class Agent(models.Model):
    #Un compte utilisateur peut correspondre à un seul Agent
    utilisateur = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="agent"
    )
    responsable = models.ForeignKey(
        Responsable, on_delete=models.CASCADE, related_name="agents"
    )
    disponible = models.BooleanField(default=True)

    numero_permis = models.CharField(max_length=100, blank=True, null=True)

    categorie_permis = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.utilisateur.email
