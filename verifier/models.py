from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
import datetime
Base = declarative_base()

class Receipt(Base):
    __tablename__ = 'receipts'
    id = Column(Integer, primary_key=True)
    job_id = Column(String(128), nullable=False, unique=True)
    operator = Column(String(128))
    device = Column(Text)
    method = Column(String(64))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    signature = Column(Text)
    signed_json = Column(Text)
    raw_payload = Column(Text)
    pdf_path = Column(String(512))
    status = Column(String(32), default='created')
    email = Column(String(256))
