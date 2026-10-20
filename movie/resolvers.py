import os
import json
import requests
from flask import request
from flask_jwt_extended import get_jwt

SCHEDULE_URL = os.getenv("SCHEDULE_URL", "http://127.0.0.1:3202")
BOOKING_GRAPHQL_URL = os.getenv(
    "BOOKING_GRAPHQL_URL", "http://127.0.0.1:3201/graphql")
FORBIDDEN = {"success": False, "message": "Accès refusé."}


def is_admin():
    # get_jwt() renvoie {} si aucun token n'a été fourni
    return get_jwt().get("admin", False)


def auth_header():
    # On transmet le token de l'appelant aux autres services
    return {"Authorization": request.headers.get("Authorization", "")}


def all_movies(_, info):
    with open('{}/data/movies.json'.format("."), "r") as file:
        return json.load(file)['movies']


def movie_with_title(_, info, _title):
    with open('{}/data/movies.json'.format("."), "r") as file:
        movies = json.load(file)
    for movie in movies['movies']:
        if movie['title'].lower() == _title.lower():
            return movie


def all_actors(_, info):
    with open('{}/data/actors.json'.format("."), "r") as file:
        return json.load(file)['actors']


def actor_with_id(_, info, _id):
    with open('{}/data/actors.json'.format("."), "r") as file:
        actors = json.load(file)
    for actor in actors['actors']:
        if actor['id'] == _id:
            return actor


def movie_with_id(_, info, _id):
    with open('{}/data/movies.json'.format("."), "r") as file:
        movies = json.load(file)
        for movie in movies['movies']:
            if movie['id'] == _id:
                return movie


def update_rate(_, info, _id, _rate):
    if not is_admin():
        raise Exception("forbidden")
    newmovie = None
    with open('{}/data/movies.json'.format("."), "r") as rfile:
        movies = json.load(rfile)
        for movie in movies['movies']:
            if movie['id'] == _id:
                movie['rating'] = _rate
                newmovie = movie
    # On n'écrit que si le film existe, sinon on écraserait le fichier
    if newmovie is None:
        return None
    with open('{}/data/movies.json'.format("."), "w") as wfile:
        json.dump(movies, wfile, indent=2)
    return newmovie


def resolve_actors_in_movie(movie, info):
    with open('{}/data/actors.json'.format("."), "r") as file:
        actors = json.load(file)
        result = [actor for actor in actors['actors']
                  if movie['id'] in actor['films']]
        return result


def add_movie(_, info, _id, title, director, rating):
    if not is_admin():
        return FORBIDDEN
    path = "./data/movies.json"
    with open(path, "r") as file:
        data = json.load(file)

    # On vérifie que le film n'existe pas déjà
    if any(movie["id"] == _id for movie in data["movies"]):
        return {"success": False,
                "message": f"Le film d'identifiant {_id} existe déjà."}

    data["movies"].append({"director": director, "id": _id,
                           "rating": rating, "title": title})
    # Sauvegarde uniquement après toutes les vérifications
    with open(path, "w") as file:
        json.dump(data, file, indent=2)

    return {"success": True,
            "message": f"Le film {title} a été ajouté avec succès."}


def add_actors(_, info, id, firstname, lastname, birthyear, films):
    if not is_admin():
        return FORBIDDEN
    movies_path = "./data/movies.json"
    actors_path = "./data/actors.json"
    # films est optionnel dans le schéma
    films = films or []

    # 1. Vérifier que tous les films existent dans movies.json
    with open(movies_path, "r") as file:
        movies = json.load(file)["movies"]
    movie_ids = {movie["id"] for movie in movies}
    unknown_films = [film for film in films if film not in movie_ids]
    if unknown_films:
        return {"success": False,
                "message": "Film(s) inconnu(s) : {}."
                .format(", ".join(unknown_films))}

    # 2. Vérifier que l'acteur n'existe pas déjà
    with open(actors_path, "r") as file:
        data = json.load(file)
    if any(actor["id"] == id for actor in data["actors"]):
        return {"success": False,
                "message": "L'acteur d'identifiant {} existe déjà."
                .format(id)}

    # 3. Ajouter l'acteur et sauvegarder
    data["actors"].append({
        "id": id,
        "firstname": firstname,
        "lastname": lastname,
        "birthyear": birthyear,
        "films": films,
    })
    with open(actors_path, "w") as file:
        json.dump(data, file, indent=2)

    return {"success": True,
            "message": "L'acteur {} {} a été ajouté avec succès."
            .format(firstname, lastname)}


def delete_movie(_, info, _id):
    if not is_admin():
        return FORBIDDEN
    movies_path = "./data/movies.json"
    actors_path = "./data/actors.json"

    with open(movies_path, "r") as file:
        movies_data = json.load(file)

    # Vérifier que le film existe
    if not any(movie["id"] == _id for movie in movies_data["movies"]):
        return {"success": False,
                "message": "Le film {} n'existe pas.".format(_id)}

    # On retire d'abord le film du planning et des bookings ; si un service
    # est injoignable, on ne supprime pas le film pour rester cohérent
    try:
        response = requests.delete(f"{SCHEDULE_URL}/movies/{_id}",
                                   headers=auth_header(), timeout=5)
        # 404 : le film n'était programmé à aucune date
        if response.status_code not in (200, 404):
            return {"success": False,
                    "message": "Le service schedule a refusé la suppression."}
        response = requests.post(
            BOOKING_GRAPHQL_URL,
            json={"query": "mutation ($m: String!) { "
                  "delete_movie_everywhere(movie: $m) { success message } }",
                  "variables": {"m": _id}},
            headers=auth_header(), timeout=5)
        result = response.json().get("data") or {}
        if not (result.get("delete_movie_everywhere") or {}).get("success"):
            return {"success": False,
                    "message": "Le service booking a refusé la suppression."}
    except (requests.RequestException, ValueError):
        return {"success": False,
                "message": "Service schedule ou booking injoignable."}

    # Supprimer le film de movies.json
    movies_data["movies"] = [
        movie for movie in movies_data["movies"] if movie["id"] != _id]
    with open(movies_path, "w") as file:
        json.dump(movies_data, file, indent=2)

    # Retirer l'identifiant du film de la liste "films" de chaque acteur
    with open(actors_path, "r") as file:
        actors_data = json.load(file)

    for actor in actors_data["actors"]:
        actor["films"] = [film for film in actor["films"] if film != _id]
    with open(actors_path, "w") as file:
        json.dump(actors_data, file, indent=2)

    return {"success": True,
            "message": "Le film {} a été supprimé.".format(_id)}


def delete_actor(_, info, _id):
    # Supprime un acteur
    if not is_admin():
        return FORBIDDEN
    actors_path = "./data/actors.json"
    with open(actors_path, "r") as file:
        actors_data = json.load(file)
    previous = len(actors_data["actors"])
    # On garde tous les acteurs sauf celui à supprimer
    actors_data["actors"] = [
        actor for actor in actors_data["actors"] if actor["id"] != _id]
    # Si ça n'a pas retiré d'acteur, c'est que celui-ci n'était pas dans la db
    if len(actors_data["actors"]) == previous:
        return {"success": False,
                "message": "L'acteur {} n'a pas été trouvé.".format(_id)}
    # On écrase le fichier avec la liste des acteurs sans celui à supprimer
    with open(actors_path, "w") as file:
        json.dump(actors_data, file, indent=2)
    return {"success": True,
            "message": "L'acteur {} a été supprimé.".format(_id)}
