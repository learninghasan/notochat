import os
import tempfile
os.environ["DATABASE_URL"]="sqlite:///"+tempfile.mktemp(suffix=".db")
os.environ["APP_TOKEN"]="test-token"
from fastapi.testclient import TestClient
from main import app
client=TestClient(app)
headers={"Authorization":"Bearer test-token"}
def test_unauthorized():
    assert client.get("/conversations").status_code==401

def test_handover_reply_and_return():
    assert client.post("/conversations/1/messages",headers=headers,json={"text":"hello"}).status_code==409
    assert client.patch("/conversations/1/mode",headers=headers,json={"mode":"human"}).status_code==200
    r=client.post("/conversations/1/messages",headers=headers,json={"text":"ধন্যবাদ"})
    assert r.status_code==200 and "local-only" in r.json()["delivery"]
    assert client.get("/conversations/1/messages",headers=headers).json()[-1]["text"]=="ধন্যবাদ"
    assert client.patch("/conversations/1/mode",headers=headers,json={"mode":"ai"}).status_code==200

def test_missing_conversation_and_invalid_mode():
    assert client.get("/conversations/999/messages",headers=headers).status_code==404
    assert client.patch("/conversations/1/mode",headers=headers,json={"mode":"admin"}).status_code==422

def test_ai_fails_clearly_without_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    assert client.post("/conversations/1/draft",headers=headers).status_code==503
