import subprocess
import uuid
import time
import threading
import json
import random
from typing import Dict, Optional

class ContainerManager:
    def __init__(self, container_host_ip=None, ssh_username=None):
        # Configuration for local Docker
        self.container_host_ip = 'localhost'
        self.ssh_username = None
        self.is_remote = False  # Always local for development
        
        # Test local Docker connection
        self._test_connection()
        
        self.user_containers: Dict[str, dict] = {}
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def _test_connection(self):
        """Test local Docker connection"""
        try:
            # Test local Docker
            result = subprocess.run(['docker', 'ps'], capture_output=True, text=True, check=True)
            print("✅ Local Docker connection successful")
        except Exception as e:
            print(f"❌ Docker connection failed: {e}")
            print("Make sure Docker Desktop is installed and running")
            raise e
    
    def _run_command(self, cmd: list) -> subprocess.CompletedProcess:
        """Execute Docker command locally"""
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    def create_user_container(self, username: str) -> dict:
        """Create container locally"""
        container_id = str(uuid.uuid4())[:8]
        container_name = f"cli-{username}-{container_id}"
        volume_name = f"user-data-{username}"
        
        port = self._find_available_port()
        
        try:
            # Step 1: Create volume locally
            print(f"Creating volume {volume_name}")
            self._run_command(['docker', 'volume', 'create', volume_name])
            
            # Step 2: Create container locally using custom image
            cmd = [
                'docker', 'run', '-d',
                '--name', container_name,
                '-v', f'{volume_name}:/workspace',
                '--memory', '128m',
                '--memory-swap', '128m',
                '--cpus', '0.5',
                '--pids-limit', '50',
                '--read-only',
                '--tmpfs', '/tmp:exec',
                '--tmpfs', '/var/tmp:exec',
                '--tmpfs', '/home/ros/.ros:rw,exec',
                '--security-opt', 'no-new-privileges',
                '--cap-drop', 'NET_RAW',
                '--cap-drop', 'SYS_ADMIN',
                '--cap-drop', 'SYS_MODULE',
                '-p', f'{port}:7681',
                '--user', 'ros',
                '--env', 'HOME=/home/ros',
                '--env', 'USER=ros',
                '--env', 'SHELL=/bin/bash',
                '--workdir', '/workspace',
                'cli-isolation:latest'
            ]
            
            result = self._run_command(cmd)
            container_id_full = result.stdout.strip()
            
            # Store container info for localhost
            self.user_containers[username] = {
                "container_id": container_id_full,
                "container_name": container_name,
                "volume_name": volume_name,
                "port": port,
                "host_ip": self.container_host_ip,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "url": f"http://{self.container_host_ip}:{port}",
                "has_persistent_data": True,
                "deployment_type": "local"
            }
            
            print(f"✅ Created container {container_name} on localhost:{port}")
            return self.user_containers[username]
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating container: {e}")
            print(f"Error details: {e.stderr}")
            return None
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating container on {self.container_host_ip}: {e}")
            print(f"Error details: {e.stderr}")
            return None
    
    def get_user_container(self, username: str) -> Optional[dict]:
        """Get existing container info for user"""
        if username in self.user_containers:
            # Update last accessed time
            self.user_containers[username]["last_accessed"] = time.time()
            return self.user_containers[username]
        return None
    
    def remove_user_container(self, username: str) -> bool:
        """Remove user's container but PRESERVE their data volume"""
        if username not in self.user_containers:
            return False
        
        try:
            container_info = self.user_containers[username]
            container_name = container_info["container_name"]
            volume_name = container_info.get("volume_name", f"user-data-{username}")
            
            # Stop and remove container locally
            self._run_command(['docker', 'stop', container_name])
            self._run_command(['docker', 'rm', container_name])
            
            # Remove from tracking but KEEP the volume
            del self.user_containers[username]
            
            print(f"Container {container_name} removed from localhost")
            print(f"User data preserved in volume: {volume_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error removing container for {username}: {e}")
            return False
    
    def check_user_has_data(self, username: str) -> dict:
        """Check if user has persistent data from previous sessions"""
        volume_name = f"user-data-{username}"
        try:
            result = self._run_command(['docker', 'volume', 'inspect', volume_name])
            
            if result.returncode == 0:
                volume_info = json.loads(result.stdout)[0]
                return {
                    "has_data": True,
                    "volume_name": volume_name,
                    "created_at": volume_info.get("CreatedAt", "Unknown"),
                    "message": f"User {username} has saved files from previous sessions",
                    "host": self.container_host_ip
                }
            else:
                return {
                    "has_data": False,
                    "volume_name": volume_name,
                    "message": f"User {username} will get a clean workspace"
                }
        except subprocess.CalledProcessError:
            return {
                "has_data": False,
                "volume_name": volume_name,
                "message": f"User {username} will get a clean workspace"
            }
    
    def _find_available_port(self) -> int:
        """Find an available port starting from 7681"""
        # Simple approach: just use a random port in the range
        # For a demo, this is sufficient
        return random.randint(7681, 7780)
    
    def _cleanup_inactive_containers(self):
        """Remove containers inactive for more than 2 minutes"""
        current_time = time.time()
        inactive_users = []
        
        for username, info in self.user_containers.items():
            if current_time - info["last_accessed"] > 120:  # 2 minutes
                inactive_users.append(username)
        
        for username in inactive_users:
            print(f"Cleaning up inactive container for user: {username}")
            self.remove_user_container(username)
    
    def _cleanup_loop(self):
        """Background thread to cleanup inactive containers"""
        while True:
            time.sleep(30)      # Run cleanup every 30 seconds
            try:
                self._cleanup_inactive_containers()
            except Exception as e:
                print(f"Error in cleanup loop: {e}") 

