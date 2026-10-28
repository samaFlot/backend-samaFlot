import os
import requests
from .services import (
    preparer_donnees_pour_ia,
    recuperer_ressources_admissibles,
)
import json

from django.utils import timezone

from flotte.models import Vehicule


def construire_prompt(donnees):
    prompt = f"""
    Tu es un assistant intelligent de gestion de flotte pour SamaFlott.

    Ton rôle est d'analyser une demande de chargement et les ressources
    admissibles fournies par le système afin de proposer les meilleures
    associations entre véhicules et agents.

    Tu ne crées jamais de mission.
    Tu ne modifies jamais les données.
    La décision finale appartient au responsable de flotte.

    RÈGLES :

    - Utilise uniquement les véhicules et agents fournis.
    - Ne crée jamais de nouvel ID.
    - Ne propose pas une ressource qui ne figure pas dans les données reçues.
    - Un véhicule doit être associé à un seul agent dans une proposition.
    - Un agent ne doit pas être associé à plusieurs véhicules dans la même réponse.
    - Le nombre de propositions ne doit pas dépasser le nombre de véhicules demandés.
    - Ne vérifie pas la catégorie de permis par rapport au véhicule.
    - Ne déduis pas de nouvelles règles réglementaires.
    - Les ressources reçues ont déjà été contrôlées par le backend.
    - Ton rôle est de recommander, pas de décider.

    CRITÈRES DE RECOMMANDATION :

    - Privilégie les associations cohérentes avec la demande.
    - Privilégie les véhicules dont les caractéristiques correspondent
    le mieux aux besoins de la demande.
    - Lorsque plusieurs véhicules sont demandés, propose plusieurs
    associations différentes si suffisamment de ressources sont disponibles.

    DONNÉES DE LA DEMANDE :

    {donnees["demande"]}

    VÉHICULES ADMISSIBLES :

    {donnees["vehicules"]}

    AGENTS ADMISSIBLES :

    {donnees["agents"]}

    FORMAT DE RÉPONSE OBLIGATOIRE :

    {{
        "propositions": [
            {{
                "vehicule_id": 0,
                "agent_id": 0,
                "score": 0,
                "raison": "..."
            }}
        ]
    }}

    CONTRAINTES :

    - vehicule_id doit correspondre à un véhicule fourni.
    - agent_id doit correspondre à un agent fourni.
    - score doit être un entier entre 0 et 100.
    - raison doit être courte et claire.
    - Retourne uniquement un objet JSON valide.
    - Ne mets aucun texte avant ou après le JSON.
    - N'utilise jamais de balises Markdown comme ```json ou ```.
    """

    return prompt


def appeler_openrouter(prompt):
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("La clé API OpenRouter n'est pas configurée.")

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


def obtenir_propositions_ia(demande):

    # Récupérer les ressources pouvant être proposées
    ressources = recuperer_ressources_admissibles(demande)

    vehicules = ressources["vehicules"]
    agents = ressources["agents"]

    # ---------------------------------------------------------
    # VÉRIFIER LES RESSOURCES AVANT D'APPELER L'IA
    # ---------------------------------------------------------

    if not vehicules and not agents:
        return {
            "propositions": [],
            "message": (
                "Aucun véhicule ni agent n’est actuellement "
                "disponible pour cette demande."
            ),
        }

    if not vehicules:
        return {
            "propositions": [],
            "message": (
                "Aucun véhicule n’est actuellement disponible "
                "pour cette demande."
            ),
        }

    if not agents:
        return {
            "propositions": [],
            "message": (
                "Aucun agent n’est actuellement disponible "
                "pour cette demande."
            ),
        }


    # Préparer les informations de la demande,
    # ainsi que les véhicules et agents admissibles
    donnees = preparer_donnees_pour_ia(demande, ressources)

    # Récupérer les objets Django correspondants
    # aux ressources admissibles.
    #ressources = recuperer_ressources_admissibles(demande)

    # Construire le prompt qui sera envoyé à l'IA
    prompt = construire_prompt(donnees)

    # Envoyer le prompt à OpenRouter
    # et récupérer la réponse de l'IA
    reponse = appeler_openrouter(prompt)

    print("========== REPONSE IA ==========")
    print(reponse)
    print("================================")

    # Transformer la réponse de l'IA en objet Python
    try:
        resultat = json.loads(reponse)

    except json.JSONDecodeError:
        raise ValueError(
            "La réponse de l'IA n'est pas un JSON valide."
        )

    # Récupérer les propositions
    propositions = resultat.get("propositions", [])

    if not isinstance(propositions, list):
        raise ValueError(
            "Le format des propositions est invalide."
        )

    # Créer des dictionnaires pour retrouver
    # facilement un véhicule ou un agent par son ID.
    vehicules = {
        vehicule.id: vehicule
        for vehicule in ressources["vehicules"]
    }

    agents = {
        agent.id: agent
        for agent in ressources["agents"]
    }

    propositions_valides = []

    for proposition in propositions:

        vehicule_id = proposition.get("vehicule_id")
        agent_id = proposition.get("agent_id")

        # Vérifier que les IDs existent réellement
        # parmi les ressources admissibles.
        if vehicule_id not in vehicules:
            continue

        if agent_id not in agents:
            continue

        # Un véhicule ne peut apparaître
        # qu'une seule fois.
        if any(
            p["vehicule"]["id"] == vehicule_id
            for p in propositions_valides
        ):
            continue

        # Un agent ne peut être associé
        # qu'à un seul véhicule.
        if any(
            p["agent"]["id"] == agent_id
            for p in propositions_valides
        ):
            continue

        vehicule = vehicules[vehicule_id]
        agent = agents[agent_id]

        propositions_valides.append({
            "vehicule": {
                "id": vehicule.id,
                "immatriculation": vehicule.immatriculation,
                "type_vehicule": vehicule.type_vehicule,
                "poids": float(vehicule.poids),
                "hauteur": float(vehicule.hauteur),
                "largeur": float(vehicule.largeur),
            },

            "agent": {
                "id": agent.id,
                "prenom": agent.utilisateur.first_name,
                "nom": agent.utilisateur.last_name,
                "telephone": agent.utilisateur.telephone,
                "photo": (
                    agent.utilisateur.photo.url
                    if agent.utilisateur.photo
                    else None
                ),
                "categorie_permis": agent.categorie_permis,
                "date_expiration_permis": str(
                    agent.date_expiration_permis
                ),
            },

            "score": int(
                proposition.get("score", 0)
            ),

            "raison": proposition.get(
                "raison",
                "Association recommandée par l'IA."
            ),

            "criteres": {
                "vehicule_disponible": (
                    vehicule.statut
                    == Vehicule.Statut.DISPONIBLE
                ),

                "agent_disponible": agent.disponible,

                "bon_etat_technique": (
                    vehicule.etat_technique
                    == Vehicule.EtatTechnique.BON_ETAT
                ),

                "permis_valide": agent.permis_valide,

                "documents_valides": all(
                    document.date_expiration
                    >= timezone.localdate()
                    for document in vehicule.documents.all()
                ),
            },
        })

    # Trier par score décroissant.
    propositions_valides.sort(
        key=lambda proposition: proposition["score"],
        reverse=True
    )

    # Ne pas dépasser le nombre de véhicules demandés.
    nombre_max = demande.nombre_vehicules_demandes

    propositions_valides = propositions_valides[:nombre_max]

    message = None

    nombre_demande = demande.nombre_vehicules_demandes
    nombre_propositions = len(propositions_valides)

    if nombre_propositions == 0:
        message = (
            "Aucune association entre un véhicule et un agent "
            "n’a pu être proposée pour cette demande."
        )
    elif nombre_propositions < nombre_demande:

        nombre_vehicules = len(ressources["vehicules"])
        nombre_agents = len(ressources["agents"])

        if nombre_agents < nombre_demande:
            if nombre_agents == 1:
                message = (
                    "Une seule affectation est actuellement possible "
                    "car un seul agent est disponible pour cette demande."
                )
            else:
                message = (
                    f"{nombre_agents} affectations sont actuellement possibles "
                    f"car seuls {nombre_agents} agents sont disponibles."
                )

        elif nombre_vehicules < nombre_demande:

            if nombre_vehicules == 1:
                message = (
                    "Une seule affectation est actuellement possible "
                    "car un seul véhicule est disponible pour cette demande."
                )
            else:
                message = (
                    f"{nombre_vehicules} affectations sont actuellement possibles "
                    f"car seuls {nombre_vehicules} véhicules sont disponibles."
                )

        else:

            if nombre_propositions == 1:
                message = (
                    "Une seule affectation est actuellement possible "
                    "avec les ressources disponibles."
                )
            else:
                message = (
                    f"{nombre_propositions} affectations sont actuellement possibles "
                    "avec les ressources disponibles."
                )


    return {
        "propositions": propositions_valides,
        "message": message,
    }
