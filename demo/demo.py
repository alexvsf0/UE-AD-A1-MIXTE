"""Démo des services movie, booking, schedule et user.

Raconte un scénario court qui traverse tous les services : connexion par
token, ajout d'un film, programmation, réservation puis suppression en
cascade. Les données créées sont supprimées à la fin.

Usage : python demo/demo.py [-v]   (-v affiche le corps des réponses)
Uniquement la bibliothèque standard, pour tourner dans une image python nue.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

USER_URL = os.getenv("USER_URL", "http://127.0.0.1:3203")
SCHEDULE_URL = os.getenv("SCHEDULE_URL", "http://127.0.0.1:3202")
MOVIE_GRAPHQL_URL = os.getenv(
    "MOVIE_GRAPHQL_URL", "http://127.0.0.1:3001/graphql")
BOOKING_GRAPHQL_URL = os.getenv(
    "BOOKING_GRAPHQL_URL", "http://127.0.0.1:3201/graphql")
ADMIN_NAME = os.getenv("DEMO_ADMIN_NAME", "Chris Rivers")

VERBOSE = "-v" in sys.argv or os.getenv("DEMO_VERBOSE") == "1"
USE_COLOR = bool(os.getenv("FORCE_COLOR")) or (
    sys.stdout.isatty() and not os.getenv("NO_COLOR"))

# Identifiants propres à cette exécution pour ne pas toucher aux vraies données
SUFFIX = str(int(time.time()))[-6:]
DEMO_USER = f"demo_{SUFFIX}"
DEMO_NAME = f"Demo {SUFFIX}"
DEMO_MOVIE = f"demo-movie-{SUFFIX}"
DEMO_DATE = "20990101"

results = {"ok": 0, "ko": 0}
# Rempli au fil du scénario, sert au nettoyage même en cas d'interruption
tokens = {}


def color(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def call(method, url, body=None, token=None, params=None):
    # Renvoie (statut, corps décodé) ; lève URLError si le service est éteint
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        payload = raw.decode(errors="replace").strip()
    return status, payload


def summarize(payload):
    # Résumé d'une ligne d'une réponse REST ou GraphQL
    if isinstance(payload, dict):
        if payload.get("errors"):
            return payload["errors"][0].get("message", "erreur")
        if isinstance(payload.get("data"), dict):
            payload = next(iter(payload["data"].values()), None)
            if isinstance(payload, dict) and "message" in payload:
                return payload["message"]
        elif "message" in payload or "error" in payload:
            return str(payload.get("message") or payload.get("error"))
        elif "access_token" in payload:
            return "token JWT reçu"
    text = json.dumps(payload, ensure_ascii=False) if payload else "(vide)"
    return text if len(text) <= 90 else text[:87] + "..."


def section(title):
    print()
    print(color("1;36", f"━━ {title} " + "━" * max(3, 66 - len(title))))


def step(label, method, url, expect=200, body=None, token=None, params=None,
         check=None):
    # Exécute un appel et affiche une ligne ✔/✘ ; expect=None ignore le statut
    try:
        status, payload = call(method, url, body, token, params)
    except urllib.error.URLError as error:
        status, payload = None, f"injoignable ({error.reason})"
    ok = (expect is None or status == expect)
    if ok and check is not None:
        try:
            ok = bool(check(payload))
        except (KeyError, TypeError, IndexError, AttributeError):
            ok = False
    results["ok" if ok else "ko"] += 1

    mark = color("32", "✔") if ok else color("31", "✘")
    path = urllib.parse.urlparse(url).path
    print(f" {mark} {label}")
    detail = f"{method} {path} → {status} · {summarize(payload)}"
    print(color("2", "     " + detail))
    if VERBOSE and payload is not None:
        dump = json.dumps(payload, indent=2, ensure_ascii=False)
        print(color("2", "\n".join("       " + line
                                   for line in dump.splitlines())))
    return payload


def gql(label, url, query, variables=None, token=None, check=None):
    return step(label, "POST", url, None,
                {"query": query, "variables": variables or {}}, token,
                check=check)


def wait_for_services(timeout=90):
    homes = [USER_URL, SCHEDULE_URL,
             MOVIE_GRAPHQL_URL.rsplit("/graphql", 1)[0],
             BOOKING_GRAPHQL_URL.rsplit("/graphql", 1)[0]]
    deadline = time.time() + timeout
    for url in homes:
        while True:
            try:
                call("GET", url + "/")
                break
            except (urllib.error.URLError, OSError):
                if time.time() > deadline:
                    print(color("31", f"✘ service injoignable : {url}"))
                    sys.exit(1)
                time.sleep(2)
    print(color("2", "services prêts"))


def login(name):
    payload = step(f"{name} se connecte", "POST", USER_URL + "/login",
                   params={"name": name},
                   check=lambda p: "access_token" in p)
    if not isinstance(payload, dict) or "access_token" not in payload:
        print(color("31", "Impossible de continuer sans token."))
        sys.exit(1)
    return payload["access_token"]


def cleanup(admin):
    # Suppression silencieuse de ce que la démo a créé, même si elle
    # s'est arrêtée au milieu
    actions = [
        ("POST", MOVIE_GRAPHQL_URL, {
            "query": "mutation ($id: String!) "
                     "{ delete_movie(_id: $id) { success } }",
            "variables": {"id": DEMO_MOVIE}}),
        ("DELETE", f"{SCHEDULE_URL}/dates/{DEMO_DATE}", None),
        ("DELETE", f"{USER_URL}/user/{DEMO_USER}", None),
    ]
    for method, url, body in actions:
        try:
            call(method, url, body, admin)
        except (urllib.error.URLError, OSError):
            pass


def scenario():
    section("1. Connexion : le service user délivre des tokens JWT")
    admin = tokens["admin"] = login(ADMIN_NAME)
    step("création d'un compte client", "POST",
         f"{USER_URL}/user/{DEMO_USER}", 201, body={"name": DEMO_NAME})
    client = login(DEMO_NAME)

    section("2. Catalogue : movie en GraphQL, mutations réservées aux admins")
    gql("un client lit un film et ses acteurs en une requête",
        MOVIE_GRAPHQL_URL,
        '{ movie_with_title(_title: "the martian") '
        "{ title director actors { firstname lastname } } }",
        check=lambda p: p["data"]["movie_with_title"]["actors"])
    add_movie = ("mutation ($id: String!) { add_movie(_id: $id, "
                 'title: "Film de démo", director: "Démo", rating: 7.5) '
                 "{ success message } }")
    gql("un client ne peut pas ajouter de film", MOVIE_GRAPHQL_URL,
        add_movie, {"id": DEMO_MOVIE}, client,
        check=lambda p: not p["data"]["add_movie"]["success"])
    gql("l'admin ajoute un film", MOVIE_GRAPHQL_URL, add_movie,
        {"id": DEMO_MOVIE}, admin,
        check=lambda p: p["data"]["add_movie"]["success"])

    section("3. Programmation : schedule vérifie le film auprès de movie")
    step("programmer un film inconnu est refusé", "POST",
         f"{SCHEDULE_URL}/movies/{DEMO_DATE}/film-inexistant", 404,
         token=admin)
    step("l'admin programme le film de démo", "POST",
         f"{SCHEDULE_URL}/movies/{DEMO_DATE}/{DEMO_MOVIE}", 201, token=admin)

    section("4. Réservation : user → booking → schedule + movie")
    bookings_url = f"{USER_URL}/user/{DEMO_USER}/bookings"
    step("le client réserve le film", "POST", bookings_url, 201,
         body={"date": DEMO_DATE, "movieid": DEMO_MOVIE}, token=client)
    step("réserver un jour où le film n'est pas programmé est refusé",
         "POST", bookings_url, 400,
         body={"date": "20990102", "movieid": DEMO_MOVIE}, token=client)
    step("le client voit ses réservations avec le détail des films", "GET",
         bookings_url, token=client,
         check=lambda p: p["dates"][0]["movies"][0]["title"]
         == "Film de démo")
    step("mais pas celles des autres", "GET",
         f"{USER_URL}/user/chris_rivers/bookings", 403, token=client)

    section("5. Suppression en cascade : movie prévient schedule et booking")
    gql("l'admin supprime le film", MOVIE_GRAPHQL_URL,
        "mutation ($id: String!) { delete_movie(_id: $id) "
        "{ success message } }",
        {"id": DEMO_MOVIE}, admin,
        check=lambda p: p["data"]["delete_movie"]["success"])
    step("il n'est plus programmé", "GET",
         f"{SCHEDULE_URL}/movies/{DEMO_MOVIE}", 404)
    step("la réservation du client a disparu", "GET", bookings_url,
         token=client, check=lambda p: p["dates"] == [])


def main():
    print(color("1", "Démo des services movie / booking / schedule / user"))
    wait_for_services()
    try:
        scenario()
    except (KeyError, TypeError, IndexError) as error:
        # Une réponse inattendue empêche de continuer le scénario
        results["ko"] += 1
        print(color("31", f"\nScénario interrompu : réponse inattendue "
                          f"({error!r})"))
    finally:
        if "admin" in tokens:
            cleanup(tokens["admin"])

    print()
    total = results["ok"] + results["ko"]
    summary = f"{results['ok']}/{total} étapes réussies"
    if results["ko"]:
        print(color("1;31", f"✘ {summary}, {results['ko']} en échec"))
        sys.exit(1)
    print(color("1;32", f"✔ {summary}"))


if __name__ == "__main__":
    main()
