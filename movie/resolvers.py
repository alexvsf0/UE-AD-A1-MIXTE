import json
import requests

def movie_with_id(_,info,_id):
    with open('{}/data/movies.json'.format("."), "r") as file:
        movies = json.load(file)
        for movie in movies['movies']:
            if movie['id'] == _id:
                return movie
             
def update_rate(_,info,_id,_rate):
    newmovies = {}
    newmovie = {}
    with open('{}/data/movies.json'.format("."), "r") as rfile:
        movies = json.load(rfile)
        for movie in movies['movies']:
            if movie['id'] == _id:
                movie['rating'] = _rate
                newmovie = movie
                newmovies = movies
    with open('{}/data/movies.json'.format("."), "w") as wfile:
        json.dump(newmovies, wfile)
    return newmovie
 
def resolve_actors_in_movie(movie, info):
    with open('{}/data/actors.json'.format("."), "r") as file:
        actors = json.load(file)
        result = [actor for actor in actors['actors'] if movie['id'] in actor['films']]
        return result
    
def add_movie(_, info, _id, title, director, rating):
    path = "./data/movies.json"
    with open(path, "r") as file:
        data = json.load(file)
    
        # On vérifie que le film n'existe pas déjà
        movies = next((movie for movie in data["movies"] if data["id"] == _id), None)
        if movies is None:
            movie = {"director": director, "id": _id, "rating": rating, "title": title}
            movies["movies"].append(movie)
        else : 
            return {"success": False, "message": f"Le film d'identifiant {_id} existe déjà."}
        # Sauvegarde uniquement après toutes les vérifications
        with open(path, "w") as file:
            json.dump(movies, file, indent=2)
    
        return {"success": True, "message": f"Le film {title} a été ajouté avec succès."}
     

def add_actors(_, info, id, firstname, lastname, birthyear, films):
    movies_path = "./data/movies.json"
    actors_path = "./data/actors.json"

    # 1. Vérifier que tous les films existent dans movies.json
    with open(movies_path, "r") as file:
        movies = json.load(file)["movies"]
    movie_ids = {movie["id"] for movie in movies}
    unknown_films = [film for film in films if film not in movie_ids]
    if unknown_films:
        return {"success": False, "message": "Film(s) inconnu(s) : {}.".format(", ".join(unknown_films))}

    # 2. Vérifier que l'acteur n'existe pas déjà
    with open(actors_path, "r") as file:
        data = json.load(file)
    if any(actor["id"] == id for actor in data["actors"]):
        return {"success": False, "message": "L'acteur d'identifiant {} existe déjà.".format(id)}

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

    return {"success": True, "message": "L'acteur {} {} a été ajouté avec succès.".format(firstname, lastname)}

def delete_movie(_, info, _id):
    movies_path = "./data/movies.json"
    actors_path = "./data/actors.json"

    with open(movies_path, "r") as file:
        movies_data = json.load(file)

    # Vérifier que le film existe
    if not any(movie["id"] == _id for movie in movies_data["movies"]):
        return {"success": False, "message": "Le film {} n'existe pas.".format(_id)}

    # Supprimer le film de movies.json
    movies_data["movies"] = [movie for movie in movies_data["movies"] if movie["id"] != _id]
    with open(movies_path, "w") as file:
        json.dump(movies_data, file, indent=2)

    # Retirer l'identifiant du film de la liste "films" de chaque acteur
    with open(actors_path, "r") as file:
        actors_data = json.load(file)

    for actor in actors_data["actors"]:
        actor["films"] = [film for film in actor["films"] if film != _id]
    with open(actors_path, "w") as file:
        json.dump(actors_data, file, indent=2)

    return {"success": True, "message": "Le film {} a été supprimé.".format(_id)}
    