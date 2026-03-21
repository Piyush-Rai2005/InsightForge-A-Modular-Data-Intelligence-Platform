from datetime import datetime

class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    def log(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{self.name}] {ts} - {msg}")

    def run(self, context: dict) -> dict:
        raise NotImplementedError