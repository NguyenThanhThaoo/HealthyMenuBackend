import json
import math

from bson import ObjectId
from flask import Flask, request, jsonify, Blueprint, send_from_directory, render_template

from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler # type: ignore
from sklearn.neighbors import NearestNeighbors # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
from flask_pymongo import PyMongo
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask_restful import Api, Resource
from flasgger import Swagger
# import schedule
# import time
from datetime import datetime
# from random import random
# Khởi tạo Flask Server Backend
load_dotenv()
app = Flask(__name__)
api = Api(app)
# Apply Flask CORS
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['UPLOAD_FOLDER'] = "static"

app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
mongo = PyMongo(app)
client = MongoClient(os.environ.get("MONGO_URI"))
db = client['HealthyMenu']
app.secret_key = os.environ.get("FLASK_SECRET")
app.config['JWT_SECRET_KEY'] = os.environ.get("JWT_SECRET_KEY")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
jwt = JWTManager(app)


# Select the relevant features
features = ['Calo', 'Carbohydrate', 'Protein', 'fat', 'fiber', 'Sodium', 'VitaminC', 'Purine', 'sugar', 'Cholesterol', 'iron']
diseases = pd.read_csv('diseases.csv')

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Tạo thư mục nếu chưa tồn tại
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
 
@app.route("/test_connection", methods=["GET"])
def test_connection():
    try:
        # Try to retrieve the list of collections as a basic test
        user = db.users
        result =user.find_one({"email":os.environ.get("EMAIL_ADMIN")})
        if(result):
            return jsonify(status="success", collections="admin exited"), 200
        else:
            user.insert_one({"email": os.environ.get("EMAIL_ADMIN"), "password": generate_password_hash(os.environ.get("PASSWORD"))})
            return jsonify(status="success", collections="account admin added"), 200
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500
@app.route("/login", methods=["POST"])
def login():
        email = request.json.get('email')
        pwd = request.json.get('password')
        user = db.users
        result = user.find_one({"email": email})
        # cur = mongo.connection.cursor()
        # cur.execute(f"select * from user where email = '{email}'")
        # users = cur.fetchone()
        # cur.close()
        # check_password_hash(users[3], pwd)
        print(result)
        if result and  check_password_hash(result["password"], pwd):
            print("ok")
            access_token = create_access_token(identity=result["email"])
            return jsonify({
                "data": {"email":result["email"]},
                "success":1,
                "err":None,
                "message": "Login Success",
                "acesstoken":"Bearer "+access_token})
        else:
            return jsonify({ "success":0,
                "err":None,
                "message": "Email or password incorrect",})

@app.route("/register", methods=["POST"])
def register():
        email = request.json.get("email")
        password = generate_password_hash(request.json.get('password'))
        date = datetime.now()
        user = db.users
        result = user.find_one({"email": email})
        if result:
            return jsonify({ "success":0,
                "err":None,
                "message": "Account exited",})
        else:
            user_name = email.split('@')[0]
            user.insert_one({"email":email,"username": user_name,"password": password})
            return jsonify({"success":1,
                "err":None,
                "message": "Account was created successfully",})
@app.route('/createFood', methods=['POST'])
def create_food():
    try:
        # Lấy dữ liệu từ form-data
        title = request.form.get('name')
        type0fgroup = request.form.get('typeoffgroup')  # Assuming this is an ID
        typeoffood = request.form.get('typeofffood')  # Assuming this is an ID
        description = request.form.get('description')
        ingredient = request.form.get('ingredient')
        methob = request.form.get('methob')
        image_file = request.files.get('image')

        # Kiểm tra các trường bắt buộc
        if not title or not type0fgroup or not typeoffood or not description or not ingredient or not methob or not image_file:
            return jsonify({"error": "Thiếu thông tin bắt buộc hoặc ảnh!"}), 400

        # Kiểm tra định dạng file ảnh
        if not allowed_file(image_file.filename):
            return jsonify({"error": "Định dạng ảnh không được hỗ trợ!"}), 400

        # Lưu ảnh với tên an toàn
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(image_path)

        # Tạo món ăn mới
        new_food = {
            "title": title,
            "type0fgroup": type0fgroup,  # Lưu ID của nhóm loại
            "typeoffood": typeoffood,  # Lưu ID của loại món ăn
            "description": description,
            "ingredient": ingredient,
            "methob": methob,
            "image_path": image_path  # Đường dẫn lưu ảnh trên server
        }
        # Thêm món ăn vào MongoDB
        result = db.Recipes.insert_one(new_food)
        new_food["_id"] = str(result.inserted_id)
        backup_to_csv()
        return jsonify({
            "message": "Tạo món ăn thành công!",
            "food": new_food
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/editFood/<food_id>', methods=['PUT'])
def edit_food(food_id):
    try:
        # Lấy dữ liệu từ form-data
        title = request.form.get('name')
        type0fgroup = request.form.get('typeoffgroup')  # Assuming this is an ID
        typeoffood = request.form.get('typeofffood')  # Assuming this is an ID
        description = request.form.get('description')
        ingredient = request.form.get('ingredient')
        methob = request.form.get('methob')
        image_file = request.files.get('image')

        # Tạo đối tượng cập nhật
        update_data = {}

        if title:
            update_data["title"] = title
        if type0fgroup:
            update_data["type0fgroup"] = type0fgroup
        if typeoffood:
            update_data["typeoffood"] = typeoffood
        if description:
            update_data["description"] = description
        if ingredient:
            update_data["ingredient"] = ingredient
        if methob:
            update_data["methob"] = methob

        # Nếu có ảnh mới, xử lý lưu ảnh
        if image_file:
            if not allowed_file(image_file.filename):
                return jsonify({"error": "Định dạng ảnh không được hỗ trợ!"}), 400

            # Lưu ảnh với tên an toàn
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            update_data["image_path"] = image_path

        # Kiểm tra nếu có dữ liệu cần cập nhật
        if not update_data:
            return jsonify({"error": "Không có thông tin để cập nhật!"}), 400

        # Cập nhật món ăn trong MongoDB
        result = db.Recipes.update_one({"_id": ObjectId(food_id)}, {"$set": update_data})

        if result.matched_count == 0:
            return jsonify({"error": "Không tìm thấy món ăn để cập nhật!"}), 404

        backup_to_csv()
        return jsonify({"message": "Cập nhật món ăn thành công!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/deleteFood/<food_id>', methods=['DELETE'])
def delete_food(food_id):
    try:
        # Xóa món ăn từ MongoDB dựa trên ID
        result = db.Recipes.delete_one({"_id": ObjectId(food_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Không tìm thấy món ăn để xóa!"}), 404

        backup_to_csv()
        return jsonify({"message": "Xóa món ăn thành công!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/dishes', methods=['GET'])
def get_dishes():
    # Lấy các tham số phân trang từ query params (mặc định là trang 1 và 10 món ăn mỗi trang)
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    # Tính toán số món ăn cần bỏ qua và lấy dữ liệu từ MongoDB
    skip = (page - 1) * limit
    dishes = db.Recipes.find().skip(skip).limit(limit)
    
    # Tính tổng số món ăn trong database
    total_dishes = db.Recipes.count_documents({})
    total_pages = math.ceil(total_dishes / limit)
    
    # Chuyển danh sách món ăn từ MongoDB thành danh sách Python
    dish_list = []
    for dish in dishes:
        dish_list.append({
            "title": dish["title"],
            "description": dish.get("description", ""),
            "image_path": dish.get("image_path", ""),
            "type0fgroup":dish.get("type0fgroup", "") ,  # Lưu ID của nhóm loại
            "typeoffood": dish.get("typeoffood", ""), 
            "ingredient":dish.get("ingredient", "") ,
            "methob":dish.get("methob", "") ,
        })

    # Trả về kết quả phân trang
    return jsonify({
        "total": total_dishes,
        "page": page,
        "limit": limit,
        "totalPages": total_pages,
        "dishes": dish_list
    })
@app.route('/recommand_dishes', methods=['POST'])
def recommand_dishes():
    # Retrieve the status from the request JSON
    status = request.json.get('status')
    
    # Filter the data based on the status
    filtered_data = diseases[diseases['status'] == status]
    print(filtered_data)
    # If filtered_data is empty, return a response indicating no data found
    if filtered_data.empty:
        return jsonify({"message": "No data found for the given health condition."}), 404
    
    # Extract the nutritional values from the filtered data
    row = filtered_data.iloc[0]  # Assuming you only need the first matching record
    
    # Extract the necessary features from the row
    calories = row['Calo']
    carbs = row['Carbohydrate']
    protein = row['Protein']
    fat = row['Fat']
    fiber = row['Fiber']
    sodium = row['Sodium']
    vitamin_c = row['VitaminC']
    purine = row['Purine']
    sugar = row['Sugar']
    cholesterol = row['Cholesterol']
    iron = row['Iron']
    
    # Call the function to recommend dishes based on the extracted values
    recommended_dishes = recommend_dishes_by_health( calories, carbs, protein, fat, fiber, sodium,
        vitamin_c, purine, sugar, cholesterol, iron, status
    )
    
    # Return the recommended dishes as a JSON response
    return jsonify(recommended_dishes.to_dict(orient='records'))  # Converts DataFrame to list of dicts

@app.route("/detailUser/<email>")
def detailUser(email):
    user = db.users
    result = user.find_one({"email": email})
    dataUser = {
        "email": result[0],
        "username": result[1],
        "avatar": result[2],
        "admin": result[4],
        "date":result[5]
    }
    # countShrimp(histories, counters)
    # print({"sumImgs":len(histories),"total" : counters["total_shrimp"],"big" : counters["total_big_shrimp"],"medium":counters["total_medium_shrimp"],"small":counters["total_small_shrimp"]})

    if user:
        return jsonify({"dataUser": dataUser})
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
    
def recommend_dishes_by_health(calories, carbs, protein, fat, fiber, Sodium, VitaminC, Purine, sugar, Cholesterol, iron, health_condition=''):
    data = pd.read_csv('Recipes.csv')
   
    # Convert categorical column 'Tình trạng sức khoẻ' to numerical
    # label_encoder = LabelEncoder()
    # data['status'] = label_encoder.fit_transform(data['status'])

    # Standardize the data
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data[features])

    # Initialize the KNN model
    knn_model = NearestNeighbors(n_neighbors=10, algorithm="brute", metric="cosine")
    knn_model.fit(data_scaled)  # Fit the model on the entire dataset
    input_features_df = pd.DataFrame([[calories, carbs, protein, fat, fiber, Sodium, VitaminC, Purine, sugar, Cholesterol, iron]], columns=features)
    distances, indices = knn_model.kneighbors(input_features_df)

    # Retrieve the recommended dishes
    recommended_dishes = data.iloc[indices[0]]

    # Select relevant columns for the output
    return recommended_dishes[['title','type0fgroup','typeoffood']]

    
def backup_to_csv():
    # Lấy tất cả dữ liệu từ collection
    
    data = db.Recipes.find()
    
    # Chuyển dữ liệu từ MongoDB sang DataFrame của pandas
    df = pd.DataFrame(list(data))
    
    # Loại bỏ trường `_id` khỏi DataFrame (vì MongoDB sẽ tự động thêm trường này)
    # if '_id' in df.columns:
    #     df = df.drop(columns=['_id'])
    
    # Đặt tên file với thời gian hiện tại
    filename = "Recipes.csv"
    
    # Lưu DataFrame vào file CSV
    df.to_csv(filename, index=False)
    print(f"Backup saved as {filename}")

# Lập lịch sao lưu hàng ngày (ví dụ vào lúc 2:00 AM)
# schedule.every().day.at("02:00").do(backup_to_csv)
# schedule.every(10).minutes.do(backup_to_csv)
# def run():
#     while True:
#         schedule.run_pending()
#         time.sleep(1)
if __name__ == '__main__':
    test_connection()
    # from threading import Thread
    # flask_thread = Thread(target=lambda: app.run(debug=True, use_reloader=False))
    # flask_thread.start()
    
    # # Chạy scheduler
    # run()
    app.run(host="0.0.0.0", port=os.environ.get(
        "FLASK_PORT"), debug=True)

