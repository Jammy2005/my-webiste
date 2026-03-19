from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from my_agent.agent import agent
# from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})



@app.post("/chat")
async def chat(req: MessageRequest):
    verbose_response = agent.invoke({"messages": [("user", req.message)]})
    print((verbose_response))
    print(verbose_response["messages"][-1].content)
    response = verbose_response["messages"][-1].content
    return {"response": f"ChatBot: {response}"}
