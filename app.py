from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
from flask_pymongo import PyMongo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, timedelta
from dotenv import load_dotenv
import my_YoloV8
import cv2
import json
import random
import imghdr
import smtplib


# from random import random
# Khởi tạo Flask Server Backend
load_dotenv()
app = Flask(__name__)
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'mp4','webp'])
# Apply Flask CORS
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['UPLOAD_FOLDER'] = "static"
#xoa
password = "qxbtmejfppoyhvrp"
from_email = "nghiahuynhhuutbag2503@gmail.com"  # must match the email used to generate the password
# to_email = ""  # receiver email
server = smtplib.SMTP("smtp.gmail.com: 587")
server.starttls()
server.login(from_email, password)


app.config["MONGO_URI"] = "mongodb://localhost:27017/HealthyMenu"
mongo = PyMongo(app)

# Model initialization before starting the server



app.secret_key = os.environ.get("FLASK_SECRET")
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
jwt = JWTManager(app)

# This function will be executed before handling the first request
# @app.before_first_request
# def initialize_model():
#     global model
#     model = my_YoloV8.YOLOv8_ObjectCounter(model_file="best.pt")
#     print("YOLOv8 model initialized.")
@app.route('/test_connection', methods=['GET'])
def test_connection():
    try:
        # Try to retrieve the list of collections as a basic test
        collections = mongo.db.list_collection_names()
        return jsonify(status="success", collections=collections), 200
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

@app.route("/login", methods=["POST"])
def login():
        email = request.json.get('email')
        pwd = request.json.get('password')
        cur = mongo.connection.cursor()
        cur.execute(f"select * from user where email = '{email}'")
        users = cur.fetchone()
        cur.close()
        # check_password_hash(users[3], pwd)
        if users and  check_password_hash(users[3], pwd):
            print("ok")
            access_token = create_access_token(identity=users[0])
            return jsonify({"email":users[0],"auth":True,"password":"","username":users[1], "avatar":users[2], "admin":users[4],"date":users[5],"access_token":"Bearer "+access_token})
        else:
            return jsonify({"auth":False})

@app.route("/register", methods=["POST"])
def register():
        print("ok")
        print(request.json.get("email"))
        email = request.json.get("email")
        password = generate_password_hash(request.json.get('password'))
        date = datetime.now()
        cur = mongo.connection.cursor()
        cur.execute(f"SELECT * FROM user WHERE email = '{email}'")
        existing_user = cur.fetchone()
        cur.close()
        if existing_user:
            return jsonify({"auth":False})
        else:
            cur = mongo.connection.cursor()
            user_name = email.split('@')[0]
            print(user_name)
            cur.execute(f"INSERT INTO user (email,username, avatar, password, admin, date) VALUES ('{email}','{user_name}','{''}','{password}','false','{date.date()}')")
            mongo.connection.commit()
            return jsonify({"auth":True})

@app.route("/detailUser/<email>")
def detailUser(email):
    cur = mongo.connection.cursor()
    cur.execute(f"SELECT * FROM user where email='{email}'")
    user = cur.fetchone()
    cur.execute(f"SELECT * FROM history where email='{email}'")
    histories = cur.fetchall()
    print(histories)
    dataUser = {
        "email": user[0],
        "username": user[1],
        "avatar": user[2],
        "admin": user[4],
        "date":user[5]
    }
    counters = {
         'total': 0,
            'fire': 0,
            'smoke': 0,
        "sumImgs": len(histories)
    }
    countShrimp(histories, counters)
    # print({"sumImgs":len(histories),"total" : counters["total_shrimp"],"big" : counters["total_big_shrimp"],"medium":counters["total_medium_shrimp"],"small":counters["total_small_shrimp"]})
    cur.close()
    if user:
        return jsonify({"dataUser": dataUser,"datas":counters,"dataHistories":histories})
    else:
        return jsonify({"exists": False})


@app.route('/delete_data', methods=['POST'])
def delete_data():
    id = request.json.get("id")
    print(id)
    CS = mongo.connection.cursor()
    try:
        CS.execute(f"""DELETE FROM history WHERE id = '{id}'""")
        mongo.connection.commit()
        CS.close()
        return jsonify({'success': True})
    except Exception as e:
        mongo.connection.rollback()
        CS.close()
        return jsonify({'success': False, 'error': str(e)})



@app.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    email = get_jwt_identity()
    if email:
        current_pwd = request.json.get('oldpas')
        new_pwd = request.json.get('newpass')
        cur = mongo.connection.cursor()
        cur.execute(f"SELECT password FROM user WHERE email = '{email}'")
        user_data = cur.fetchone()
        print(check_password_hash(user_data[0], current_pwd))
        if user_data and check_password_hash(user_data[0], current_pwd):
            cur.execute(f"UPDATE user SET password = '{generate_password_hash(new_pwd)}' WHERE email = '{email}'")
            mongo.connection.commit()
            cur.close()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False,"error":"Current password is incorrect"})
    else:
        return jsonify({'success': False,"error":"Cant find user"})
    
@app.route("/changeUsername", methods=["POST"])
def change_username():
    if request.form['email']:
        current_username = request.form['username']
        email = request.form['email']
        cur = mongo.connection.cursor()
        cur.execute(f"SELECT * FROM user WHERE email = '{email}'")
        user_data = cur.fetchone()
        path_save = user_data[2]
        if request.files.getlist('File'):
            current_avatar = request.files.getlist('File')[0]
            filename = secure_filename(current_avatar.filename)
            if(filename):
                path_save = os.path.join(app.config['UPLOAD_FOLDER'] + "/upload/users/", filename)
                current_avatar.save(path_save)
        if user_data:
            cur.execute(f"UPDATE user SET username = '{current_username}', avatar='/{path_save}' WHERE email = '{email}'")
            mongo.connection.commit()
            cur.execute(f"SELECT * FROM user WHERE email = '{email}'")
            Executed_DATA= cur.fetchone()
            print(Executed_DATA)
            cur.close()
            return jsonify({"email": Executed_DATA[0], "auth":True,"password":"","username":Executed_DATA[1], "avatar":Executed_DATA[2], "admin":Executed_DATA[4],"date":Executed_DATA[5],"access_token":"Bearer "+create_access_token(identity=Executed_DATA[0])})
        else:
            return jsonify({'success': True, 'image_path': "incorrect", "Info": {}})
    else:
        return jsonify({'success': False})


