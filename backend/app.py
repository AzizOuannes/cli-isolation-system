from flask import Flask, request, jsonify
from flask_cors import CORS
from container_manager import ContainerManager
import time

app = Flask(__name__)
CORS(app)

# Configuration for two-VM setup
CONTAINER_HOST_IP = "4.211.83.255"  # Container host VM IP
WEB_SERVER_IP = "4.211.81.54"       # Web server VM IP (this VM)

# Initialize container manager with remote host
container_manager = ContainerManager(container_host_ip=CONTAINER_HOST_IP)

# Configuration
MAX_CONCURRENT_CONTAINERS = 1000  # Very high limit

def is_system_at_capacity() -> bool:
    """Check if system has reached maximum concurrent containers"""
    active_containers = len(container_manager.user_containers)
    return active_containers >= MAX_CONCURRENT_CONTAINERS

@app.route('/api/request-cli', methods=['POST'])
def request_cli():
    """Handle CLI access request - """
    data = request.get_json()
    username = data.get('username')
    
    if not username:
        return jsonify({"error": "Username is required"}), 400
    
    # Check if user already has a container (ONE CONTAINER PER USER RULE)
    existing_container = container_manager.get_user_container(username)
    if existing_container:
        return jsonify({
            "message": f"Returning existing CLI session for {username}",
            "url": existing_container["url"],
            "container_name": existing_container["container_name"],
            "port": existing_container["port"],
            "security_level": "enhanced",
            "session_type": "existing",
            "has_persistent_data": existing_container.get("has_persistent_data", True),
            "note": "Your files from previous sessions are available in /workspace",
            "architecture": {
                "web_server": WEB_SERVER_IP,
                "container_host": CONTAINER_HOST_IP,
                "deployment": "distributed"
            }
        })
    
    # Check if user has data from previous sessions
    data_status = container_manager.check_user_has_data(username)
    
    # Check system capacity
    if is_system_at_capacity():
        return jsonify({
            "error": f"System at capacity. Maximum {MAX_CONCURRENT_CONTAINERS} concurrent users supported.",
            "active_users": len(container_manager.user_containers),
            "max_capacity": MAX_CONCURRENT_CONTAINERS
        }), 503
    
    # Create new secure container for user
    container_info = container_manager.create_user_container(username)
    if container_info:
        # Wait for secure container to start
        time.sleep(3)
        
        return jsonify({
            "message": f"CLI session created for {username}",
            "url": container_info["url"],
            "container_name": container_info["container_name"],
            "port": container_info["port"],
            "security_level": "enhanced",
            "session_type": "new",
            "has_persistent_data": True,
            "data_status": data_status,
            "workspace_info": {
                "path": "/workspace",
                "persistent": True,
                "note": "All files saved in /workspace will persist between sessions"
            },
            "resource_limits": {
                "memory": "128MB",
                "cpu": "0.5 cores",
                "processes": "50 max",
                "session_timeout": "2 minutes"
            },
            "architecture": {
                "web_server": WEB_SERVER_IP,
                "container_host": CONTAINER_HOST_IP,
                "deployment": "distributed"
            }
        })
    else:
        return jsonify({"error": "Failed to create secure CLI container"}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    active_count = len(container_manager.user_containers)
    capacity_percentage = round((active_count / MAX_CONCURRENT_CONTAINERS) * 100, 2)
    
    return jsonify({
        "status": "healthy",
        "message": "Multi-User CLI Isolation Service with Persistent Data",
        "architecture": {
            "type": "distributed",
            "web_server": WEB_SERVER_IP,
            "container_host": CONTAINER_HOST_IP,
            "description": "Two-VM architecture with separate container orchestration"
        },
        "capacity": {
            "active_containers": active_count,
            "max_capacity": MAX_CONCURRENT_CONTAINERS,
            "available_slots": MAX_CONCURRENT_CONTAINERS - active_count,
            "usage_percentage": capacity_percentage
        },
        "features": {
            "container_isolation": "Complete process, filesystem, network isolation",
            "persistent_data": "User files persist in Docker volumes",
            "resource_limits": "128MB RAM, 0.5 CPU per container",
            "one_container_per_user": "Simple policy, no rate limiting needed",
            "auto_cleanup": "Containers removed on inactivity, data preserved",
            "distributed_architecture": "Separate web server and container host VMs"
        }
    })

if __name__ == '__main__':
    print("🔒 Starting Multi-User CLI Isolation Service with Persistent Data...")
    print("🌐 Architecture: Distributed (Two-VM Setup)")
    print(f"📡 Web Server: {WEB_SERVER_IP}")
    print(f"🐳 Container Host: {CONTAINER_HOST_IP}")
    print("📋 Features:")
    print("   - One container per user (simple policy)")
    print("   - Persistent user data in Docker volumes")
    print("   - Complete container isolation")
    print(f"   - Support up to {MAX_CONCURRENT_CONTAINERS} concurrent users")
    print("   - Ephemeral containers + Persistent data")
    print("   - Distributed container orchestration")
    print("")
    
    app.run(debug=True, host='0.0.0.0', port=5000)