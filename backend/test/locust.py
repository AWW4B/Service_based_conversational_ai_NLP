from locust import HttpUser, task, between

class ChatUser(HttpUser):
    wait_time = between(1, 3)  # simulates real user think time

    @task
    def send_message(self):
        self.client.post("/chat", json={"message": "Hello, how are you?"})

    @task(2)  # weight 2 = runs twice as often
    def health_check(self):
        self.client.get("/health")