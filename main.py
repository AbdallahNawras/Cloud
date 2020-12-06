from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, set_access_cookies, jwt_optional
from flask import Flask, jsonify, request, render_template, redirect, make_response, session
from werkzeug.security import check_password_hash, generate_password_hash
from google.cloud import datastore
from google.oauth2 import service_account
from flask_restful import Resource, Api, fields, marshal_with, abort
import datetime
import os

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'auth.json'
client = datastore.Client()

app = Flask (__name__)

app.secret_key = "1234abcd"

app.config['JWT_SECRET_KEY'] = '1234abcd'
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
app.config['JWT_REFRESH_COOKIE_PATH'] = '/token/refresh'
app.config['PROPAGATE_EXCEPTIONS'] = True

jwt = JWTManager(app)
api = Api(app)



boatFields = {
    'id': fields.String,
    'name': fields.String,
    'type': fields.String,
    'length': fields.String,
    'owner': fields.String,
    'loads': fields.List(fields.String),
    'self': fields.Url('boat', absolute=True)
}

paginatedBoat = {
    "count": fields.Integer,
    "limit": fields.Integer,
    "next": fields.String,
    "previous": fields.String,
    "results": fields.List(fields.Nested(boatFields)),
    "start": fields.Integer
}

LoadFields = {
    "id": fields.String,
    "weight": fields.Integer,
    "content": fields.String,
    "delivery_date": fields.String,
    "boat_id": fields.String,
    "self": fields.Url("load", absolute=True)
}

paginatedLoad = {
    "count": fields.Integer,
    "limit": fields.Integer,
    "next": fields.String,
    "previous": fields.String,
    "results": fields.List(fields.Nested(LoadFields)),
    "start": fields.Integer
}

class BoatAPI(Resource):
    @jwt_required
    @marshal_with(boatFields)
    def get(self, id):
        key = client.key("Boat", int(id))
        boat = client.get(key)

        if boat == None:
            abort(404, Error="No boat with this boat_id exists")

        if boat["owner"] != get_jwt_identity():
            abort(403, Error= "Forbidden, you don't own this boat")

        query = client.query(kind='Load')
        result = list(query.add_filter("boat_id", "=", str(boat.id)).fetch())
        loads = list()

        for r in result:
            loads.append(r.id)

        res = {
            "id": boat.id,
            "name": boat["name"], 
            "type": boat["type"],
            "length": boat["length"],
            "owner": boat["owner"],
            "loads": loads
        }
        return res, 200
        
    @jwt_required
    @marshal_with(boatFields)
    def patch(self, id):
        if not request.is_json:
            abort(406, Error="Request body must be json")

        body = request.get_json(force=True)
        try:
            name = body["name"]
            boatType = body["type"]
            length = body["length"]
        except:
            abort(400, Error="The request object is missing at least one of the required attributes")

        key = client.key("Boat", int(id))
        boat = client.get(key)

        if boat == None:
            abort(404, Error="No boat with this boat_id exists")

        if boat["owner"] != get_jwt_identity():
            abort(403, Error= "Forbidden, you don't own this boat")

        boat["name"] = name
        boat["type"] = boatType
        boat["length"] = length

        client.put(boat)

        query = client.query(kind='Load')
        result = list(query.add_filter("boat_id", "=", str(boat.id)).fetch())
        loads = list()

        for r in result:
            loads.append(r.id)

        res = {
            "id": boat.id,
            "name": boat["name"], 
            "type": boat["type"],
            "owner": boat["owner"],
            "loads": loads,
            "length": int(boat["length"])
        }
        return res, 200

    @jwt_required
    def delete(self, id):
        key = client.key("Boat", int(id))
        boat = client.get(key)

        if boat == None:
            abort(404, Error="No boat with this boat_id exists")

        if boat["owner"] != get_jwt_identity():
            abort(403, Error= "Forbidden, you don't own this boat")

        client.delete(key)

        query = client.query(kind='Load')
        result = list(query.add_filter("boat_id", "=", str(id)).fetch())

        print(result)

        if len(result) > 0:
            for load in result:
                load["boat_id"] = None
                client.put(boat)

        return None, 204

class BoatsListAPI(Resource):
    @jwt_required
    @marshal_with(paginatedBoat)
    def get(self):
        query = client.query(kind='Boat')
        result = list(query.add_filter("owner", "=", get_jwt_identity()).fetch())
        boatsList = list()

        for r in result:
            boat = {
                "id": str(r.id),
                "name": r["name"],
                "type": r["type"],
                "length": r["length"],
                "owner": r["owner"]
            }

            boatsList.append(boat)

        return get_paginated_list(
        boatsList, 
        '/boats', 
        start=request.args.get('start', 1), 
        limit=request.args.get('limit', 5))

    @jwt_required
    @marshal_with(boatFields)
    def post(self):
        if not request.is_json:
            abort(406, Error="request must be json")

        body = request.get_json(force=True)

        try:
            name = body["name"]
            boatType = body["type"]
            length = body["length"]
        except:
            abort(400, Error="The request object is missing at least one of the required attributes")
           

        boat = datastore.Entity(client.key('Boat'))
        boat.update({
            "name": name, 
            "type": boatType,
            "length": length,
            "owner": get_jwt_identity(),
            "boat_id": ""
        })

        client.put(boat)

        res = {
            "id": boat.id,
            "name": boat["name"], 
            "type": boat["type"],
            "length": boat["length"],
            "owner": boat["owner"]
        }
        
        return res, 201

class LoadListAPI(Resource):
    @jwt_required
    @marshal_with(paginatedLoad)
    def get(self):
        query = client.query(kind='Load')
        result = query.fetch()
        LoadList = list()

        for r in result:
            if "boat_id" in r.keys():
                load = {
                    "id": str(r.id),
                    "weight": r["weight"],
                    "content": r["content"],
                    "delivery_date":  r["delivery_date"],
                    "boat_id": r["boat_id"]
                }

                LoadList.append(load)

            else:
                load = {
                    "id": str(r.id),
                    "weight": r["weight"],
                    "content": r["content"],
                    "delivery_date":  r["delivery_date"]
                }

                LoadList.append(load)

        return get_paginated_list(
        LoadList, 
        '/loads', 
        start=request.args.get('start', 1), 
        limit=request.args.get('limit', 5))

    @jwt_required
    @marshal_with(LoadFields)
    def post(self):
        body = request.get_json(force=True)

        try:
            weight = body["weight"]
            content = body["content"]
            delivery_date = body["delivery_date"]
           
        except:
            abort(400, Error="The request object is missing the required number")
           

        load = datastore.Entity(client.key('Load'))
        load.update({
            "weight": weight,
            "content": content,
            "delivery_date": delivery_date
        })

        client.put(load)

        res = {
            "id": load.id,
            "weight": load["weight"],
            "content": load["content"],
            "delivery_date": load["delivery_date"]
        }

        return res, 201

class LoadAPI(Resource):
    @jwt_required
    @marshal_with(LoadFields)
    def get(self, id):
        key = client.key("Load", int(id))
        load = client.get(key)

        if load == None:
            abort(404, Error="No load with this load_id exists")

        
        if "boat_id" in load.keys():
            res = {
                "id": str(load.id),
                "weight": load["weight"],
                "content": load["content"],
                "delivery_date": load["delivery_date"],
                "boat_id": load["boat_id"]
            }

        else:
            res = {
                "id": str(load.id),
                "weight": load["weight"],
                "content": load["content"],
                "delivery_date": load["delivery_date"]            
            }

        return res, 200

    @jwt_required
    def delete(self, id):
        key = client.key("Load", int(id))
        load = client.get(key)

        if load == None:
            abort(404, Error="No load with this load_id exists")

        client.delete(key)

        return None, 204

    @jwt_required
    @marshal_with(LoadFields)
    def patch(self, id):
        if not request.is_json:
            abort(406, Error="Request body must be json")

        body = request.get_json(force=True)
        try:
            weight = body["weight"]
            content = body["content"]
            delivery_date = body["delivery_date"]
        except:
            abort(400, Error="The request object is missing at least one of the required attributes")

        key = client.key("Load", int(id))
        load = client.get(key)

        if load == None:
            abort(404, Error="No load with this load exists")


        load["weight"] = weight
        load["content"] = content
        load["delivery_date"] = delivery_date

        client.put(load)

        if "boat_id" in load.keys():
            res = {
                "id": load.id,
                "weight": load["weight"], 
                "content": load["content"],
                "delivery_date": load["delivery_date"],
                "boat_id": load["boat_id"]
            }

        else: 
            res = {
                "id": load.id,
                "weight": load["weight"], 
                "content": load["content"],
                "delivery_date": load["delivery_date"]
            }
        return res, 200

class BoatLoadAPI(Resource):
    @jwt_required
    @marshal_with(LoadFields)
    def put(self, loadID, boatID):
        key = client.key("Load", int(loadID))
        load = client.get(key)

        key = client.key("Boat", int(boatID))
        boat = client.get(key)
        
        if load == None:
            abort(404, Error="No load with this load exists")

        if boat == None:
            abort(404, Error="No boat with this boat id exists")

        load["boat_id"] = boatID

        client.put(load)

        res = {
            "id": load.id,
            "weight": load["weight"], 
            "content": load["content"],
            "delivery_date": load["delivery_date"],
            "boat_id": load["boat_id"]
        }

        return res, 200

    @jwt_required
    @marshal_with(LoadFields)
    def delete(self, loadID, boatID):
        key = client.key("Load", int(loadID))
        load = client.get(key)

        key = client.key("Boat", int(boatID))
        boat = client.get(key)
        
        if load == None:
            abort(404, Error="No load with this load exists")

        if boat == None:
            abort(404, Error="No boat with this boat id exists")

        load["boat_id"] = None

        client.put(load)

        res = {
            "id": load.id,
            "weight": load["weight"], 
            "content": load["content"],
            "delivery_date": load["delivery_date"],
            "boat_id": load["boat_id"]
        }

        return res, 200

@app.route('/callback', methods=['POST'])
def callback():
    query = client.query(kind='User')
    result = list(query.add_filter("username", "=", request.form["username"]).fetch())

    if len(result) == 0:
        return "Error, no user with the username {} exists".format(request.form["username"])

    if request.form["username"] != result[0]["username"] or not check_password_hash(result[0]["password"], request.form["password"]):
        return "Error: bad username or password"

    print(result[0]["username"])
    expires = datetime.timedelta(days=365)

    access_token = create_access_token(identity=request.form["username"], expires_delta=expires)

    print(access_token)
    resp = make_response(redirect('/'))
    resp.set_cookie("id", str(result[0].id))
    set_access_cookies(resp, access_token)
    
    return resp
   


@app.route('/login', methods=['GET'])
def login():
    return render_template("login.html")


@app.route('/users/create', methods=['POST'])
def signupProcess():
    name = request.form['username']
    password = request.form['password']
    hashedPass = generate_password_hash(password, "sha256")

    print(name)
    print(password)
    print(hashedPass)

    query = client.query(kind='User')
    result = list(query.add_filter("username", "=", request.form["username"]).fetch())

    if len(result) > 0:
        return "Error, a user with the same username {} exists".format(request.form["username"]) 

    user = datastore.Entity(client.key('User'))
    user.update({
        "username": name, 
        "password": hashedPass,
    })

    client.put(user)
    
    return render_template("successful_signup.html")

@app.route('/logout', methods=["GET"])
@jwt_required
def logout():
    resp = make_response(redirect('/login'))
    resp.delete_cookie("access_token_cookie", path="/")
    resp.delete_cookie("refresh_token_cookie", path="/token/refresh")
    resp.delete_cookie("session", path="path")

    return resp


@app.route('/signup', methods=['GET'])
def signup():
    return render_template("signup.html")

@app.route('/')
@jwt_optional
def home():
    user = get_jwt_identity()
    if user == None:
        return redirect('/login')
    
    token = request.cookies.get("access_token_cookie")
    id = request.cookies.get("id")
    return render_template("dashboard.html", accessToken=token, username=user, userID=id)

@app.route("/users", methods=["GET"])
def users():
    query = client.query(kind='User')
    result = query.fetch()
    userList = list()

    for r in result:
        user = {
            "id": str(r.id),
            "name": r["username"],
            "password": r["password"],
        }

        userList.append(user)

    return jsonify(get_paginated_list(
        userList, 
        '/users', 
        start=request.args.get('start', 1), 
        limit=request.args.get('limit', 5)))

api.add_resource(BoatAPI, "/boats/<string:id>", endpoint='boat')
api.add_resource(BoatsListAPI, "/boats")

api.add_resource(LoadAPI, "/loads/<string:id>", endpoint='load')
api.add_resource(LoadListAPI, "/loads")

api.add_resource(BoatLoadAPI, "/loads/<string:loadID>/boats/<string:boatID>")

data = [{'employee_id': i+1} for i in range(1000)]

def get_paginated_list(results, url, start, limit):
    start = int(start)
    limit = int(limit)
    count = len(results)
    if count < start or limit < 0:
        abort(404)

    obj = {}
    obj['start'] = start
    obj['limit'] = limit
    obj['count'] = count
    
    if start == 1:
        obj['previous'] = ''
    else:
        start_copy = max(1, start - limit)
        limit_copy = start - 1
        obj['previous'] = url + '?start=%d&limit=%d' % (start_copy, limit_copy)

    if start + limit > count:
        obj['next'] = ''
    else:
        start_copy = start + limit
        obj['next'] = url + '?start=%d&limit=%d' % (start_copy, limit)

    obj['results'] = results[(start - 1):(start - 1 + limit)]
    return obj

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=8080)