import os
import uuid
import datetime
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import gspread
from google.oauth2.service_account import Credentials

# ====== Настройки ======
API_KEY = "SUPER_SECRET_ADMIN_KEY_12345"  # Ключ для админских операций
LICENSE_DAYS = 30  # Срок действия лицензии
GRACE_DAYS = 5     # Период ожидания после окончания

# Подключение к Google Sheets
SERVICE_ACCOUNT_FILE = "service_account.json"  # Файл с твоими данными
SPREADSHEET_NAME = "licenses"                  # Имя таблицы
SHEET = None

def connect_sheet():
    global SHEET
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    SHEET = client.open(SPREADSHEET_NAME).sheet1

# ====== Модели ======
class RegisterRequest(BaseModel):
    product_name: str

class CheckRequest(BaseModel):
    client_id: str
    license_key: str

class UpdateRequest(BaseModel):
    api_key: str
    client_id: str
    extra_days: int

# ====== Запуск ======
app = FastAPI()

@app.on_event("startup")
def startup_event():
    connect_sheet()

# ====== API ======
@app.post("/register")
def register(data: RegisterRequest):
    client_id = str(uuid.uuid4())
    license_key = str(uuid.uuid4())
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=LICENSE_DAYS)).strftime("%Y-%m-%d")

    # Запись в таблицу
    SHEET.append_row([client_id, license_key, data.product_name, expires_at])

    return {
        "client_id": client_id,
        "license_key": license_key,
        "expires_at": expires_at
    }

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
