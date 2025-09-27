from mongoengine import Document, StringField, DateTimeField, IntField, DictField
import datetime

class Receipt(Document):
    meta = {"collection": "receipts"}
    
    id = IntField(primary_key=True)
    job_id = StringField(required=True, unique=True, max_length=128)
    operator = StringField(max_length=128)
    device = StringField()  # Text -> just use StringField (MongoDB supports large strings)
    method = StringField(max_length=64)
    timestamp = DateTimeField(default=datetime.datetime.utcnow)
    signature = StringField()
    signed_json = StringField()
    raw_payload = StringField()
    pdf_path = StringField(max_length=512)
    status = StringField(default="created", max_length=32)
    email = StringField(max_length=256)
