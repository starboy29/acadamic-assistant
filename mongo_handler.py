# mongo_handler.py

import os
import gridfs
from pymongo import MongoClient
from config import MONGO_URI
from datetime import datetime

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["academic_notes"]  # 🔁 database name
fs = gridfs.GridFS(db)

def save_pdf(file_bytes, filename, metadata):
    """
    Save a PDF file with metadata into MongoDB GridFS.
    """
    file_id = fs.put(file_bytes, filename=filename, metadata=metadata)
    print(f"📦 File saved to DB with ID: {file_id}")
    return str(file_id)

def get_pdfs_by_metadata(subject, chapter):
    """
    Retrieve all PDF files matching subject and chapter from GridFS.
    Returns a list of (filename, file_bytes) tuples.
    """
    files = fs.find({
        "metadata.subject": subject,
        "metadata.chapter": chapter
    })

    results = []
    for file in files:
        try:
            results.append((file.filename, file.read()))
        except Exception as e:
            print(f"⚠️ Error reading file: {e}")
    return results
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






