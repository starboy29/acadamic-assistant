# mongo_handler.py

import os
from pymongo import MongoClient
from config import MONGO_URI
from datetime import datetime

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["academic_notes"]  # 🔁 database name


def add_assignment(subject, chapter, topic, deadline_str, description):
    deadline = datetime.fromisoformat(deadline_str)  # e.g., '2025-06-22T23:59:00'
    assignment = {
        "subject": subject,
        "chapter": chapter,
        "topic": topic,
        "deadline": deadline,
        "description": description,
        "status": "Pending",
        "file_id": None
    }
    db.assignments.insert_one(assignment)
    return True


def store_file_metadata(subject, chapter, topic, filename, file_id, drive_link, category):
    metadata = {
        "subject": subject,
        "chapter": chapter,
        "topic": topic,
        "filename": filename,
        "file_id": file_id,
        "drive_link": drive_link,
        "category": category,
        "uploaded_at": datetime.utcnow()
    }
    db.files.insert_one(metadata)
    print(f"📄 Metadata saved for {filename}")

def get_notes_by_subject_and_chapter(subject, chapter):
    return list(db.files.find({
        "category": "Notes",
        "subject": {"$regex": subject, "$options": "i"},
        "chapter": {"$regex": chapter, "$options": "i"}
    }))




