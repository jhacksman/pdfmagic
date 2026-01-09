from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
import io
import zipfile
import tempfile
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from contextlib import contextmanager

from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import stripe
import jwt
import bcrypt
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="PDFMagic API", version="1.0.0")

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_BUSINESS = os.getenv("STRIPE_PRICE_BUSINESS", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/app.db")

# Initialize Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Password hashing helpers
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Tier limits
TIER_LIMITS = {
    "free": {"daily_ops": 3, "max_file_mb": 5},
    "pro": {"daily_ops": 1000, "max_file_mb": 50},
    "business": {"daily_ops": 10000, "max_file_mb": 100},
}

# Database setup
def get_db_path():
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return DATABASE_PATH

@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                tier TEXT DEFAULT 'free',
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                operation_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()

@app.on_event("startup")
async def startup():
    init_db()

# Pydantic models
class UserRegister(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: str
    tier: str
    daily_ops_remaining: int
    max_file_mb: int

class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str

# Auth helpers
def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    user_id = verify_token(token)
    if not user_id:
        return None
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(user) if user else None

async def require_user(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def get_daily_ops_count(user_id: int) -> int:
    with get_db() as conn:
        today = datetime.utcnow().date().isoformat()
        result = conn.execute(
            "SELECT COUNT(*) FROM operations WHERE user_id = ? AND date(created_at) = ?",
            (user_id, today)
        ).fetchone()
        return result[0] if result else 0

def record_operation(user_id: int, operation_type: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO operations (user_id, operation_type) VALUES (?, ?)",
            (user_id, operation_type)
        )
        conn.commit()

def check_limits(user: dict, file_size_bytes: int) -> bool:
    tier = user.get("tier", "free")
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    
    # Check file size
    max_bytes = limits["max_file_mb"] * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Max size for {tier} tier: {limits['max_file_mb']}MB"
        )
    
    # Check daily operations
    daily_ops = get_daily_ops_count(user["id"])
    if daily_ops >= limits["daily_ops"]:
        raise HTTPException(
            status_code=429, 
            detail=f"Daily operation limit reached. Upgrade to increase your limit."
        )
    
    return True

# Auth endpoints
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(data: UserRegister):
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        password_hash = hash_password(data.password)
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (data.email, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        
    token = create_token(user_id)
    return TokenResponse(access_token=token)

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (data.email,)).fetchone()
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
    token = create_token(user["id"])
    return TokenResponse(access_token=token)

@app.get("/api/user/me", response_model=UserResponse)
async def get_me(user: dict = Depends(require_user)):
    tier = user.get("tier", "free")
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    daily_ops = get_daily_ops_count(user["id"])
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        tier=tier,
        daily_ops_remaining=max(0, limits["daily_ops"] - daily_ops),
        max_file_mb=limits["max_file_mb"]
    )

# PDF Operations
@app.post("/api/pdf/merge")
async def merge_pdfs(
    files: List[UploadFile] = File(...),
    user: dict = Depends(require_user)
):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 PDF files to merge")
    
    total_size = 0
    pdf_contents = []
    
    for file in files:
        content = await file.read()
        total_size += len(content)
        pdf_contents.append(content)
    
    check_limits(user, total_size)
    
    try:
        writer = PdfWriter()
        for content in pdf_contents:
            reader = PdfReader(io.BytesIO(content))
            for page in reader.pages:
                writer.add_page(page)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        record_operation(user["id"], "merge")
        
        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDFs: {str(e)}")

@app.post("/api/pdf/split")
async def split_pdf(
    file: UploadFile = File(...),
    user: dict = Depends(require_user)
):
    content = await file.read()
    check_limits(user, len(content))
    
    try:
        reader = PdfReader(io.BytesIO(content))
        
        # Create a zip file with individual pages
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                page_buffer = io.BytesIO()
                writer.write(page_buffer)
                page_buffer.seek(0)
                zip_file.writestr(f"page_{i+1}.pdf", page_buffer.read())
        
        zip_buffer.seek(0)
        record_operation(user["id"], "split")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=split_pages.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

@app.post("/api/pdf/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    user: dict = Depends(require_user)
):
    content = await file.read()
    check_limits(user, len(content))
    
    try:
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()
        
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        
        # Remove unused objects
        writer.add_metadata(reader.metadata or {})
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        record_operation(user["id"], "compress")
        
        original_size = len(content)
        compressed_size = len(output.getvalue())
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=compressed.pdf",
                "X-Original-Size": str(original_size),
                "X-Compressed-Size": str(compressed_size)
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

@app.post("/api/pdf/to-images")
async def pdf_to_images(
    file: UploadFile = File(...),
    user: dict = Depends(require_user)
):
    content = await file.read()
    check_limits(user, len(content))
    
    try:
        reader = PdfReader(io.BytesIO(content))
        
        # Create a zip file with images
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, page in enumerate(reader.pages):
                # Extract images from page
                if '/XObject' in page['/Resources']:
                    x_objects = page['/Resources']['/XObject'].get_object()
                    img_count = 0
                    for obj_name in x_objects:
                        obj = x_objects[obj_name]
                        if obj['/Subtype'] == '/Image':
                            try:
                                size = (obj['/Width'], obj['/Height'])
                                data = obj.get_data()
                                
                                if obj['/ColorSpace'] == '/DeviceRGB':
                                    mode = "RGB"
                                else:
                                    mode = "P"
                                
                                img = Image.frombytes(mode, size, data)
                                img_buffer = io.BytesIO()
                                img.save(img_buffer, format='PNG')
                                img_buffer.seek(0)
                                zip_file.writestr(f"page_{i+1}_img_{img_count+1}.png", img_buffer.read())
                                img_count += 1
                            except Exception:
                                continue
        
        zip_buffer.seek(0)
        record_operation(user["id"], "pdf_to_images")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=extracted_images.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

@app.post("/api/images/to-pdf")
async def images_to_pdf(
    files: List[UploadFile] = File(...),
    user: dict = Depends(require_user)
):
    if len(files) < 1:
        raise HTTPException(status_code=400, detail="Need at least 1 image file")
    
    total_size = 0
    images = []
    
    for file in files:
        content = await file.read()
        total_size += len(content)
        try:
            img = Image.open(io.BytesIO(content))
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            images.append(img)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image file: {file.filename}")
    
    check_limits(user, total_size)
    
    try:
        output = io.BytesIO()
        if len(images) == 1:
            images[0].save(output, format='PDF')
        else:
            images[0].save(output, format='PDF', save_all=True, append_images=images[1:])
        
        output.seek(0)
        record_operation(user["id"], "images_to_pdf")
        
        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=images.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating PDF: {str(e)}")

# Stripe endpoints
@app.post("/api/stripe/create-checkout")
async def create_checkout(
    data: CheckoutRequest,
    user: dict = Depends(require_user)
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        # Get or create Stripe customer
        customer_id = user.get("stripe_customer_id")
        if not customer_id:
            customer = stripe.Customer.create(email=user["email"])
            customer_id = customer.id
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                    (customer_id, user["id"])
                )
                conn.commit()
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": data.price_id, "quantity": 1}],
            mode="subscription",
            success_url=data.success_url,
            cancel_url=data.cancel_url,
            metadata={"user_id": str(user["id"])}
        )
        
        return {"checkout_url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        subscription_id = session.get("subscription")
        
        if user_id and subscription_id:
            # Get subscription to determine tier
            subscription = stripe.Subscription.retrieve(subscription_id)
            price_id = subscription["items"]["data"][0]["price"]["id"]
            
            if price_id == STRIPE_PRICE_PRO:
                tier = "pro"
            elif price_id == STRIPE_PRICE_BUSINESS:
                tier = "business"
            else:
                tier = "pro"
            
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET tier = ?, stripe_subscription_id = ? WHERE id = ?",
                    (tier, subscription_id, int(user_id))
                )
                conn.commit()
    
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET tier = 'free', stripe_subscription_id = NULL WHERE stripe_subscription_id = ?",
                (subscription_id,)
            )
            conn.commit()
    
    return {"status": "success"}

@app.post("/api/stripe/portal")
async def create_portal(user: dict = Depends(require_user)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No subscription found")
    
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=os.getenv("FRONTEND_URL", "http://localhost:5173")
        )
        return {"portal_url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/pricing")
async def get_pricing():
    return {
        "tiers": [
            {
                "name": "Free",
                "price": 0,
                "features": [
                    "3 operations per day",
                    "Max 5MB file size",
                    "All PDF tools"
                ]
            },
            {
                "name": "Pro",
                "price": 9.99,
                "price_id": STRIPE_PRICE_PRO,
                "features": [
                    "1,000 operations per day",
                    "Max 50MB file size",
                    "All PDF tools",
                    "Priority support"
                ]
            },
            {
                "name": "Business",
                "price": 24.99,
                "price_id": STRIPE_PRICE_BUSINESS,
                "features": [
                    "10,000 operations per day",
                    "Max 100MB file size",
                    "All PDF tools",
                    "Priority support",
                    "API access"
                ]
            }
        ]
    }

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
