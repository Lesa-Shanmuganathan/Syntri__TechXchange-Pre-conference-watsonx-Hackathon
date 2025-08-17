# db.py
import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client['syntri']

# collections
conversations = db['conversations']
financial_records = db['financial_records']
media_inputs = db['media_inputs']
risk_events = db['risk_events']
action_tasks = db['action_tasks']
voice_transcripts = db['voice_transcripts']
