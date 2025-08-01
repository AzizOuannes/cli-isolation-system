import os
import requests


# Set Grafana URL and API key, fail if not set
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY")
if not GRAFANA_API_KEY or GRAFANA_API_KEY == "YOUR_API_KEY_HERE":
    raise RuntimeError("GRAFANA_API_KEY environment variable is not set or is invalid. Please set a valid Grafana API key.")

def create_user_dashboard(username, container_name):
    url = f"{GRAFANA_URL}/api/dashboards/db"
    headers = {
        "Authorization": f"Bearer {GRAFANA_API_KEY}",
        "Content-Type": "application/json"
    }
    # Use 'id' label for filtering, as seen in Prometheus data. This may need to be improved to match the actual container's id.
    # Use regex match for id label to match any id containing the container name
    dashboard = {
        "dashboard": {
            "id": None,
            "uid": None,
            "title": f"{username} Container Dashboard",
            "panels": [
                {
                    "type": "stat",
                    "title": "CPU Usage",
                    "datasource": "prometheus",  # Use the exact name from Grafana
                    "targets": [
                        {
                            # Use regex for id label to match any id containing the container name
                            "expr": f'container_cpu_usage_seconds_total{{id=~".*{container_name}.*"}}',
                            "format": "time_series"
                        }
                    ],
                    "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8}
                }
            ],
            "schemaVersion": 36,
            "version": 0
        },
        "overwrite": True
    }
    try:
        response = requests.post(url, headers=headers, json=dashboard)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[Grafana] Failed to create dashboard for {username}/{container_name}: {e}")
        return {"error": str(e)}
