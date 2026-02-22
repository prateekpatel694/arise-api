from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import motor.motor_asyncio
import asyncio

app = FastAPI()

# --- DATABASE CONFIGURATION ---
MONGO_URI = "mongodb+srv://monar:king123@cluster0.vytusx9.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client.shadow_db
users_collection = db.users

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StartRequest(BaseModel):
    user_id: str = "default_user"

# Naya Task Update Request Model
class TaskUpdate(BaseModel):
    user_id: str = "default_user"
    day_number: int
    task_index: int
    completed: bool

# Duration add kiya taaki frontend par saaf dikhe
TASKS_LIST = [
    {"task": "Morning: Wake, Meditate, College", "time": "06:00", "duration": 60},
    {"task": "Evening: Gym Warfare (1h 45m)", "time": "17:00", "duration": 105},
    {"task": "Night: Trading, Aptitude, Coding", "time": "21:00", "duration": 120},
    {"task": "Late Night: Content Creation", "time": "23:00", "duration": 60}
]

@app.get("/")
async def health():
    try:
        await client.admin.command('ping')
        return {"status": "Online", "database": "Connected ✅"}
    except Exception as e:
        return {"status": "Online", "database": f"Error: {str(e)} ❌"}

@app.get("/api/challenge/current")
async def get_current_status(user_id: str = "default_user"):
    try:
        user = await users_collection.find_one({"user_id": user_id})
        if not user:
            return {"active": False}
        
        today_date = datetime.now()
        today_str = today_date.strftime("%Y-%m-%d")
        day_of_week = today_date.strftime("%A")
        is_sunday = day_of_week == "Sunday"
        
        # Calculate Current Day
        start_date_str = user.get("start_date", today_date.isoformat())
        start_date = datetime.fromisoformat(start_date_str)
        current_day = max(1, (today_date - start_date).days + 1)

        history = user.get("history", {})
        completed_today = history.get(today_str, [])

        tasks_response = []
        for idx, t in enumerate(TASKS_LIST):
            tasks_response.append({
                "task": t["task"], 
                "time": t["time"], 
                "duration": t["duration"],
                "completed": idx in completed_today
            })
        
        completion_percentage = 100.0 if is_sunday else (len(completed_today) / len(TASKS_LIST) * 100)

        # EXACT Data jo tumhare dashboard.tsx ko chahiye!
        return {
            "active": True,
            "challenge": {
                "current_day": current_day,
                "current_rank": "E",
                "current_level": 1,
                "stats": {"strength": 10, "vitality": 10, "agility": 10, "recovery": 10},
                "start_date": start_date_str
            },
            "today": {
                "day_number": current_day,
                "date": today_str,
                "day_of_week": day_of_week,
                "tasks": tasks_response,
                "completion_percentage": completion_percentage,
                "is_sunday": is_sunday
            }
        }
    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.post("/api/challenge/start")
async def start_challenge(req: StartRequest):
    try:
        existing = await users_collection.find_one({"user_id": req.user_id})
        if existing:
            return {"error": "Already started"} # Frontend ab isko pakad lega!

        new_user = {
            "user_id": req.user_id,
            "start_date": datetime.now().isoformat(),
            "active": True,
            "history": {}
        }
        await users_collection.insert_one(new_user)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# NAYA ENDPOINT: Task ko tick/untick karne ke liye
@app.post("/api/challenge/task")
async def update_task(req: TaskUpdate):
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        user = await users_collection.find_one({"user_id": req.user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        history = user.get("history", {})
        completed_today = history.get(today_str, [])
        
        if req.completed and req.task_index not in completed_today:
            completed_today.append(req.task_index)
        elif not req.completed and req.task_index in completed_today:
            completed_today.remove(req.task_index)
            
        history[today_str] = completed_today
        completion_percentage = (len(completed_today) / len(TASKS_LIST)) * 100
        
        await users_collection.update_one(
            {"user_id": req.user_id}, 
            {"$set": {"history": history}}
        )
        return {"success": True, "completion_percentage": completion_percentage}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# NAYA ENDPOINT: Stats page ke liye
@app.get("/api/challenge/history")
async def get_history(user_id: str = "default_user", days: int = 30):
    # Dummy data taaki stats page crash na ho
    return {"history": []}