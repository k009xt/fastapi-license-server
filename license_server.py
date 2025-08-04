# license_server.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# Настройка базы данных (SQLite)
DATABASE_URL = "sqlite:///licenses.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class LicenseDB(Base):
    __tablename__ = "licenses"
    license_key = Column(String, primary_key=True)
    customer_id = Column(Integer)
    expiration_date = Column(DateTime)
    is_active = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)

class LicenseVerifyRequest(BaseModel):
    license_key: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/license/verify")
async def verify_license(request: LicenseVerifyRequest, db: Session = Depends(get_db)):
    license = db.query(LicenseDB).filter(LicenseDB.license_key == request.license_key).first()
    if not license:
        raise HTTPException(status_code=400, detail="Недействительный лицензионный ключ")
    if not license.is_active:
        raise HTTPException(status_code=403, detail="Лицензия деактивирована")
    if license.expiration_date < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Срок лицензии истёк")
    return {
        "status": "valid",
        "license_key": license.license_key,
        "expiration_date": license.expiration_date.isoformat(),
        "is_active": license.is_active
    }