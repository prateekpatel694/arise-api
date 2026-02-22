from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta # Timezone ke liye zaroori
import motor.motor_asyncio

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

class TaskUpdate(BaseModel):
    user_id: str = "default_user"
    day_number: int
    task_index: int
    completed: bool

TASKS_LIST = [
    {"task": "Morning: Wake, Meditate, College", "time": "06:00", "duration": 60},
    {"task": "Evening: Gym Warfare (1h 45m)", "time": "17:00", "duration": 105},
    {"task": "Night: Trading, Aptitude, Coding", "time": "21:00", "duration": 120},
    {"task": "Late Night: Content Creation", "time": "23:00", "duration": 60}
]

# Helper function to get India Time (IST)
def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

@app.get("/")
async def health():
    try:
        await client.admin.command('ping')
        return {"status": "Online", "database": "Connected ✅", "server_time_ist": get_ist_time().isoformat()}
    except Exception as e:
        return {"status": "Online", "database": f"Error: {str(e)} ❌"}

@app.get("/api/challenge/current")
async def get_current_status(user_id: str = "default_user"):
    try:
        user = await users_collection.find_one({"user_id": user_id})
        if not user:
            return {"active": False}
        
        ist_now = get_ist_time()
        today_str = ist_now.strftime("%Y-%m-%d")
        day_of_week = ist_now.strftime("%A")
        is_sunday = day_of_week == "Sunday"
        
        # Start date handling
        start_date_str = user.get("start_date")
        start_date = datetime.fromisoformat(start_date_str)
        
        # Calculate Current Day strictly by date difference
        current_day = (ist_now.date() - start_date.date()).days + 1
        current_day = max(1, current_day)

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

        return {
            "active": True,
            "challenge": {
                "current_day": current_day,
                "current_rank": user.get("rank", "E"),
                "current_level": user.get("level", 1),
                "stats": user.get("stats", {"strength": 10, "vitality": 10, "agility": 10, "recovery": 10}),
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
        raise HTTPException(status_code=500, detail="Sync failed")

@app.post("/api/challenge/start")
async def start_challenge(req: StartRequest):
    try:
        ist_now = get_ist_time()
        existing = await users_collection.find_one({"user_id": req.user_id})
        
        if existing:
            # Re-activate if it was inactive
            await users_collection.update_one(
                {"user_id": req.user_id},
                {"$set": {"active": True, "start_date": ist_now.isoformat()}}
            )
        else:
            new_user = {
                "user_id": req.user_id,
                "start_date": ist_now.isoformat(),
                "active": True,
                "rank": "E",
                "level": 1,
                "stats": {"strength": 10, "vitality": 10, "agility": 10, "recovery": 10},
                "history": {}
            }
            await users_collection.insert_one(new_user)
        return {"success": True}
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
        completed_today = history.get(today_str, [])
        
        if req.completed and req.task_index not in completed_today:
            completed_today.append(req.task_index)
        elif not req.completed and req.task_index in completed_today:
            if req.task_index in completed_today:
                completed_today.remove(req.task_index)
            
        history[today_str] = completed_today
        
        await users_collection.update_one(
            {"user_id": req.user_id}, 
            {"$set": {"history": history}}
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/challenge/history")
async def get_history(user_id: str = "default_user", days: int = 30):
    user = await users_collection.find_one({"user_id": user_id})
    return {"history": user.get("history", {}) if user else {}}