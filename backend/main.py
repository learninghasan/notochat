import os
from typing import Literal
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

class Base(DeclarativeBase): pass
class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer: Mapped[str] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(30))
    mode: Mapped[str] = mapped_column(default="ai")
class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(String(8000))
class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    price: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer)

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./inbox.db"))
def create_workspace(engine, trusted_identity=False, seed_sample=True):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        if seed_sample and os.getenv("SEED_SAMPLE_DATA", "1" if str(engine.url).startswith("sqlite") else "0") == "1" and not s.scalar(select(Conversation.id).limit(1)):
            s.add_all([Conversation(id=1, customer="রাফি আহমেদ", channel="Messenger"), Conversation(id=2, customer="নুসরাত জাহান", channel="Website"), Conversation(id=3, customer="সাদিয়া রহমান", channel="Instagram", mode="human")])
            s.add_all([Message(conversation_id=1, role="customer", text="পাঞ্জাবিটার দাম কত? ৪২ সাইজ আছে?"), Message(conversation_id=2, role="customer", text="ঢাকায় ডেলিভারি কত দিনে হবে?"), Message(conversation_id=3, role="customer", text="আমার অর্ডারটা এক্সচেঞ্জ করতে চাই।")])
            s.add_all([Product(name="Ivory Panjabi · 42",price=2450,stock=12),Product(name="Navy Linen Shirt · L",price=1390,stock=8)])
            s.commit()
    app = FastAPI(title="NotoChat", version="0.2.0")
    app.state.engine=engine
    security = HTTPBearer(auto_error=False)
    def authorize(request: Request, auth: HTTPAuthorizationCredentials | None = Depends(security)):
        if trusted_identity:
            principal=request.scope.get("notochat.principal")
            if not principal:raise HTTPException(401,"Verified business session required")
            if principal.get("role") not in ("owner","admin") and request.method not in ("GET","HEAD"):
                allowed=request.url.path.startswith(("/conversations","/orders","/leads","/bookings","/notifications/","/push/"))
                if not allowed:raise HTTPException(403,"Owner or admin permission required")
            return principal
        token = os.getenv("APP_TOKEN")
        if not token: raise HTTPException(503, "Set APP_TOKEN on the server before using the API")
        import secrets
        if not auth or not secrets.compare_digest(auth.credentials, token): raise HTTPException(401, "Invalid access token")
    def session(request:Request):
        with Session(engine) as s:
            cleanup=app.state.configure_access(s,request.scope.get("notochat.principal")) if hasattr(app.state,"configure_access") else None
            try:yield s
            finally:
                if cleanup:cleanup()
    class Reply(BaseModel):
        text: str = Field(min_length=1, max_length=8000)
    class NewConversation(BaseModel):
        customer: str = Field(min_length=1,max_length=120)
        channel: Literal["Messenger","Instagram","WhatsApp","Facebook comments","Website"] = "Website"
    class Mode(BaseModel):
        mode: Literal["ai", "human"]
    def conversation(s, cid):
        c = s.get(Conversation,cid)
        if not c: raise HTTPException(404,"Conversation not found")
        return c
    @app.get("/health")
    def health(): return {"status":"ok", "scope":"isolated business workspace" if trusted_identity else "legacy single workspace"}
    @app.get("/conversations", dependencies=[Depends(authorize)])
    def conversations(s:Session=Depends(session)):
        app.state.expire_handovers(s)
        return [{"id":c.id,"customer":c.customer,"channel":c.channel,"mode":c.mode} for c in s.scalars(select(Conversation).order_by(Conversation.id))]
    @app.post("/conversations",dependencies=[Depends(authorize)])
    def create_conversation(body:NewConversation,s:Session=Depends(session)):
        if not body.customer.strip():raise HTTPException(422,"Customer name is required")
        c=Conversation(customer=body.customer.strip(),channel=body.channel,mode="human")
        s.add(c);s.commit()
        return {"id":c.id,"customer":c.customer,"channel":c.channel,"mode":c.mode}
    @app.get("/conversations/{cid}/messages", dependencies=[Depends(authorize)])
    def messages(cid:int,s:Session=Depends(session)):
        conversation(s,cid)
        return [{"id":m.id,"role":m.role,"text":m.text,"verified_comment":bool((proof:=s.get(Base.WorkspaceRecord,f"verified_message:{m.id}")) and proof.data.get("channel")=="Facebook comments")} for m in s.scalars(select(Message).where(Message.conversation_id==cid).order_by(Message.id))]
    @app.post("/conversations/{cid}/messages", dependencies=[Depends(authorize)])
    def reply(cid:int,body:Reply,s:Session=Depends(session)):
        c=conversation(s,cid)
        if c.mode != "human": raise HTTPException(409,"Take over the conversation before replying")
        if not body.text.strip(): raise HTTPException(422,"Message cannot be blank")
        message=Message(conversation_id=cid,role="team",text=body.text.strip());s.add(message);s.flush()
        if c.channel=="Website":app.state.record_reply(s,cid,message.id)
        s.commit()
        return {"saved":True,"delivery":"local-only; channel not connected"}
    @app.patch("/conversations/{cid}/mode", dependencies=[Depends(authorize)])
    def mode(cid:int,body:Mode,s:Session=Depends(session)):
        c=conversation(s,cid); c.mode=body.mode
        if body.mode=="ai": app.state.clear_handover(s,cid)
        s.commit(); return {"mode":c.mode}
    @app.get("/products", dependencies=[Depends(authorize)])
    def products(s:Session=Depends(session)):
        return [{"id":p.id,"name":p.name,"price":p.price,"stock":p.stock} for p in s.scalars(select(Product))]
    @app.post("/conversations/{cid}/draft", dependencies=[Depends(authorize)])
    async def draft(cid:int,s:Session=Depends(session)):
        from workspace import AssistantInput
        return await app.state.assistant(cid,AssistantInput(action="draft"),s)

    from workspace import install
    install(app, engine, Base, Conversation, Message, Product, authorize, session, tenant=trusted_identity)
    return app

app=create_workspace(engine)
