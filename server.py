from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import motor.motor_asyncio
import bcrypt
import jwt
import os

app = FastAPI()

# --- DATABASE CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://monar:king123@cluster0.vytusx9.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client.shadow_db
users_collection = db.users
custom_tasks_collection = db.custom_tasks

JWT_SECRET = os.getenv("JWT_SECRET", "shadow_monarch_secret_key_123")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PYDANTIC SCHEMAS ---
class AuthRequest(BaseModel):
    email: str
    password: str

class StartRequest(BaseModel):
    user_id: str = "default_user"

class TaskUpdate(BaseModel):
    user_id: str = "default_user"
    day_number: int
    task_index: int
    completed: bool

class CustomTaskRequest(BaseModel):
    user_id: str = "default_user"
    task: str
    time: str
    duration: int = 30
    task_type: str = "permanent"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

# --- HELPER FUNCTIONS ---
def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def calculate_rank(percentage):
    if percentage >= 97: return "1%"
    elif percentage >= 90: return "S"
    elif percentage >= 85: return "A"
    elif percentage >= 75: return "B"
    elif percentage >= 65: return "C"
    elif percentage >= 50: return "D"
    elif percentage >= 30: return "E"
    else: return "F"

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
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")

# --- SYSTEM HEALTH ROUTE ---
@app.api_route("/", methods=["GET", "HEAD"])
async def health():
    try:
        await client.admin.command('ping')
        return {"status": "Online", "database": "Connected ✅", "server_time_ist": get_ist_time().isoformat()}
    except Exception as e:
        return {"status": "Online", "database": f"Error: {str(e)} ❌"}

# --- AUTHENTICATION ENDPOINTS ---
@app.post("/api/auth/register")
@app.post("/auth/register")
async def register(user_data: AuthRequest):
    email_clean = user_data.email.strip().lower()
    existing_user = await users_collection.find_one({"email": email_clean})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists with this email!")

    hashed_pwd = hash_password(user_data.password.strip())
    ist_now = get_ist_time()
    
    new_user = {
        "email": email_clean,
        "password": hashed_pwd,
        "user_id": email_clean,
        "start_date": ist_now.isoformat(),
        "active": True,
        "history": {}
    }

    result = await users_collection.insert_one(new_user)
    user_id = str(result.inserted_id)
    token = create_access_token({"userId": user_id, "email": email_clean})

    return {
        "success": True,
        "token": token,
        "userId": email_clean,
        "email": email_clean,
        "message": "Shadow Monarch Awakened!"
    }

@app.post("/api/auth/login")
@app.post("/auth/login")
async def login(user_data: AuthRequest):
    email_clean = user_data.email.strip().lower()
    user = await users_collection.find_one({"email": email_clean})
    
    if not user or not verify_password(user_data.password.strip(), user["password"]):
        raise HTTPException(status_code=400, detail="Invalid Email or Password!")

    token = create_access_token({"userId": str(user["_id"]), "email": user["email"]})

    return {
        "success": True,
        "token": token,
        "userId": user.get("user_id", email_clean),
        "email": user["email"],
        "message": "Welcome Back, Shadow Monarch!"
    }

# --- CHALLENGE & TASK PROGRESSION ENDPOINTS ---
@app.get("/api/challenge/current")
async def get_current_status(user_id: str = "default_user"):
    try:
        user = await users_collection.find_one({"user_id": user_id})
        if not user:
            user = {"user_id": user_id, "start_date": get_ist_time().isoformat(), "history": {}}

        ist_now = get_ist_time()
        today_str = ist_now.strftime("%Y-%m-%d")
        day_of_week = ist_now.strftime("%A")
        
        start_date_str = user.get("start_date")
        try:
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            else:
                start_date = ist_now
        except Exception:
            start_date = ist_now
            
        current_day = max(1, (ist_now.date() - start_date.date()).days + 1)

        user_tasks_cursor = custom_tasks_collection.find({"user_id": user_id})
        user_tasks = await user_tasks_cursor.to_list(length=100)

        tasks_list = []
        for t in user_tasks:
            if t.get("task_type") == "temporary":
                s_date = t.get("start_date")
                e_date = t.get("end_date")
                if s_date and e_date and not (s_date <= today_str <= e_date):
                    continue
            
            tasks_list.append({
                "task": t.get("task"),
                "time": t.get("time", "12:00 PM"),
                "duration": t.get("duration", 30),
                "task_type": t.get("task_type", "permanent"),
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date")
            })

        history = user.get("history", {})
        if not isinstance(history, dict): history = {}
            
        completed_today = history.get(today_str, [])
        if not isinstance(completed_today, list): completed_today = []

        tasks_response = []
        for idx, t in enumerate(tasks_list):
            tasks_response.append({
                "task": t["task"], 
                "time": t["time"], 
                "duration": t["duration"],
                "task_type": t["task_type"],
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date"),
                "completed": idx in completed_today
            })
        
        total_tasks_count = len(tasks_response)
        completion_percentage = (len(completed_today) / total_tasks_count * 100) if total_tasks_count > 0 else 0.0
        
        total_tasks_done = sum(len(tasks) for tasks in history.values() if isinstance(tasks, list))
        current_level = 1 + (total_tasks_done // 5)
        current_rank_daily = calculate_rank(completion_percentage)
        
        stats = {
            "strength": 10 + int(total_tasks_done * 1.5),
            "vitality": 10 + int(total_tasks_done * 1.2),
            "agility": 10 + int(total_tasks_done * 1.0),
            "recovery": 10 + int(total_tasks_done * 0.8)
        }
        
        return {
            "active": True,
            "challenge": {
                "current_day": current_day,
                "current_rank": current_rank_daily, 
                "current_level": current_level,
                "stats": stats,
                "start_date": start_date_str if start_date_str else ist_now.isoformat()
            },
            "today": {
                "day_number": current_day,
                "date": today_str,
                "day_of_week": day_of_week,
                "tasks": tasks_response,
                "completion_percentage": completion_percentage, 
                "is_sunday": False
            }
        }
    except Exception as e:
        print(f"CRITICAL ERROR IN CURRENT STATUS: {e}")
        return {"active": False, "error": str(e)}

@app.post("/api/challenge/custom-task")
async def add_custom_task(req: CustomTaskRequest):
    try:
        new_task = {
            "user_id": req.user_id,
            "task": req.task,
            "time": req.time,
            "duration": req.duration,
            "task_type": req.task_type,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "created_at": get_ist_time().isoformat()
        }
        await custom_tasks_collection.insert_one(new_task)
        return {"success": True, "message": "Task added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/challenge/task")
async def update_task(req: TaskUpdate):
    try:
        ist_now = get_ist_time()
        today_str = ist_now.strftime("%Y-%m-%d")
        user = await users_collection.find_one({"user_id": req.user_id})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        history = user.get("history", {})
        if not isinstance(history, dict): history = {}
            
        completed_today = history.get(today_str, [])
        if not isinstance(completed_today, list): completed_today = []
        
        if req.completed and req.task_index not in completed_today:
            completed_today.append(req.task_index)
        elif not req.completed and req.task_index in completed_today:
            completed_today.remove(req.task_index)
            
        history[today_str] = completed_today
        await users_collection.update_one({"user_id": req.user_id}, {"$set": {"history": history}})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/challenge/stats")
@app.get("/api/challenge/history")
async def get_history(user_id: str = "default_user", days: int = 30):
    try:
        user = await users_collection.find_one({"user_id": user_id})
        if not user:
            return {"history": []}
        
        history_dict = user.get("history", {})
        if not isinstance(history_dict, dict): history_dict = {}
            
        formatted_history = []
        ist_now = get_ist_time()
        today_date = ist_now.date()
        
        start_date_str = user.get("start_date")
        try:
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00")).date()
            else:
                start_date = today_date
        except Exception:
            start_date = today_date
            
        range_start = max(start_date, today_date - timedelta(days=days-1))
        current_iter_date = range_start
        
        while current_iter_date <= today_date:
            date_str = current_iter_date.strftime("%Y-%m-%d")
            day_name = current_iter_date.strftime("%A")
            day_num = max(1, (current_iter_date - start_date).days + 1)
            
            completed_count = len(history_dict.get(date_str, []))
            user_tasks_count = await custom_tasks_collection.count_documents({"user_id": user_id})
            completion_percentage = (completed_count / user_tasks_count * 100) if user_tasks_count > 0 else 0.0
                
            formatted_history.append({
                "day_number": day_num,
                "date": date_str,
                "day_of_week": day_name,
                "completion_percentage": completion_percentage,
                "rank": calculate_rank(completion_percentage)
            })
            current_iter_date += timedelta(days=1)
        
        return {
            "current_rank": calculate_rank(formatted_history[-1]["completion_percentage"] if formatted_history else 0),
            "current_level": 1 + (sum(len(v) for v in history_dict.values() if isinstance(v, list)) // 5),
            "history": formatted_history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))