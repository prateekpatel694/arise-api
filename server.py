from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
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
    {"task": "Utho & 1 Glass Paani", "time": "07:30", "duration": 5},
    {"task": "Quick Fresh & Meditation", "time": "07:35", "duration": 15},
    {"task": "Shower, Breakfast & Ready", "time": "07:45", "duration": 45},
    {"task": "Commute to College", "time": "08:30", "duration": 30},
    {"task": "COLLEGE HOURS + Lunch Missions", "time": "09:00", "duration": 495},
    {"task": "Ghar wapsi + Gear up", "time": "17:15", "duration": 15},
    {"task": "GYM WARFARE (Push limits!)", "time": "17:30", "duration": 105},
    {"task": "Shower & Fresh", "time": "19:15", "duration": 30},
    {"task": "Hair Oiling + Immunity Drink", "time": "19:45", "duration": 30},
    {"task": "Dinner (Recovery fuel)", "time": "20:15", "duration": 30},
    {"task": "Power Break / Mental Prep", "time": "20:45", "duration": 15},
    {"task": "TRADING (Sniper focus)", "time": "21:00", "duration": 60},
    {"task": "APTITUDE STUDY", "time": "22:00", "duration": 60},
    {"task": "CODING (Deep Work Mode: ON)", "time": "23:00", "duration": 120},
    {"task": "CONTENT CREATION", "time": "01:00", "duration": 60},
    {"task": "Brush & Sleep Prep", "time": "02:00", "duration": 10}
]

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
    else: return "F" # <30% par seedha F rank

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
        
        start_date_str = user.get("start_date")
        start_date = datetime.fromisoformat(start_date_str)
        current_day = max(1, (ist_now.date() - start_date.date()).days + 1)

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

        total_tasks_done = sum(len(tasks) for tasks in history.values())
        current_level = 1 + (total_tasks_done // 5) 
        
        active_days = len(history) if len(history) > 0 else 1
        avg_completion = (total_tasks_done / (active_days * len(TASKS_LIST))) * 100
        current_rank = calculate_rank(avg_completion)
        
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
                "current_rank": current_rank,
                "current_level": current_level,
                "stats": stats,
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
        raise HTTPException(status_code=500, detail="Sync failed")

@app.post("/api/challenge/start")
async def start_challenge(req: StartRequest):
    try:
        ist_now = get_ist_time()
        existing = await users_collection.find_one({"user_id": req.user_id})
        if existing:
            await users_collection.update_one({"user_id": req.user_id}, {"$set": {"active": True}})
        else:
            new_user = {
                "user_id": req.user_id,
                "start_date": ist_now.isoformat(),
                "active": True,
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
            completed_today.remove(req.task_index)
            
        history[today_str] = completed_today
        await users_collection.update_one({"user_id": req.user_id}, {"$set": {"history": history}})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/challenge/history")
async def get_history(user_id: str = "default_user", days: int = 30):
    try:
        user = await users_collection.find_one({"user_id": user_id})
        if not user:
            return {"history": []}
        
        history_dict = user.get("history", {})
        formatted_history = []
        
        for date_str, tasks in history_dict.items():
            completion_percentage = (len(tasks) / len(TASKS_LIST)) * 100
            formatted_history.append({
                "date": date_str,
                "completion_percentage": completion_percentage
            })
        
        formatted_history.sort(key=lambda x: x["date"])
        return {"history": formatted_history[-days:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))