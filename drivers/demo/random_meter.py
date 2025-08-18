# drivers/demo/random_meter.py
import random, time

class Driver:
    """
    Minimal demo driver. No hardware needed.
    Generates random voltage and current values.
    """
    def __init__(self, resource: str | None = None, **kwargs):
        self.resource = resource
        self.rng = random.Random(42)
        self.start = time.time()

    def poll(self) -> dict:
        t = time.time() - self.start
        v = 3.3 + 0.2 * self.rng.uniform(-1, 1)
        i = 0.12 + 0.03 * self.rng.uniform(-1, 1)
        return {
            "idn": "DEMO,RANDOM,METER,0.1",
            "voltage": v,
            "current": i,
            "ts": time.time(),
            "units": {"voltage": "V", "current": "A"},
        }

    def close(self):
        pass
