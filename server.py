import os
import uuid
import datetime
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import gspread
from google.oauth2.service_account import Credentials

# ====== Конфигурация ======
API_KEY = os.getenv("ADMIN_API_KEY", "SUPER_SECRET_ADMIN_KEY_12345")
LICENSE_DAYS = 30
GRACE_DAYS = 5

SPREADSHEET_ID = "1cMVLTqMnJe_6LP9VmFPjW6dgJiFIY3RBU0OiMTi7SgI"
SHEET = None

def connect_sheet():
    global SHEET
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    print("Raw JSON:", raw)  # Добавьте эту строку для отладки
    service_account_info = json.loads(raw)
    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    SHEET = client.open_by_key(SPREADSHEET_ID).sheet1

# ====== Модели запросов ======
class RegisterRequest(BaseModel):
    product_name: str

class CheckRequest(BaseModel):
    client_id: str
    license_key: str

class UpdateRequest(BaseModel):
    api_key: str
    client_id: str
    extra_days: int

# ====== FastAPI ======
app = FastAPI()

@app.on_event("startup")
def startup_event():
    connect_sheet()

@app.post("/register")
def register(data: RegisterRequest):
    client_id = str(uuid.uuid4())
    license_key = str(uuid.uuid4())
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=LICENSE_DAYS)).strftime("%Y-%m-%d")
    SHEET.append_row([client_id, license_key, data.product_name, expires_at])
    return {"client_id": client_id, "license_key": license_key, "expires_at": expires_at}

@app.post("/check")
def check_license(data: CheckRequest):
    rows = SHEET.get_all_records()
    for row in rows:
        if row["client_id"] == data.client_id and row["license_key"] == data.license_key:
            expires_at = datetime.datetime.strptime(row["expires_at"], "%Y-%m-%d")
            now = datetime.datetime.utcnow()
            if now <= expires_at:
                return {"status": "valid", "expires_at": row["expires_at"]}
            elif now <= expires_at + datetime.timedelta(days=GRACE_DAYS):
                return {"status": "grace", "expires_at": row["expires_at"]}
            else:
                return {"status": "expired", "expires_at": row["expires_at"]}
    raise HTTPException(status_code=404, detail="License not found")

@app.post("/update")
def update_license(data: UpdateRequest):
    if data.api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    rows = SHEET.get_all_records()
    for idx, row in enumerate(rows, start=2):
        if row["client_id"] == data.client_id:
            expires_at = datetime.datetime.strptime(row["expires_at"], "%Y-%m-%d")
            new_expiry = (expires_at + datetime.timedelta(days=data.extra_days)).strftime("%Y-%m-%d")
            SHEET.update_cell(idx, 4, new_expiry)
            return {"status": "updated", "new_expires_at": new_expiry}
    raise HTTPException(status_code=404, detail="Client ID not found")
