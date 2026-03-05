# =============================================================================
# tests/locustfile.py
# Purpose : Stress testing for assignment Phase VI — Production Readiness.
# Usage   : locust -f tests/locustfile.py --host=http://localhost:8000
#           Then open http://localhost:8089 for the Locust web UI.
# =============================================================================

from locust import HttpUser, task, between
import uuid


class ShoppingUser(HttpUser):
    """
    Simulates a real user interacting with the Daraz assistant.
    Each simulated user gets their own session_id to test session isolation.
    """
    wait_time = between(2, 5)  # realistic think time between messages

    def on_start(self):
        """Called once per simulated user — create a unique session."""
        self.session_id = str(uuid.uuid4())

        # Warmup: get welcome message
        self.client.get(f"/session/welcome/{self.session_id}")

    @task(3)
    def send_shopping_message(self):
        """Most common action — send a shopping query."""
        self.client.post(
            "/chat",
            json={
                "session_id": self.session_id,
                "message"   : "I need wireless earbuds under 3000 PKR"
            },
            name="/chat [shopping query]"
        )

    @task(2)
    def send_followup(self):
        """Follow-up message in same session — tests memory."""
        self.client.post(
            "/chat",
            json={
                "session_id": self.session_id,
                "message"   : "What about noise cancellation?"
            },
            name="/chat [follow-up]"
        )

    @task(1)
    def health_check(self):
        """Lightweight probe — tests server responsiveness under load."""
        self.client.get("/health", name="/health")

    @task(1)
    def check_session_state(self):
        """Verifies state extraction works under concurrent load."""
        self.client.get(
            f"/debug/state/{self.session_id}",
            name="/debug/state"
        )

    def on_stop(self):
        """Clean up session when simulated user leaves."""
        self.client.post(
            "/reset",
            json={"session_id": self.session_id},
            name="/reset"
        )