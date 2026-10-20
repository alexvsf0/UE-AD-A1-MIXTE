import os
from flask import Flask, request, jsonify, make_response
import json
import requests
from flask_jwt_extended import (create_access_token, get_jwt_identity,
                                JWTManager, jwt_required)

app = Flask(__name__)

PORT = 3203
HOST = '0.0.0.0'
BOOKING_GRAPHQL_URL = os.getenv(
    "BOOKING_GRAPHQL_URL", "http://127.0.0.1:3201/graphql")
BOOKING_FIELDS = """
    userid
    dates {
        date
        movies { id title director rating }
    }
"""

app.config["JWT_SECRET_KEY"] = os.getenv(
    "JWT_SECRET_KEY", "super-secret-dev-key-change-me-in-production")
jwt = JWTManager(app)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_COOKIE_SECURE"] = False

with open('{}/data/users.json'.format("."), "r") as jsf:
    users = json.load(jsf)["users"]


@app.route("/login", methods=['POST'])
def login():
    # On récupère le nom de l'utilisateur et on récupère son compte
    if request.args:
        req = request.args
        name = req["name"]
        user = [user for user in users if user["name"] == name]
        if not user:
            return (make_response("error : user not found", 404))
        user = user[0]
        # On va créer un token avec le statut admin de l'utilisateur pour les
        # autres services qui n'ont pas accès à cette database
        additionnal_claim = {"admin": user["admin"]}
        # L'identité du token est l'id (stable), pas le nom (modifiable)
        token = create_access_token(
            identity=user["id"], additional_claims=additionnal_claim)
        return jsonify(access_token=token)
    return (make_response(jsonify({"error": "missing name"}), 400))


def write(users):
    with open("{}/data/users.json".format("."), "w") as f:
        full = {}
        full["users"] = users
        json.dump(full, f)


def is_admin(user_id):
    user = [user for user in users if user["id"] == user_id]
    if user:
        return (user[0]["admin"])
    return (False)


def booking_graphql(query, variables):
    # Appelle le service booking avec le token de l'appelant.
    # Renvoie (data, erreur) ; erreur est une réponse Flask prête à renvoyer
    try:
        response = requests.post(
            BOOKING_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": request.headers.get(
                "Authorization", "")},
            timeout=10,
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None, make_response(
            jsonify({"error": "booking service unavailable"}), 503)
    if payload.get("errors") or not payload.get("data"):
        return None, make_response(
            jsonify({"error": payload.get("errors", "booking error")}), 502)
    return payload["data"], None


def mutation_response(result):
    # Traduit un MutationResult du service booking en réponse HTTP
    return make_response(jsonify(result), 200 if result["success"] else 400)


@app.route("/", methods=['GET'])
def home():
    return "<h1 style='color:blue'>Welcome to the User service!</h1>"


@app.route("/json", methods=["GET"])
@jwt_required()
def get_json():
    # Renvoie la liste des utilisateurs avec toutes les infos,
    # réservé aux admins
    current_user = get_jwt_identity()
    if not is_admin(current_user):
        return make_response(jsonify({"error": "forbidden"}), 403)
    res = make_response(jsonify(users), 200)
    return res


@app.route("/user/<user_id>", methods=["GET"])
@jwt_required()
def get_user_id(user_id):
    # Renvoie les infos d'un utilisateur,
    # réservé à l'utilisateur ou aux admins
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id == current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    for user in users:
        if user_id == str(user["id"]):
            return (make_response(jsonify(user), 200))
    return (make_response(jsonify({"error": "Not found"}), 404))


@app.route("/user/admin", methods=["GET"])
@jwt_required()
def get_admin():
    # Renvoie la liste des admins, réservé aux admins
    current_user = get_jwt_identity()
    if not is_admin(current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    rep = [user for user in users if user["admin"]]
    return (make_response(jsonify(rep), 200))


@app.route("/user/<user_id>", methods=["POST"])
@jwt_required(optional=True)
def create_user(user_id):
    # Créer un compte,
    # nécessite d'être admin pour créer un compte administrateur
    current_user = get_jwt_identity()
    for user in users:
        if user_id == str(user["id"]):
            return (make_response(
                jsonify({"error": "user ID already exists"}), 409))
    req = request.get_json(silent=True)
    if not req or "name" not in req:
        return (make_response(jsonify({"error": "name is required"}), 400))
    if any(user["name"] == req["name"] for user in users):
        return (make_response(
            jsonify({"error": "user name already exists"}), 409))
    req["admin"] = bool(req.get("admin", False))
    if req["admin"] and not is_admin(current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    req["id"] = user_id
    users.append(req)
    write(users)
    return (make_response(jsonify(req), 201))


@app.route("/user/<user_id>", methods=["PUT"])
@jwt_required()
def modify_user(user_id):
    # Modifie un compte, réservé à l'utilisateur ou aux admins
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id == current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    user_exist = False
    req = request.get_json(silent=True)
    if not req:
        return (make_response(jsonify({"error": "missing body"}), 400))
    if req.get("admin") and not is_admin(current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    for i in range(len(users)):
        if user_id == str(users[i]["id"]):
            # On complète avec les anciennes valeurs pour ne rien perdre
            users[i] = {**users[i], **req, "id": user_id}
            req = users[i]
            user_exist = True
    if not user_exist:
        return (make_response(jsonify({"error": "user not found"}), 404))
    write(users)
    return (make_response(jsonify(req), 200))


@app.route("/user/<user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    # Supprime un compte, réservé à l'utilisateur ou aux admins
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id == current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    for user in users:
        if user_id == str(user["id"]):
            # On supprime d'abord ses bookings (aucun booking n'est pas une
            # erreur) ; si le service est injoignable, on ne supprime rien
            _, error = booking_graphql(
                "mutation ($id: String!) "
                "{ delete_with_id(_id: $id) { success message } }",
                {"id": user_id})
            if error:
                return error
            users.remove(user)
            write(users)
            return (make_response("", 204))
    return (make_response(jsonify({"error": "user not found"}), 404))


@app.route("/user/<user_id>/bookings", methods=["GET"])
@jwt_required()
def get_user_bookings(user_id):
    # Renvoie les bookings d'un utilisateur avec le détail des films,
    # réservé à l'utilisateur ou aux admins
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id == current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    if not any(user_id == str(user["id"]) for user in users):
        return (make_response(jsonify({"error": "user not found"}), 404))
    data, error = booking_graphql(
        "query ($id: String!) { booking_with_id(_id: $id) {"
        + BOOKING_FIELDS + "} }",
        {"id": user_id})
    if error:
        return error
    booking = data["booking_with_id"] or {"userid": user_id, "dates": []}
    return (make_response(jsonify(booking), 200))


@app.route("/user/<user_id>/bookings", methods=["POST"])
@jwt_required()
def add_user_booking(user_id):
    # Réserve un film pour un utilisateur, body : {"date": ..., "movieid": ...}
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id == current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    req = request.get_json(silent=True) or {}
    if "date" not in req or "movieid" not in req:
        return (make_response(
            jsonify({"error": "date and movieid are required"}), 400))
    data, error = booking_graphql(
        "mutation ($u: String!, $d: String!, $m: String!) "
        "{ add_booking(userid: $u, date: $d, movieid: $m) "
        "{ success message } }",
        {"u": user_id, "d": req["date"], "m": req["movieid"]})
    if error:
        return error
    result = data["add_booking"]
    if result["success"]:
        return make_response(jsonify(result), 201)
    return mutation_response(result)


@app.route("/user/<user_id>/bookings/<date>", methods=["DELETE"])
@jwt_required()
def delete_user_booking_date(user_id, date):
    # Annule toutes les réservations d'un utilisateur à une date
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id == current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    data, error = booking_graphql(
        "mutation ($u: String!, $d: String!) "
        "{ delete_date_with_id(_id: $u, date: $d) { success message } }",
        {"u": user_id, "d": date})
    if error:
        return error
    return mutation_response(data["delete_date_with_id"])


@app.route("/user/<user_id>/bookings/<date>/<movieid>", methods=["DELETE"])
@jwt_required()
def delete_user_booking_movie(user_id, date, movieid):
    # Annule la réservation d'un film à une date pour un utilisateur
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id == current_user):
        return (make_response(jsonify({"error": "forbidden"}), 403))
    data, error = booking_graphql(
        "mutation ($u: String!, $d: String!, $m: String!) "
        "{ delete_movie_with_id_and_date(_id: $u, date: $d, movie: $m) "
        "{ success message } }",
        {"u": user_id, "d": date, "m": movieid})
    if error:
        return error
    return mutation_response(data["delete_movie_with_id_and_date"])


if __name__ == "__main__":
    print("Server running in port %s" % (PORT))
    app.run(host=HOST, port=PORT)
