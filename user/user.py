import os
from flask import Flask, render_template, request, jsonify, make_response
import requests
import json
from werkzeug.exceptions import NotFound
from flask_jwt_extended import create_access_token, get_jwt_identity, JWTManager, jwt_required

app = Flask(__name__)

PORT = 3203
HOST = '0.0.0.0'

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super-secret")
jwt = JWTManager(app)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_COOKIE_SECURE"] = False

with open('{}/data/users.json'.format("."), "r") as jsf:
   users = json.load(jsf)["users"]

@app.route("/login", methods=['POST'])
def login():
   #On récupère le nom de l'utilisateur et on récupère son compte
   if request.args:
      req = request.args
      name = req["name"]
      user=[user for user in users if user["name"]==name]
      if not user:
         return (make_response("error : user not found", 404))
      user=user[0]
      additionnal_claim={"admin":user["admin"]} #On va créer un token avec le statut admin de l'utilisateur pour les autres services qui n'ont pas accès à cette database
      token = create_access_token(identity=name, additional_claims=additionnal_claim)
      return jsonify(access_token=token)
   return(jsonify("fail"))

def write(users):
    with open("{}/data/users.json".format("."), "w") as f:
        full = {}
        full["users"] = users
        json.dump(full, f)

def is_admin(username):
   user = [user for user in users if user["name"]==username]
   if user:
      return(user[0]["admin"])
   return(False)

def get_id(username):
   user = [user for user in users if user["name"]==username]
   if user:
      return(user[0]["id"])
   return(False)

@app.route("/", methods=['GET'])
def home():
   return "<h1 style='color:blue'>Welcome to the User service!</h1>"

@app.route("/json", methods=["GET"])
@jwt_required()
def get_json():
    #Renvoie la liste des utilisateurs avec toutes les infos, réservé aux admins
    current_user = get_jwt_identity()
    if not is_admin(current_user):
       return make_response(jsonify({"error" : "forbidden"}), 403)
    res = make_response(jsonify(users), 200)
    return res

@app.route("/user/<user_id>", methods=["GET"])
@jwt_required()
def get_user_id(user_id):
    #Renvoie les infos d'un utilisateur, réservé à l'utilisateur ou aux admins
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id==get_id(current_user)):
       return(make_response(jsonify({"error" : "forbidden"}), 403))
    for user in users :
       if user_id==str(user["id"]):
          return (make_response(jsonify(user), 200))
    return (make_response(jsonify({"error" : "Not found"}), 404))

@app.route("/user/admin", methods=["GET"])
@jwt_required()
def get_admin():
    #Renvoie la liste des admins, réservé aux admins
    current_user = get_jwt_identity()
    if not is_admin(current_user):
       return(make_response(jsonify({"error" : "forbidden"}), 403))
    for user in users :
       rep = [user for user in users if user["admin"]]
       return (make_response(jsonify(rep), 200))
    return (make_response(jsonify({"error" : "Not found"}), 404))

@app.route("/user/<user_id>", methods=["POST"])
@jwt_required(optional=True)
def create_user(user_id):
    #Créer un compte, nécessite d'être admin pour créer un compte administrateur
    current_user = get_jwt_identity()
    for user in users :
       if user_id==str(user["id"]):
          return (make_response(jsonify({"error": "user ID already exists"}), 500))
    req = request.get_json()
    if req["admin"] and not is_admin(current_user):
       return (make_response(jsonify({"error" : "forbidden"}), 403))
    users.append(req)
    write(users)
    return (make_response(jsonify(req), 200))

@app.route("/user/<user_id>", methods=["PUT"])
@jwt_required()
def modify_user(user_id):
    #Modifie un compte, réservé à l'utilisateur ou aux admins
    current_user = get_jwt_identity()
    user_exist=False
    req = request.get_json()
    if req["admin"] and not is_admin(current_user):
      return (make_response(jsonify({"error" : "forbidden"}), 403))
    for i in range (len(users)) :
       if user_id==str(users[i]["id"]):
          users[i] = req
          users[i]["id"]=user_id
          user_exist=True
    if not user_exist : 
       return (make_response(jsonify({"error" : "user not found"}), 404))
    write(users)
    return (make_response(jsonify(req), 200))

@app.route("/user/<user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    #Supprime un compte, réservé à l'utilisateur ou aux admins
    current_user = get_jwt_identity()
    if not (is_admin(current_user) or user_id==current_user):
       return(make_response(jsonify({"error" : "forbidden"}), 403))
    for user in users :
       if user_id==str(user["id"]):
          users.remove(user)
          write(users)
          return (make_response("succesfully deleted"),204)
    return (make_response(jsonify({"error" : "user not found"}), 404))

if __name__ == "__main__":
   print("Server running in port %s"%(PORT))
   app.run(host=HOST, port=PORT)
