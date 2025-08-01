
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import subprocess
import json
import sqlite3
import uuid
import threading
import time
from typing import Optional, Dict

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
DOCKER_HOST_IP = os.getenv("DOCKER_HOST_IP", "localhost")
MAX_CONTAINERS = int(os.getenv("MAX_CONTAINERS", "100"))

app = FastAPI(
    title="Unified CLI API",
    description="Simplified FastAPI backend for CLI isolation",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Docker client with error handling
try:
    # Test Docker CLI directly instead of using Python Docker library
    result = subprocess.run(['docker', 'version', '--format', 'json'], 
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        docker_info = json.loads(result.stdout)
        print("✅ Docker CLI connected successfully")
        print(f"🐳 Docker version: {docker_info.get('Client', {}).get('Version', 'unknown')}")
        docker_client = "cli"  # Use CLI mode instead of Python library
    else:
        print(f"❌ Docker CLI failed: {result.stderr}")
        docker_client = None
except Exception as e:
    print(f"❌ Docker CLI test failed: {e}")
    docker_client = None

if docker_client is None:
    print("📋 CLI functionality will be disabled, but API and auth will work")

# In-memory container tracking
user_containers: Dict[str, dict] = {}
allocated_ports = set()  # No reserved ports for monitoring services

# Database setup
def init_db():
    conn = sqlite3.connect('app.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class CLIRequest(BaseModel):
    pass

# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user_by_username(username: str):
    conn = None
    try:
        conn = sqlite3.connect('app.db', timeout=10.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?", 
            (username, username)
        )
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        return None
    finally:
        if conn:
            conn.close()

def get_user_by_id(user_id: int):
    conn = None
    try:
        conn = sqlite3.connect('app.db', timeout=10.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        print(f"Database error in get_user_by_id: {e}")
        return None
    finally:
        if conn:
            conn.close()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    
    return user

def find_available_port() -> int:
    # Use port range 8090-8190 for user containers
    for port in range(8090, 8190):
        if port not in allocated_ports:
            allocated_ports.add(port)
            return port
    raise Exception("No available ports")

def create_user_container(username: str, user_id: int) -> dict:
    """Create a secure Docker container for the user using CLI"""
    if docker_client is None:
        raise Exception("Docker is not available. Please start Docker Desktop and restart the server.")
    
    container_id = str(uuid.uuid4())[:8]
    container_name = f"cli-{username}-{container_id}"
    volume_name = f"user-data-{username}"
    
    try:
        port = find_available_port()
        
        # Create volume if it doesn't exist
        result = subprocess.run(['docker', 'volume', 'inspect', volume_name], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            # Volume doesn't exist, create it
            result = subprocess.run(['docker', 'volume', 'create', volume_name], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to create volume: {result.stderr}")
        
        # Create container using CLI
        docker_cmd = [
            'docker', 'run', '-d',
            '--name', container_name,
            # '--network', 'cli-isloation-fastapi_default',  # Removed for portability
            '-p', f'{port}:7681',
            '-v', f'{volume_name}:/workspace',
            '--memory=128m',
            '--cpus=0.5',
            '--pids-limit=50',
            '--read-only',
            '--tmpfs', '/tmp',
            '--tmpfs', '/home',
            '--tmpfs', '/var',
            '--security-opt', 'no-new-privileges',
            '--cap-drop', 'ALL',
            '--cap-add', 'CHOWN',
            '--cap-add', 'DAC_OVERRIDE',
            '--cap-add', 'FOWNER',
            '--cap-add', 'SETGID',
            '--cap-add', 'SETUID',
            '-e', 'HOME=/workspace',
            '-e', 'USER=user',
            '-e', 'SHELL=/bin/bash',
            '-w', '/workspace',
            '--label', f'user_id={user_id}',
            '--label', f'username={username}',
            # '--label', 'service=unified-cli-monitoring',  # Removed monitoring label
            '--restart', 'unless-stopped',
            'tsl0922/ttyd:latest',
            'ttyd', '-W', '-p', '7681', '--max-clients', '1', 'bash'
        ]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            # Free port on error
            allocated_ports.discard(port)
            raise Exception(f"Docker container creation failed: {result.stderr}")
        
        # Get the actual container ID from Docker
        actual_container_id = result.stdout.strip()
        
        container_info = {
            "container_id": actual_container_id,
            "container_name": container_name,
            "volume_name": volume_name,
            "port": port,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "url": f"http://{DOCKER_HOST_IP}:{port}",
            "user_id": user_id,
            "status": "running"
        }
        
        user_containers[username] = container_info
        print(f"✅ Created container {container_name} for {username} on port {port}")
        return container_info
        
    except Exception as e:
        if port in allocated_ports:
            allocated_ports.remove(port)
        raise Exception(f"Failed to create container: {str(e)}")

def cleanup_user_container(username: str) -> bool:
    """Clean up user's container using CLI"""
    if username not in user_containers:
        return False
        
    container_info = user_containers[username]
    
    try:
        # Stop and remove container using CLI
        container_name = container_info["container_name"]
        
        # Stop container
        subprocess.run(['docker', 'stop', container_name], 
                      capture_output=True, text=True, timeout=10)
        
        # Remove container
        subprocess.run(['docker', 'rm', container_name], 
                      capture_output=True, text=True, timeout=10)
        
        # Free port
        allocated_ports.discard(container_info["port"])
        
        # Remove from tracking
        del user_containers[username]
        print(f"✅ Cleaned up container {container_name} for {username}")
        return True
        
    except Exception as e:
        print(f"Error cleaning up container for {username}: {e}")
        return False

def cleanup_inactive_containers():
    """Background cleanup of inactive containers"""
    while True:
        try:
            time.sleep(15)  # Check every 15 seconds

            # Skip cleanup if no containers to check
            if not user_containers:
                continue


            cutoff_time = datetime.now() - timedelta(minutes=3)  # 3 minutes of  inactivity
            to_remove = []

            # Create a copy to avoid modification during iteration
            containers_copy = dict(user_containers)

            for username, container_info in containers_copy.items():
                try:
                    last_accessed = datetime.fromisoformat(container_info["last_accessed"])
                    if last_accessed < cutoff_time:
                        print(f"[CLEANUP] {username} inactive since {last_accessed}, removing container {container_info['container_name']}")
                        to_remove.append(username)
                except Exception as e:
                    print(f"[CLEANUP] Error parsing last_accessed for {username}: {e}")
                    to_remove.append(username)

            for username in to_remove:
                try:
                    cleanup_user_container(username)
                    print(f"[CLEANUP] Auto-cleaned inactive container for {username}")
                except Exception as e:
                    print(f"[CLEANUP] Error during auto-cleanup for {username}: {e}")

        except Exception as e:
            print(f"Cleanup loop error: {e}")
            # Continue the loop even if there's an error

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_inactive_containers, daemon=True)
cleanup_thread.start()

# API Routes

@app.get("/")
async def root():
    return {"message": "Unified CLI API", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_containers": len(user_containers),
        "max_capacity": MAX_CONTAINERS
    }

# Authentication endpoints
@app.post("/auth/signup", response_model=Token)
async def signup(user_data: UserCreate):
    try:
        # Check if user exists
        existing_user = get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        # Hash password and create user
        hashed_password = get_password_hash(user_data.password)
        
        conn = sqlite3.connect('app.db', timeout=10.0)
        cursor = conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (user_data.username, user_data.email, hashed_password)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Create token
        access_token = create_access_token(data={
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email
        })
        
        return Token(
            access_token=access_token,
            user={
                "id": user_id,
                "username": user_data.username,
                "email": user_data.email
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    try:
        user = get_user_by_username(user_credentials.username)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not verify_password(user_credentials.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(data={
            "id": user["id"],
            "username": user["username"],
            "email": user["email"]
        })
        
        return Token(
            access_token=access_token,
            user={
                "id": user["id"],
                "username": user["username"],
                "email": user["email"]
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/auth/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    return {
        "valid": True,
        "user": {
            "id": current_user["id"],
            "username": current_user["username"],
            "email": current_user["email"]
        }
    }

# CLI endpoints

@app.post("/cli/request")
async def request_cli_access(current_user: dict = Depends(get_current_user)):
    username = current_user["username"]

    # Check if user already has a container
    if username in user_containers:
        container_info = user_containers[username]
        # Update last_accessed on every request
        container_info["last_accessed"] = datetime.now().isoformat()
        return {
            "success": True,
            "message": f"Returning existing CLI session for {username}",
            "container_info": container_info
        }

    # Check capacity
    if len(user_containers) >= MAX_CONTAINERS:
        raise HTTPException(
            status_code=503,
            detail=f"System at capacity. Maximum {MAX_CONTAINERS} concurrent users supported."
        )

    # Create new container
    try:
        container_info = create_user_container(username, current_user["id"])
        return {
            "success": True,
            "message": f"CLI session created for {username}",
            "container_info": container_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cli/status/{username}")
async def get_cli_status(username: str, current_user: dict = Depends(get_current_user)):
    if current_user["username"] != username:
        raise HTTPException(status_code=403, detail="Access denied")

    if docker_client is None:
        return {"exists": False, "message": "Docker is not available"}

    if username not in user_containers:
        return {"exists": False, "message": "No active CLI session found"}

    container_info = user_containers[username]
    # Update last_accessed on every status check
    container_info["last_accessed"] = datetime.now().isoformat()

    # Check if container is still running using CLI
    try:
        result = subprocess.run(['docker', 'inspect', container_info["container_name"], 
                               '--format', '{{.State.Status}}'], 
                              capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            # Container not found
            cleanup_user_container(username)
            return {"exists": False, "message": "Container not found"}

        status = result.stdout.strip()

    except Exception as e:
        status = "unknown"
        print(f"Error checking container status: {e}")

    return {
        "exists": True,
        "status": status,
        "container_info": container_info
    }

@app.delete("/cli/terminate/{username}")
async def terminate_cli_session(username: str, current_user: dict = Depends(get_current_user)):
    if current_user["username"] != username:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if cleanup_user_container(username):
        return {"success": True, "message": f"CLI session terminated for {username}"}
    else:
        return {"success": False, "message": "No active session found"}

    if cleanup_user_container(username):
        return {"success": True, "message": f"CLI session terminated for {username}"}
    else:
        return {"success": False, "message": "No active session found"}

# Simple status endpoint
@app.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """Get basic system status"""
    try:
        username = current_user["username"]
        user_container = user_containers.get(username)
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "user": {
                "username": username,
                "has_container": username in user_containers,
                "container_info": user_container if user_container else None
            },
            "system": {
                "active_containers": len(user_containers),
                "max_capacity": MAX_CONTAINERS,
                "docker_available": docker_client is not None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting Unified CLI API on port 8000")
    print(f"📊 Max concurrent containers: {MAX_CONTAINERS}")
    print(f"🐳 Docker host: {DOCKER_HOST_IP}")
    print(f"📚 API Documentation: http://localhost:8000/docs")
    
    # Use reload=False to avoid the import string warning when running directly
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
