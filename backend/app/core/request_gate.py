"""Cheap, bounded per-process flood admission before routing or database access."""
import threading
import time


class RequestGate:
    def __init__(self, *, ip_rate=60, global_rate=200, login_ip_rate=5, login_global_rate=20,
                 max_ips=4096, clock=time.monotonic):
        self.rates = (ip_rate, global_rate, login_ip_rate, login_global_rate)
        self.clock = clock
        self.max_ips = max_ips
        self.lock = threading.Lock()
        self.ips = {}
        self.global_buckets = {}
        self.last_cleanup = clock()

    def admit(self, ip: str, login=False):
        with self.lock:
            now = self.clock()
            if now - self.last_cleanup > 30:
                self.ips = {key: value for key, value in self.ips.items() if now - value["seen"] < 600}
                self.last_cleanup = now
            if ip not in self.ips:
                if len(self.ips) >= self.max_ips:
                    return False
                self.ips[ip] = {"seen": now, "buckets": {}}
            state = self.ips[ip]
            state["seen"] = now
            candidates = [(state["buckets"], "api", self.rates[0]), (self.global_buckets, "api", self.rates[1])]
            if login:
                candidates += [(state["buckets"], "login", self.rates[2]), (self.global_buckets, "login", self.rates[3])]
            available = []
            for store, key, rate in candidates:
                tokens, at = store.get(key, (rate * 2, now))
                tokens = min(rate * 2, tokens + max(0, now - at) * rate)
                available.append((store, key, tokens))
            if any(tokens < 1 for _, _, tokens in available):
                return False
            for store, key, tokens in available:
                store[key] = (tokens - 1, now)
            return True


request_gate = RequestGate()
