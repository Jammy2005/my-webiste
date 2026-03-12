from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from my_agent.agent import agent

app = FastAPI()

# Enable CORS (important if you have a frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema
class MessageRequest(BaseModel):
    message: str

# Root route
@app.get("/")
async def root():
    return {"status": "API running"}


@app.post("/chat")
async def chat(req: MessageRequest):
    response = agent.invoke({"messages":req.message})
    return {"response": f"ChatBot: {response}"}
