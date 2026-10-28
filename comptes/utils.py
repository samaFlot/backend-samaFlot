# comptes/utils.py
#Le module secrets sert à générer des valeurs aléatoires et difficiles à deviner.
import secrets
#string nous donne des ensembles de caractères déjà prêts.
import string
#Django fournit déjà une fonction appelée send_mail() pour envoyer un email.
from django.core.mail import send_mail
#Cela permet d'accéder aux paramètres définis dans settings
from django.conf import settings

#par défaut, le mot de passe aura 10 caractères.
def generer_mot_de_passe(longueur=10):
    #On construit l'ensemble des caractères autorisé: notre mot de passe peut contenir des lettres et des lettres
    alphabet = string.ascii_letters + string.digits
    #on génére le mot de passe et on le retourne
    #on choisit un caractère aléatoire dans alphabet et on le repete 10 fois et _ signifie qu'on a pas besoin de connaitre le numéro de l'itération
    return "".join(secrets.choice(alphabet) for _ in range(longueur))

#is_reset=False signifie par défaut : on considère qu'il s'agit de la création d'un compte
#Cela permet d'utiliser la même fonction pour deux situations
def envoyer_identifiants(email, prenom, mot_de_passe, is_reset=False):
    sujet = "Réinitialisation de votre accès SamaFlot" if is_reset else "Bienvenue sur SamaFlot"
    corps = (
        f"Bonjour {prenom},\n\n"
        f"{'Votre accès a été réinitialisé.' if is_reset else 'Votre compte SamaFlot a été créé.'}\n\n"
        f"Email : {email}\n"
        f"Mot de passe : {mot_de_passe}\n\n"
        f"Connectez-vous pour accéder à votre espace."
    )
    send_mail(sujet, corps, settings.DEFAULT_FROM_EMAIL, [email])