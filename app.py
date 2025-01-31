from flask import Flask, request, jsonify, render_template, redirect, url_for
import pymysql
import boto3
import base64
import csv
import uuid
from datetime import datetime, timezone


app = Flask(__name__)

# DynamoDB Local setup
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url='http://localhost:8000',  # DynamoDB Local endpoint
    region_name='us-west-2',
    aws_access_key_id='dummy',
    aws_secret_access_key='dummy'
)

# MySQL database connection setup
db = pymysql.connect(
    host="localhost",
    user="root",     # Replace with your MySQL username
    password="root123",  # Replace with your MySQL password
    database="socialapp_db"
)

# Reference to the DynamoDB tables
users_table = dynamodb.Table('Users')
posts_table = dynamodb.Table('Posts')

def create_dynamodb_tables():
    # Create Users Table
    try:
        users_table.load()
        print("Users table already exists.")
    except:
        dynamodb.create_table(
            TableName='Users',
            KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        print("Users table created successfully.")

    # Create Posts Table
    try:
        posts_table.load()
        print("Posts table already exists.")
    except:
        dynamodb.create_table(
            TableName='Posts',
            KeySchema=[{'AttributeName': 'post_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'post_id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        print("Posts table created successfully.")

def import_users_from_csv():
    with open('users.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            users_table.put_item(Item={
                'user_id': row['user_id'],
                'username': row['username'],
                'email': row['email']
            })
    print("Users imported successfully.")

def import_posts_from_csv():
    with open('posts.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Add metadata to DynamoDB
            posts_table.put_item(Item={
                'post_id': row['post_id'],
                'user_id': row['user_id'],
                'title': row['title'],
                'content': row['content'],
                'created_at': datetime.utcnow().isoformat()
            })

            # Add image to MySQL
            image_data = base64.b64decode(row['image'])
            cursor = db.cursor()
            cursor.execute("INSERT INTO post_images (post_id, image) VALUES (%s, %s)", (row['post_id'], image_data))
            db.commit()
            cursor.close()
    print("Posts imported successfully.")

    
@app.route('/')
def home():
    return render_template('index.html')

# Route to create a new post
@app.route('/create_post', methods=['POST'])
def create_post():
    title = request.form.get('title')
    content = request.form.get('content')
    user_id = request.form.get('user_id')
    image = request.files.get('image')
    
    # Generate a unique post_id
    post_id = str(uuid.uuid4())
    
    # Insert metadata into DynamoDB
    posts_table.put_item(
        Item={
            'post_id': post_id,
            'user_id': user_id,
            'title': title,
            'content': content,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
    )

    # Insert the image into MySQL
    if image:
        image_data = image.read()
        cursor = db.cursor()
        cursor.execute("INSERT INTO post_images (post_id, image) VALUES (%s, %s)", (post_id, image_data))
        db.commit()
        cursor.close()
    
    return redirect(url_for('home'))

# Route to get all posts
@app.route('/get_users', methods=['GET'])
def get_users():
    """Retrieve all users from DynamoDB."""
    response = users_table.scan()
    users = response.get('Items', [])
    return jsonify(users)

@app.route('/get_posts', methods=['GET'])
def get_posts():
    """Retrieve all posts, with images combined from MySQL."""
    response = posts_table.scan()
    posts = response.get('Items', [])

    # Retrieve images from MySQL and merge with posts metadata
    for post in posts:
        post_id = post['post_id']
        cursor = db.cursor()
        cursor.execute("SELECT image FROM post_images WHERE post_id = %s", (post_id,))
        image_row = cursor.fetchone()
        cursor.close()
        
        # Convert the binary image to base64
        if image_row and image_row[0]:
            post['image'] = f"data:image/jpeg;base64,{base64.b64encode(image_row[0]).decode('utf-8')}"
        else:
            post['image'] = None

    return jsonify(posts)


if __name__ == '__main__':
    #create_dynamodb_tables()
    #import_users_from_csv()
    #import_posts_from_csv()
    app.run(debug=True)
