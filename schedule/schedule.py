from flask import Flask, jsonify, make_response
import json
import sys
from werkzeug.exceptions import NotFound
from pymongo import MongoClient
from bson.json_util import dumps
from flask_jwt_extended import create_access_token, get_jwt, JWTManager, jwt_required

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "super-secret"
jwt = JWTManager(app)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_COOKIE_SECURE"] = False

PORT = 3202
HOST = '0.0.0.0'
client = MongoClient("mongodb://root:example@localhost:27017/")

with open('{}/data/times.json'.format("."), "r") as jsf:
    schedule = json.load(jsf)["schedule"]

db = client["schedule"]
collection = db["schedule"]
if collection.count_documents({}) == 0:
    print("Creating collection")
    collection.insert_many(schedule)

@app.route("/", methods=['GET'])
def home():
    return "<h1 style='color:blue'>Welcome to the Showtime service!</h1>"


@app.route("/json", methods=["GET"])
def get_json():
    #Renvoie la liste des films
    mylist = list(collection.find({},  {"_id": 0}))
    res = make_response(jsonify(mylist), 200)
    return res


@app.route("/dates/<date>", methods=["GET"])
def get_movies_by_date(date):
    # TODO : Aller chercher le nom du film à afficher plutôt que l'ID
    # Cherche la première entrée qui correspond à la date
    mylist = collection.find_one({"date": date},  {"_id": 0,"date": 0})
    if mylist!=None:
        res = make_response(jsonify(mylist), 200)
        return res
    return make_response(jsonify({"error": "Date not found"}), 404)


@app.route("/movies/<movieid>", methods=["GET"])
def get_dates_by_movieid(movieid):
    # On teste si movieid est dans la liste 'movies' et on récupère la date
    mylist = list(collection.find({"movies": movieid},  {"_id": 0, "movies":0}))
    print(mylist)
    if mylist!=[]:
        res = make_response(jsonify(mylist), 200)
        return res
    return make_response(jsonify({"error": "Movie not found"}), 404)

@app.route("/movies/<date>/<movieid>", methods=["POST"])
@jwt_required()
def create_movie(date, movieid):
    #Vérifie si le film existe déjà à cette date, sinon l'ajoute, réservé aux admins
    if not get_jwt().get("admin", False):
           return make_response(jsonify({"error" : "forbidden"}), 403)
    movie=collection.find_one({"date":date,"movies":movieid})
    if movie is not None :
        return make_response(jsonify({"error": "Movie already exist"}), 409)
    collection.update_one({"date": date}, {"$addToSet": {"movies": movieid}},upsert=True)
    res = make_response(jsonify({"message": "done"}), 201)
    return res


@app.route("/movies/<movieid>", methods=["DELETE"])
@jwt_required()
def del_movie_by_id(movieid):
    #Supprime un film de toutes les dates où il est proposé, réservé aux admins
    if not get_jwt().get("admin", False):
       return make_response(jsonify({"error" : "forbidden"}), 403)
    mylist = list(collection.find({"movies": movieid}))
    if mylist==[]:
            return make_response(jsonify({"error": "Movie ID not found"}), 404)
    collection.update_many(
        {"movies": movieid},
        {"$pull": {"movies": movieid}},
    )
    return make_response(jsonify({"message": "done"}), 200)
    
@app.route("/movies/<date>/<movieid>", methods=["DELETE"])
@jwt_required()
def del_movie_at_one_date(date, movieid):
    #Supprime un film de à une date fixée, réservé aux admins
    if not get_jwt().get("admin", False):
       return make_response(jsonify({"error" : "forbidden"}), 403)
    movie=collection.find_one({"date": date, "movies": movieid})
    if movie is None:
            return make_response(jsonify({"error": "Movie ID not found at this date"}), 404)
    collection.update_one({"date": date}, {"$pull": {"movies": movieid}})
    return make_response(jsonify({"message": "done"}), 200)

@app.route("/dates/<date>", methods=["DELETE"])
@jwt_required()
def del_movies_by_date(date):
    #Supprime tous les films à une date, réservé aux admins
    if not get_jwt().get("admin", False):
       return make_response(jsonify({"error" : "forbidden"}), 403)
    mylist = collection.find_one({"date": date})
    if mylist==None:
            return make_response(jsonify({"error": "Date not found"}), 404)
    collection.delete_one({"date": date})
    return make_response(jsonify({"message": "done"}), 200)


if __name__ == "__main__":
    print("Server running in port %s" % (PORT))
    app.run(host=HOST, port=PORT)
