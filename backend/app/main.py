from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request, BackgroundTasks
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
from urllib.parse import urlparse

from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import stripe
import jwt
import bcrypt
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import httpx
import sentry_sdk
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

load_dotenv()

# Initialize Sentry for error monitoring
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )

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
DATABASE_URL = os.getenv("DATABASE_URL", "")  # PostgreSQL connection string
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/app.db")  # SQLite fallback
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "")  # Your app's bundle ID

# Email Configuration (SendGrid)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@pdfmagic.app")

# Initialize Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Password hashing helpers
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Tier limits (Updated pricing: Pro $5, Business $25)
TIER_LIMITS = {
    "free": {"daily_ops": 3, "max_file_mb": 5},
    "pro": {"daily_ops": 100, "max_file_mb": 25},  # Reduced from 1000 to 100
    "business": {"daily_ops": 1000, "max_file_mb": 100},  # Reduced from 10000 to 1000
}

# Email helper functions
def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send email via SendGrid"""
    if not SENDGRID_API_KEY:
        print(f"SendGrid not configured, would send email to {to_email}: {subject}")
        return False
    
    try:
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        if SENTRY_DSN:
            sentry_sdk.capture_exception(e)
        return False

def send_welcome_email(email: str):
    """Send welcome email to new user"""
    html_content = f"""
    <h1>Welcome to PDFMagic!</h1>
    <p>Thanks for signing up. You can now use our PDF tools:</p>
    <ul>
        <li>Merge PDFs</li>
        <li>Split PDFs</li>
        <li>Compress PDFs</li>
        <li>Convert PDF to Images</li>
        <li>Convert Images to PDF</li>
    </ul>
    <p>Free users get 3 operations per day. <a href="{FRONTEND_URL}">Upgrade to Pro</a> for unlimited access!</p>
    <p>Best,<br>The PDFMagic Team</p>
    """
    send_email(email, "Welcome to PDFMagic!", html_content)

def send_password_reset_email(email: str, reset_token: str):
    """Send password reset email"""
    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
    html_content = f"""
    <h1>Reset Your Password</h1>
    <p>You requested a password reset for your PDFMagic account.</p>
    <p><a href="{reset_url}" style="background-color: #7c3aed; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Reset Password</a></p>
    <p>This link expires in 1 hour.</p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    <p>Best,<br>The PDFMagic Team</p>
    """
    send_email(email, "Reset Your PDFMagic Password", html_content)

# Database setup - supports both PostgreSQL and SQLite
USE_POSTGRES = bool(DATABASE_URL)

def get_db_path():
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return DATABASE_PATH

@contextmanager
def get_db():
    if USE_POSTGRES:
        import psycopg
        conn = psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

def init_db():
    with get_db() as conn:
        if USE_POSTGRES:
            # PostgreSQL schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    tier TEXT DEFAULT 'free',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    reset_token TEXT,
                    reset_token_expires TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    operation_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # SQLite schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    tier TEXT DEFAULT 'free',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    reset_token TEXT,
                    reset_token_expires TIMESTAMP,
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

class GoogleAuthRequest(BaseModel):
    id_token: str

class AppleAuthRequest(BaseModel):
    id_token: str
    user_info: Optional[dict] = None  # Apple only sends user info on first sign-in

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class UpdateProfileRequest(BaseModel):
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class MessageResponse(BaseModel):
    message: str

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
async def register(data: UserRegister, background_tasks: BackgroundTasks):
    placeholder = "%s" if USE_POSTGRES else "?"
    with get_db() as conn:
        existing = conn.execute(f"SELECT id FROM users WHERE email = {placeholder}", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        password_hash = hash_password(data.password)
        if USE_POSTGRES:
            cursor = conn.execute(
                f"INSERT INTO users (email, password_hash) VALUES ({placeholder}, {placeholder}) RETURNING id",
                (data.email, password_hash)
            )
            user_id = cursor.fetchone()["id"]
        else:
            cursor = conn.execute(
                f"INSERT INTO users (email, password_hash) VALUES ({placeholder}, {placeholder})",
                (data.email, password_hash)
            )
            user_id = cursor.lastrowid
        conn.commit()
    
    background_tasks.add_task(send_welcome_email, data.email)
    token = create_token(user_id)
    return TokenResponse(access_token=token)

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    placeholder = "%s" if USE_POSTGRES else "?"
    with get_db() as conn:
        user = conn.execute(f"SELECT * FROM users WHERE email = {placeholder}", (data.email,)).fetchone()
        if not user or not verify_password(data.password, dict(user)["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
    token = create_token(dict(user)["id"])
    return TokenResponse(access_token=token)

@app.post("/api/auth/forgot-password", response_model=MessageResponse)
async def forgot_password(data: PasswordResetRequest, background_tasks: BackgroundTasks):
    """Request a password reset email"""
    placeholder = "%s" if USE_POSTGRES else "?"
    with get_db() as conn:
        user = conn.execute(f"SELECT * FROM users WHERE email = {placeholder}", (data.email,)).fetchone()
        if user:
            reset_token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            conn.execute(
                f"UPDATE users SET reset_token = {placeholder}, reset_token_expires = {placeholder} WHERE email = {placeholder}",
                (reset_token, expires, data.email)
            )
            conn.commit()
            background_tasks.add_task(send_password_reset_email, data.email, reset_token)
    
    return MessageResponse(message="If an account exists with this email, you will receive a password reset link.")

@app.post("/api/auth/reset-password", response_model=MessageResponse)
async def reset_password(data: PasswordResetConfirm):
    """Reset password using token from email"""
    placeholder = "%s" if USE_POSTGRES else "?"
    with get_db() as conn:
        user = conn.execute(
            f"SELECT * FROM users WHERE reset_token = {placeholder}",
            (data.token,)
        ).fetchone()
        
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
        user_dict = dict(user)
        if user_dict.get("reset_token_expires"):
            expires = user_dict["reset_token_expires"]
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires)
            if expires < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Reset token has expired")
        
        password_hash = hash_password(data.new_password)
        conn.execute(
            f"UPDATE users SET password_hash = {placeholder}, reset_token = NULL, reset_token_expires = NULL WHERE id = {placeholder}",
            (password_hash, user_dict["id"])
        )
        conn.commit()
    
    return MessageResponse(message="Password has been reset successfully")

@app.post("/api/auth/google", response_model=TokenResponse)
async def google_auth(data: GoogleAuthRequest):
    """Authenticate with Google Sign-In"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    try:
        # Verify the Google ID token
        idinfo = id_token.verify_oauth2_token(
            data.id_token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        email = idinfo.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        # Check if user exists, create if not
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            
            if user:
                user_id = user["id"]
            else:
                # Create new user with random password (they'll use OAuth to login)
                random_password = secrets.token_hex(32)
                password_hash = hash_password(random_password)
                cursor = conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, password_hash)
                )
                conn.commit()
                user_id = cursor.lastrowid
        
        token = create_token(user_id)
        return TokenResponse(access_token=token)
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")

@app.post("/api/auth/apple", response_model=TokenResponse)
async def apple_auth(data: AppleAuthRequest):
    """Authenticate with Sign in with Apple"""
    if not APPLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Apple OAuth not configured")
    
    try:
        # Fetch Apple's public keys
        async with httpx.AsyncClient() as client:
            response = await client.get("https://appleid.apple.com/auth/keys")
            apple_keys = response.json()
        
        # Decode the token header to get the key ID
        header = jwt.get_unverified_header(data.id_token)
        kid = header.get("kid")
        
        # Find the matching key
        key = None
        for k in apple_keys.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break
        
        if not key:
            raise HTTPException(status_code=401, detail="Unable to find matching Apple key")
        
        # Verify and decode the token
        from jose import jwt as jose_jwt
        from jose.utils import base64url_decode
        import json
        
        # Construct the public key
        public_key = {
            "kty": key["kty"],
            "kid": key["kid"],
            "use": key["use"],
            "alg": key["alg"],
            "n": key["n"],
            "e": key["e"]
        }
        
        # Verify the token
        payload = jose_jwt.decode(
            data.id_token,
            public_key,
            algorithms=["RS256"],
            audience=APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com"
        )
        
        email = payload.get("email")
        
        # Apple only sends email on first sign-in, check user_info
        if not email and data.user_info:
            email = data.user_info.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Apple")
        
        # Check if user exists, create if not
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            
            if user:
                user_id = user["id"]
            else:
                # Create new user with random password
                random_password = secrets.token_hex(32)
                password_hash = hash_password(random_password)
                cursor = conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, password_hash)
                )
                conn.commit()
                user_id = cursor.lastrowid
        
        token = create_token(user_id)
        return TokenResponse(access_token=token)
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Apple token: {str(e)}")

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

@app.put("/api/user/profile", response_model=MessageResponse)
async def update_profile(data: UpdateProfileRequest, user: dict = Depends(require_user)):
    """Update user profile (email or password)"""
    placeholder = "%s" if USE_POSTGRES else "?"
    
    if data.new_password:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="Current password required to change password")
        if not verify_password(data.current_password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    with get_db() as conn:
        if data.email and data.email != user["email"]:
            existing = conn.execute(f"SELECT id FROM users WHERE email = {placeholder}", (data.email,)).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
            conn.execute(f"UPDATE users SET email = {placeholder} WHERE id = {placeholder}", (data.email, user["id"]))
        
        if data.new_password:
            password_hash = hash_password(data.new_password)
            conn.execute(f"UPDATE users SET password_hash = {placeholder} WHERE id = {placeholder}", (password_hash, user["id"]))
        
        conn.commit()
    
    return MessageResponse(message="Profile updated successfully")

@app.delete("/api/user/account", response_model=MessageResponse)
async def delete_account(user: dict = Depends(require_user)):
    """Delete user account and all associated data"""
    placeholder = "%s" if USE_POSTGRES else "?"
    
    with get_db() as conn:
        conn.execute(f"DELETE FROM operations WHERE user_id = {placeholder}", (user["id"],))
        conn.execute(f"DELETE FROM users WHERE id = {placeholder}", (user["id"],))
        conn.commit()
    
    return MessageResponse(message="Account deleted successfully")

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
                            "price": 5,
                            "price_id": STRIPE_PRICE_PRO,
                            "features": [
                                "100 operations per day",
                                "Max 25MB file size",
                                "All PDF tools",
                                "Priority support"
                            ]
                        },
                        {
                            "name": "Business",
                            "price": 25,
                            "price_id": STRIPE_PRICE_BUSINESS,
                "features": [
                    "1,000 operations per day",
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
