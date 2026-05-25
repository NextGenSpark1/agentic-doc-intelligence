# Pipeline stages:
# classify → extract → resolve_entities → build_relationships
#   → reconstruct_timeline → detect_anomalies → summarise

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Investigation Intelligence API")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/cases")
async def create_case(body: dict):
    # TODO: validate with CaseSchema, persist to Supabase
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@app.post("/cases/{case_id}/documents")
async def upload_document(case_id: str, body: dict):
    # TODO: accept multipart upload, store in Supabase Storage, enqueue pipeline
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@app.post("/cases/{case_id}/chat")
async def chat(case_id: str, body: dict):
    # TODO: validate with ChatRequest, run RAG, return ChatResponse
    return JSONResponse(status_code=501, content={"detail": "not implemented"})
