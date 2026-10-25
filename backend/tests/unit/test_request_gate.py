from concurrent.futures import ThreadPoolExecutor

from app.core.request_gate import RequestGate


def test_10000_bot_requests_are_bounded_across_ips():
    gate=RequestGate(global_rate=10,login_global_rate=2,clock=lambda:0)
    admitted=sum(gate.admit(str(i),login=True) for i in range(10000))
    assert admitted==4
    assert len(gate.ips)<=4096


def test_parallel_admission_is_atomic():
    gate=RequestGate(global_rate=100,ip_rate=100,login_ip_rate=3,clock=lambda:0)
    with ThreadPoolExecutor(max_workers=16) as pool:
        accepted=list(pool.map(lambda _:gate.admit("same-ip",True),range(200)))
    assert sum(accepted)==6


def test_budget_refills_without_deny_extending_wait():
    now=[0.0];gate=RequestGate(ip_rate=1,clock=lambda:now[0])
    assert gate.admit("ip") and gate.admit("ip")
    assert not gate.admit("ip")
    now[0]=0.5
    for _ in range(100):assert not gate.admit("ip")
    now[0]=1
    assert gate.admit("ip")


def test_key_capacity_does_not_evict_and_reset_existing_budgets():
    now=[0];gate=RequestGate(max_ips=2,clock=lambda:now[0])
    assert gate.admit("one") and gate.admit("two")
    assert not gate.admit("three")
    now[0]=601
    assert gate.admit("three") and len(gate.ips)==1


def test_gate_rejects_before_route_or_database(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import middleware
    class Deny:
        def admit(self,*a):return False
    monkeypatch.setattr(middleware,"request_gate",Deny())
    with TestClient(app) as c:
        r=c.post("/api/auth/login",content=b"invalid json")
        assert r.status_code==429
        assert r.headers["Retry-After"]=="1" and r.headers["Cache-Control"]=="no-store"
