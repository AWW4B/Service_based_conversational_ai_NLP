# =============================================================================
# tests/locust.py
# Purpose : Stress testing for assignment Phase VI — Production Readiness.
# Usage   : 
#   1. pip install locust
#   2. locust -f backend/tests/locust.py --host=http://localhost:8000
#   3. Open http://localhost:8089 to start the stress test
# =============================================================================

from locust import HttpUser, task, between
import uuid

class ShoppingUser(HttpUser):
    """
    Simulates a real user interacting with the Daraz assistant.
    Each simulated user gets their own session_id to test concurrent memory isolation.
    """
    # Wait between 5 to 10 seconds between tasks (simulates real human typing/reading)
    wait_time = between(5, 10)

    def on_start(self):
        """Called once per simulated user — create a unique session."""
        self.session_id = str(uuid.uuid4())
        self.client.get(f"/session/welcome/{self.session_id}", name="/session/welcome")

    @task(3)
    def send_shopping_message(self):
        """Simulates sending a shopping query via the REST fallback."""
        self.client.post(
            "/chat",
            json={
                "session_id": self.session_id,
                "message"   : "I need wireless earbuds under 3000 PKR"
            },
            name="/chat [shopping query]"
        )

    @task(2)
    def check_health(self):
        """Lightweight probe — tests FastAPI event loop responsiveness under load."""
        self.client.get("/health", name="/health")

    @task(1)
    def get_sessions(self):
        """Tests the database read speed."""
        self.client.get("/sessions", name="/sessions")

    def on_stop(self):
        """Clean up the database when the simulated user leaves."""
        self.client.post(
            "/reset",
            json={"session_id": self.session_id},
            name="/reset"
        )