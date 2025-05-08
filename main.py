from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Literal
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os

load_dotenv()

# Firebase initialization
cred_dict = {
    "type": os.getenv("google_credentials_type"),
    "project_id": os.getenv("project_id"),
    "private_key_id": os.getenv("private_key_id"),
    "private_key": os.getenv("private_key").replace("\\n", "\n"),
    "client_email": os.getenv("client_email"),
    "client_id": os.getenv("client_id"),
    "auth_uri": os.getenv("auth_uri"),
    "token_uri": os.getenv("token_uri"),
    "auth_provider_x509_cert_url": os.getenv("auth_provider_x509_cert_url"),
    "client_x509_cert_url": os.getenv("client_x509_cert_url"),
    "universe_domain": os.getenv("universe_domain")
}

cred = credentials.Certificate(cred_dict)

# Only initialize if not already initialized (prevents error during reload)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://iot-project-afca0-default-rtdb.firebaseio.com/'
    })

app = FastAPI()

# === Models ===
FilterType = Literal[
    "alkaline_filter", "carbon_filter", "pre_filter", "ro_filter", "sediment_filter"
]



# === 1. Sensor Metadata Setup ===
class SensorMetadata(BaseModel):
    user_id: str
    filter_type: FilterType
    sensor_id: str
    sensor_name: str

@app.post("/init_sensor/")
def init_sensor(meta: SensorMetadata):
    try:
        path = f"users/{meta.user_id}/{meta.filter_type}/{meta.sensor_id}"
        ref = db.reference(path)
        ref.set({
            "sensor_name": meta.sensor_name,
            "readings": {}
        })
        return {"message": "Sensor initialized successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === 2. Time-Series Data Upload (Batch for Multiple Filters and Sensors) ===
class SingleReading(BaseModel):
    sensor_id: str
    timestamp: str
    value: str

class FilterReadings(BaseModel):
    filter_type: FilterType
    readings: List[SingleReading]

class BatchSensorUpload(BaseModel):
    user_id: str
    filters: List[FilterReadings]

# === Background Task Function ===
def process_sensor_data_batch(data: BatchSensorUpload):
    update_data = {}

    for filter_data in data.filters:
        for reading in filter_data.readings:
            key_path = f"{data.user_id}/{filter_data.filter_type}/{reading.sensor_id}/readings/{reading.timestamp}"
            update_data[key_path] = reading.value

    root_ref = db.reference("users")
    root_ref.update(update_data)

# === API Endpoint ===
@app.post("/upload_batch_sensor_values/")
def upload_batch_sensor_values(data: BatchSensorUpload, background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(process_sensor_data_batch, data)
        return {"message": "Batch upload started in background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
