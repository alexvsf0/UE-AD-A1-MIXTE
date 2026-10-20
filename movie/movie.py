from ariadne import (graphql_sync, make_executable_schema,
                     load_schema_from_path, ObjectType, QueryType,
                     MutationType)
import os
from flask import Flask, request, jsonify, make_response
from flask_jwt_extended import JWTManager, jwt_required
import resolvers as r

PORT = 3001
HOST = '0.0.0.0'
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv(
    "JWT_SECRET_KEY", "super-secret-dev-key-change-me-in-production")
jwt = JWTManager(app)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]

# todo create elements for Ariadne
type_defs = load_schema_from_path("movie.graphql")
query = QueryType()
mutation = MutationType()
movie = ObjectType("Movie")
query.set_field('movie_with_id', r.movie_with_id)
query.set_field('movies', r.all_movies)
query.set_field('movie_with_title', r.movie_with_title)
query.set_field('actor_with_id', r.actor_with_id)
query.set_field('actors', r.all_actors)
mutation.set_field('update_movie_rate', r.update_rate)
mutation.set_field('add_movie', r.add_movie)
mutation.set_field('add_actors', r.add_actors)
mutation.set_field('delete_movie', r.delete_movie)
mutation.set_field('delete_actor', r.delete_actor)
movie.set_field('actors', r.resolve_actors_in_movie)
schema = make_executable_schema(type_defs, movie, query, mutation)


# root message
@app.route("/", methods=['GET'])
def home():
    return make_response(
        "<h1 style='color:blue'>Welcome to the Movie service!</h1>", 200)


# graphql entry points, les lectures sont publiques, les mutations
# vérifient le statut admin du token
@app.route('/graphql', methods=['POST'])
@jwt_required(optional=True)
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(
        schema,
        data,
        context_value=None,
        debug=app.debug
    )
    status_code = 200 if success else 400
    return jsonify(result), status_code


if __name__ == "__main__":
    print("Server running in port %s" % (PORT))
    app.run(host=HOST, port=PORT)
