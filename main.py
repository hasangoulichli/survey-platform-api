import os
import csv
from io import StringIO
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv

# .env dosyasını oku
load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI(title="KAPSA Survey Export API")

# Next.js arayüzünden gelen indirme isteklerine izin ver (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

@app.get("/")
def read_root():
    return {"durum": "basarili", "mesaj": "Survey API sunucusu aktif olarak calisiyor!"}

# URL'den gelen survey_id parametresini alıyoruz
@app.get("/export/csv/{survey_id}")
async def export_data(survey_id: str):
    """
    Sadece belirtilen anket ID'sine ait yanıtları çeker ve CSV olarak indirir.
    """
    # Veritabanında sadece o ankete (survey_id) ait olan satırları filtrele
    response = supabase.table("responses").select("*").eq("survey_id", survey_id).execute()
    data = response.data
    
    if not data:
        raise HTTPException(status_code=404, detail="Bu anket için henüz hiç yanıt bulunamadı.")
        
    flat_data = []
    all_keys = ["response_id", "session_id", "created_at"]
    dynamic_keys = set()
    
    for row in data:
        base_info = {
            "response_id": row.get("id"),
            "session_id": row.get("session_id"),
            "created_at": row.get("created_at")
        }
        
        payload = row.get("answer_payload", {})
        flat_payload = flatten_dict(payload)
        
        for k in flat_payload.keys():
            dynamic_keys.add(k)
            
        base_info.update(flat_payload)
        flat_data.append(base_info)
        
    fieldnames = all_keys + list(dynamic_keys)
        
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(flat_data)
    
    output.seek(0)
    
    # Dosya adını anket ID'sine göre özelleştir
    return StreamingResponse(
        output, 
        media_type="text/csv", 
        headers={"Content-Disposition": f"attachment; filename=anket_verisi_{survey_id}.csv"}
    )