import json
import requests # soucis avec requests alors que requeststs est bien dans les requirements.

SCHEDULE_URL = "http://127.0.0.1:3202"

# RESOLVEUR de la requête
def booking_with_id(_,info,_id):
   with open('{}/data/bookings.json'.format("."), "r") as file:
      bookings = json.load(file)
      for booking in bookings['bookings']:
         if booking['userid'] == _id:
            return booking
      return None
   
def delete_with_id(_, info, _id):
   with open('{}/data/bookings.json'.format("."), "r") as file:
      bookings = json.load(file)

   before = len(bookings["bookings"])
   bookings["bookings"] = [b for b in bookings["bookings"] if b["userid"] != _id]

   if len(bookings["bookings"]) == before:
      return {"success": False, "message": "Aucun booking trouvé pour {}.".format(_id)}

   with open('{}/data/bookings.json'.format("."), "w") as file:
      json.dump(bookings, file, indent=2)
   return {"success": True, "message": "Le booking de {} a été supprimé.".format(_id)}
   
# RESOLVER du type Date dans Booking
def resolve_bookings_date(booking,info):
   # dates est déjà dans booking donc :
   return booking['dates'] 


# RESOLVER d'ajout
def add_booking(_, info, userid, date, movieid):
    path = "./data/bookings.json"

    try:
        response = requests.get("{}/dates/{}".format(SCHEDULE_URL, date), timeout=5)
    except requests.RequestException:
        return {"success": False, "message": "Service schedule injoignable."}

    if response.status_code != 200 or str(movieid) not in [str(m) for m in response.json()]:
        return {"success": False, "message": "Le film {} n'est pas programmé le {}.".format(movieid, date)}

    with open(path, "r") as file:
        data = json.load(file)

    booking = next((b for b in data["bookings"] if b["userid"] == userid), None)
    if booking is None:
        return {"success": False, "message": "Utilisateur {} introuvable.".format(userid)}

    entry = next((d for d in booking["dates"] if d["date"] == date), None)
    if entry is None:
        booking["dates"].append({"date": date, "movies": [movieid]})
    elif movieid not in entry["movies"]:
        entry["movies"].append(movieid)
    else:
        return {"success": False, "message": "Le film {} est déjà réservé le {} pour {}.".format(movieid, date, userid)}

    with open(path, "w") as file:
        json.dump(data, file, indent=2)

    return {"success": True, "message": "Réservation ajoutée pour {} le {}.".format(userid, date)}