from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from my_agent.agent import agent
from fastapi.responses import FileResponse

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
async def serve_frontend():
    return FileResponse("index.html")



@app.post("/chat")
async def chat(req: MessageRequest):
    verbose_response = agent.invoke({"messages": [("user", req.message)]})
    print((verbose_response))
    print(verbose_response["messages"][-1].content)
    response = verbose_response["messages"][-1].content
    return {"response": f"ChatBot: {response}"}
