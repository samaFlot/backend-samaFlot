# On importe le système d'administration de Django
from django.contrib import admin
#on récupère la configuration d'administration fournie par Django pour les utilisateurs
from django.contrib.auth.admin import UserAdmin
#On importe nos trois modèles
from .models import CustomUser, Responsable, Agent

#On crée une nouvelle configuration admin pour notre CustomUser car UserAdmin de Django est prévu pour le modèle User standard
class CustomUserAdmin(UserAdmin):
    #Cette configuration d'administration concerne le modèle CustomUser
    model = CustomUser
    #les colonnes affichées dans la liste des utilisateurs
    list_display = ("email", "role", "is_staff", "is_active")
    #Trie les utilisateurs par email
    ordering = ("email",)

    #CCela organise les champs lorsque tu ouvres un utilisateur déjà créé dans /admin/
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations", {"fields": ("first_name", "last_name", "telephone", "photo", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    #add_fieldsets intervient lorsque tu cliques sur Ajouter un utilisateur
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role", "is_staff", "is_superuser"),
        }),
    )


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Responsable)
admin.site.register(Agent)
