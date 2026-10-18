import json

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