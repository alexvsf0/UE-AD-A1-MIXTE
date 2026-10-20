import os
import json
# soucis avec requests alors que requeststs est bien dans les requirements.
import requests

SCHEDULE_URL = os.getenv("SCHEDULE_URL", "http://127.0.0.1:3202")
MOVIE_GRAPHQL_URL = os.getenv(
    "MOVIE_GRAPHQL_URL", "http://127.0.0.1:3001/graphql")
MOVIE_QUERY = """
query ($id: String!) {
    movie_with_id(_id: $id) {
        id
        title
        director
        rating
        actors {
            id
            firstname
            lastname
            birthyear
            films
        }
    }
}
"""


# RESOLVEUR de la requête
def booking_with_id(_, info, _id):
    with open("./data/bookings.json", "r") as file:
        bookings = json.load(file)["bookings"]

        for booking in bookings:
            if booking["userid"] == _id:
                return booking

        raise Exception("User ID not found")


def delete_with_id(_, info, _id):
    with open('{}/data/bookings.json'.format("."), "r") as file:
        bookings = json.load(file)

    before = len(bookings["bookings"])
    bookings["bookings"] = [
        b for b in bookings["bookings"] if b["userid"] != _id]

    if len(bookings["bookings"]) == before:
        return {"success": False,
                "message": "Aucun booking trouvé pour {}.".format(_id)}

    with open('{}/data/bookings.json'.format("."), "w") as file:
        json.dump(bookings, file, indent=2)
    return {"success": True,
            "message": "Le booking de {} a été supprimé.".format(_id)}


def delete_date_with_id(_, info, _id, date):
    with open('{}/data/bookings.json'.format("."), "r") as file:
        bookings = json.load(file)
    indice_user = -1
    for i in range(len(bookings["bookings"])):
        if bookings["bookings"][i]["userid"] == _id:
            indice_user = i
            before = len(bookings["bookings"][i]["dates"])
            bookings["bookings"][i]["dates"] = [
                b for b in bookings["bookings"][i]["dates"]
                if b["date"] != date]
    if indice_user == -1:
        return {"success": False,
                "message": "Aucun booking trouvé pour {}.".format(_id)}
    if len(bookings["bookings"][indice_user]["dates"]) == before:
        return {"success": False,
                "message": "Aucun booking à la date du {} trouvé pour {}."
                .format(date, _id)}

    with open('{}/data/bookings.json'.format("."), "w") as file:
        json.dump(bookings, file, indent=2)
    return {"success": True,
            "message": "Le booking de {} a la date du {} a été supprimé."
            .format(_id, date)}


def delete_movie_with_id_and_date(_, info, _id, date, movie):
    with open('{}/data/bookings.json'.format("."), "r") as file:
        bookings = json.load(file)
    indice_user = -1
    indice_date = -1
    for i in range(len(bookings["bookings"])):
        if bookings["bookings"][i]["userid"] == _id:
            indice_user = i
            for j in range(len(bookings["bookings"][i]["dates"])):
                if bookings["bookings"][i]["dates"][j]["date"] == date:
                    indice_date = j
                    movies = bookings["bookings"][i]["dates"][j]["movies"]
                    before = len(movies)
                    bookings["bookings"][i]["dates"][j]["movies"] = [
                        b for b in movies if b != movie]
    if indice_user == -1:
        return {"success": False,
                "message": "Aucun booking trouvé pour {}.".format(_id)}
    if indice_date == -1:
        return {"success": False,
                "message": "Aucun booking à la date du {} trouvé pour {}."
                .format(date, _id)}
    user_dates = bookings["bookings"][indice_user]["dates"]
    if len(user_dates[indice_date]["movies"]) == before:
        return {"success": False,
                "message": "Aucun booking du film {} à la date du {} trouvé "
                "pour {}.".format(movie, date, _id)}

    with open('{}/data/bookings.json'.format("."), "w") as file:
        json.dump(bookings, file, indent=2)
    return {"success": True,
            "message": "Le booking de {} a la date du {} pour le film {} "
            "a été supprimé.".format(_id, date, movie)}


# RESOLVER du type Date dans Booking
def resolve_bookings_date(booking, info):
    # dates est déjà dans booking donc :
    return booking['dates']


def add_booking(_, info, userid, date, movieid):
    path = "./data/bookings.json"
    try:
        response = requests.get(f"{SCHEDULE_URL}/dates/{date}", timeout=5)
    except requests.RequestException:
        return {"success": False, "message": "Service schedule injoignable."}

    if response.status_code != 200 or str(movieid) not in [
            str(m) for m in response.json().get("movies", [])]:
        return {"success": False,
                "message": f"Le film {movieid} n'est pas programmé le {date}."}

    with open(path, "r") as file:
        bookings = json.load(file)

    # On cherche l'utilisateur, sinon on crée son entrée
    booking = next(
        (b for b in bookings["bookings"] if b["userid"] == userid), None)
    if booking is None:
        booking = {"userid": userid, "dates": []}
        bookings["bookings"].append(booking)

    # On cherche la date, sinon on l'ajoute avec le film
    entry = next((d for d in booking["dates"] if d["date"] == date), None)
    if entry is None:
        booking["dates"].append({"date": date, "movies": [movieid]})
    elif movieid in entry["movies"]:
        return {"success": False,
                "message": f"Le film {movieid} est déjà réservé le {date}."}
    else:
        entry["movies"].append(movieid)

    # Sauvegarde uniquement après toutes les vérifications
    with open(path, "w") as file:
        json.dump(bookings, file, indent=2)

    return {"success": True,
            "message": f"Le film {movieid} est réservé le {date} "
            f"pour {userid}."}


# Liaison avec les données stockées par le service movie.
def resolve_date_movies(date, info):
    movies_detail = []
    for movie_id in date["movies"]:
        try:
            response = requests.post(
                MOVIE_GRAPHQL_URL,
                json={"query": MOVIE_QUERY, "variables": {"id": movie_id}},
                timeout=5,
            )
        except requests.exceptions.RequestException:
            raise Exception("movie service unavailable")

        payload = response.json()
        if response.status_code != 200 or payload.get("errors"):
            raise Exception(f"invalid movie: {movie_id}")

        movie = payload["data"]["movie_with_id"]
        if movie is None:
            raise Exception(f"invalid movie: {movie_id}")

        movies_detail.append(movie)
    return movies_detail
