import os, io, json
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import qrcode

PDF_OUT_DIR = os.environ.get('PDF_OUT_DIR', './data/pdfs')
os.makedirs(PDF_OUT_DIR, exist_ok=True)

def build_pdf_for_receipt(receipt_json: dict, signature_hex: str, job_id: str) -> str:
    filename = f"bitshred_{job_id}.pdf"
    path = os.path.join(PDF_OUT_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    margin = 50
    y = h - margin
    c.setFont('Helvetica-Bold', 20)
    c.drawString(margin, y, 'BitShred')
    c.setFont('Helvetica', 12)
    c.drawString(margin+120, y, 'Secure Data Wipe Certificate')
    y -= 40
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin, y, 'Device Information')
    c.drawString(w/2, y, 'Operator / Contact')
    y -= 16
    c.setFont('Helvetica', 10)
    dev = receipt_json.get('device') or {}
    c.drawString(margin, y, f"Model: {dev.get('model','-')}")
    c.drawString(w/2, y, f"Operator: {receipt_json.get('operator','-')}")
    y -= 14
    c.drawString(margin, y, f"Serial: {dev.get('serial','-')}")
    c.drawString(w/2, y, f"Email: {receipt_json.get('email','-')}")
    y -= 20
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin, y, 'Wipe Details')
    y -= 14
    c.setFont('Helvetica', 10)
    c.drawString(margin, y, f"Method: {receipt_json.get('method','auto')}")
    y -= 12
    c.drawString(margin, y, f"NIST Category: {receipt_json.get('nist_category','purge')}")
    y -= 20
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin, y, 'Evidence (sample)')
    y -= 14
    c.setFont('Helvetica', 9)
    ev = receipt_json.get('evidence',[])
    if ev:
        sample = ev[0]
        c.drawString(margin, y, f"Cmd: {sample.get('cmd')}")
        y -= 12
        out = sample.get('out','')[:200].replace('\n',' ')
        c.drawString(margin, y, f"Out: {out}")
        y -= 18
    else:
        c.drawString(margin, y, 'No evidence captured.')
        y -= 18
    c.setFont('Helvetica-Bold', 10)
    c.drawString(margin, y, 'Digital Signature:')
    y -= 12
    c.setFont('Helvetica', 8)
    c.drawString(margin, y, signature_hex[:120] + ('...' if len(signature_hex)>120 else ''))
    verifier = receipt_json.get('verifier','')
    if verifier:
        url = f"{verifier.rstrip('/')}/receipts/verify?job_id={job_id}"
    else:
        url = f"urn:bitshred:{job_id}"
    qr = qrcode.make(url)
    bio = io.BytesIO()
    qr.save(bio, format='PNG')
    bio.seek(0)
    c.drawInlineImage(bio, w - margin - 120, margin + 20, width=110, height=110)
    c.setFont('Helvetica-Oblique', 8)
    c.drawString(margin, margin+10, 'This certificate is digitally signed and verifiable via BitShred verifier.')
    c.save()
    return path
