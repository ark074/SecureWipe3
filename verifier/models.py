from mongoengine import Document, StringField, DateTimeField
import datetime

class Receipt(Document):
    """
    MongoEngine document for receipts. Uses MongoDB's default ObjectId as the primary key.
    The job_id field is unique and used throughout the application to lookup receipts.
    """
    meta = {"collection": "receipts", "indexes": ["job_id"]}

    job_id = StringField(required=True, unique=True, max_length=128)
    operator = StringField(max_length=128)
    device = StringField()  # long text supported
    method = StringField(max_length=64)
    timestamp = DateTimeField(default=datetime.datetime.utcnow)
    signature = StringField()
    signed_json = StringField()
    raw_payload = StringField()
    pdf_path = StringField(max_length=512)
    status = StringField(default="created", max_length=32)
    email = StringField(max_length=256)
