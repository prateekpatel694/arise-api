from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import motor.motor_asyncio
import asyncio

app = FastAPI()

# --- REVISED CONFIGURATION ---
# Standard Format (Mobile Hotspot ke liye sabse best)
# Standard Connection String (Mobile Hotspot ke liye Bulletproof)
MONGO_URI = "mongodb://monar:king123@cluster0-shard-00-00.vytusx9.mongodb.net:27017,cluster0-shard-00-01.vytusx9.mongodb.net:27017,cluster0-shard-00-02.vytusx9.mongodb.net:27017/shadow_db?ssl=true&replicaSet=atlas-h1v0n8-shard-0&authSource=admin&retryWrites=true&w=majority"
# Connection Setup with Timeout
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

TASKS_LIST = [
    {"task": "Morning: Wake, Meditate, College", "time": "06:00"},
    {"task": "Evening: Gym Warfare (1h 45m)", "time": "17:00"},
    {"task": "Night: Trading, Aptitude, Coding", "time": "21:00"},
    {"task": "Late Night: Content Creation", "time": "23:00"}
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
            return {"active": False, "day": 0}
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        history = user.get("history", {})
        completed_today = history.get(today_str, [])

        tasks_response = []
        for idx, t in enumerate(TASKS_LIST):
            tasks_response.append({
                "task": t["task"], "time": t["time"], "completed": idx in completed_today
            })

        return {"active": True, "day": 1, "today": {"date": today_str, "tasks": tasks_response}}
    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.post("/api/challenge/start")
async def start_challenge(req: StartRequest):
    try:
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