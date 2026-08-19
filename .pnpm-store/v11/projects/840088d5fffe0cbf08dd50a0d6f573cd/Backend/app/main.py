from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from app.core.database import Base, engine
from app.api import auth, projects, workspaces
# import models to ensure they are registered with Base
from app.models import user, project, document, review

load_dotenv()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Refyne AI Backend")

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(workspaces.router)
from app.api import documents
app.include_router(documents.router)
from app.api import retrieval
app.include_router(retrieval.router)
from app.api import document_generation
app.include_router(document_generation.router)
from app.api import supervisor
app.include_router(supervisor.router)
from app.api import supervisor_chat
app.include_router(supervisor_chat.router)
from app.api import review
app.include_router(review.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
