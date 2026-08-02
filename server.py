from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
import bcrypt
import jwt
import os
from datetime import datetime, timedelta

app = FastAPI()

# Enable CORS for Mobile Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Connection (Env variable ya Direct Connection)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["arise_database"]
users_collection = db["users"]

JWT_SECRET = os.getenv("JWT_SECRET", "shadow_monarch_secret_key_123")
ALGORITHM = "HS256"

# Pydantic Schemas
class AuthRequest(BaseModel):
    email: str
    password: str

# Helper Functions
def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

# ⚔️ REGISTER USER ENDPOINT
@app.post("/api/auth/register")
def register(user_data: AuthRequest):
    # Check if user exists
    existing_user = users_collection.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists!"
        )

    hashed_pwd = hash_password(user_data.password)
    new_user = {
        "email": user_data.email.lower(),
        "password": hashed_pwd,
        "created_at": datetime.utcnow()
    }

    result = users_collection.insert_one(new_user)
    user_id = str(result.inserted_id)
    token = create_access_token({"userId": user_id, "email": user_data.email.lower()})

    return {
        "success": True,
        "token": token,
        "userId": user_id,
        "email": user_data.email.lower(),
        "message": "Shadow Monarch Awakened Successfully!"
    }

# 🔓 LOGIN USER ENDPOINT
@app.post("/api/auth/login")
def login(user_data: AuthRequest):
    user = users_collection.find_one({"email": user_data.email.lower()})
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid email or password!"
        )

    if not verify_password(user_data.password, user["password"]):
        raise HTTPException(
            status_code=400,
            detail="Invalid email or password!"
        )

    user_id = str(user["_id"])
    token = create_access_token({"userId": user_id, "email": user["email"]})

    return {
        "success": True,
        "token": token,
        "userId": user_id,
        "email": user["email"],
        "message": "Welcome Back, Shadow Monarch!"
    }