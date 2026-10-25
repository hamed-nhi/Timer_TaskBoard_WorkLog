from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import ApiError
from app.core.time import now_local
from app.main import app
from app.services import auth
from app.services import login_protection as protection
from tests.support import Client, make_user, sql


def attempt(username="alice", password="wrong-password", **extra):
    return Client().post("/api/auth/login", json={"username":username,"password":password,**extra})


def test_concurrent_password_guesses_admit_only_three():
    make_user("alice")
    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses=list(pool.map(lambda _:attempt().status_code, range(12)))
    assert statuses.count(401)==3
    assert statuses.count(429)==9
    assert sql("SELECT COUNT(*) n FROM login_attempts")[0]["n"]==3
    assert sql("SELECT COUNT(*) n FROM sessions")[0]["n"]==0


def test_success_does_not_clear_ip_failure_history():
    make_user("alice")
    for i in range(8):
        make_user("known"+str(i))
        assert attempt("known"+str(i)).status_code==401
    assert attempt(password="password123").status_code==200
    for i in range(2):
        make_user("other"+str(i))
        assert attempt("other"+str(i)).status_code==401
    assert attempt(password="password123").status_code==429


@pytest.mark.parametrize("setting,limit",[("login_ip_burst",4),("login_ip_hourly",4),("login_global_per_minute",4)])
def test_successes_also_consume_request_budgets(monkeypatch, setting, limit):
    monkeypatch.setattr(settings,setting,limit)
    make_user("alice")
    for _ in range(limit):assert attempt(password="password123").status_code==200
    response=attempt(password="password123")
    assert response.status_code==429 and int(response.headers["Retry-After"])>0


def test_global_budget_applies_across_real_client_ips(monkeypatch):
    monkeypatch.setattr(settings,"login_global_per_minute",3)
    for i in range(4):
        with TestClient(app,client=(f"192.0.2.{i+1}",1)) as c:
            r=c.post("/api/auth/login",json={"username":"nobody","password":"wrong-password"},headers={"X-Requested-With":"timelog"})
            assert r.status_code==(401 if i<3 else 429)


def test_forged_forwarding_headers_cannot_change_direct_client_ip():
    for i in range(3):
        response=Client().post("/api/auth/login",json={"username":"alice","password":"wrong-password"},headers={"X-Forwarded-For":f"192.0.2.{i}","Forwarded":"for=203.0.113.1"})
        assert response.status_code==401
    assert attempt().status_code==429
    assert sql("SELECT DISTINCT host(ip) ip FROM login_attempts")==[{"ip":"127.0.0.1"}]


def test_persisted_limit_survives_new_client_and_time_window(monkeypatch):
    make_user("alice")
    for _ in range(3):assert attempt().status_code==401
    assert attempt(password="password123").status_code==429
    later=now_local()+timedelta(minutes=21)
    monkeypatch.setattr(auth,"now_local",lambda:later)
    monkeypatch.setattr(protection,"now_local",lambda:later)
    assert attempt(password="password123").status_code==200


@pytest.fixture
def captcha(monkeypatch):
    monkeypatch.setattr(settings,"captcha_provider","arcaptcha")
    monkeypatch.setattr(settings,"arcaptcha_site_key","public-test-site")
    monkeypatch.setattr(settings,"arcaptcha_secret_key","private-test-secret")
    make_user("alice")


def test_config_never_exposes_secret(captcha):
    r=Client().get("/api/auth/config")
    assert r.status_code==200 and r.get_json()=={"captcha_provider":"arcaptcha","site_key":"public-test-site"}
    assert "private-test-secret" not in r.text and r.headers["cache-control"]=="no-store"


@pytest.mark.parametrize("token",[None,"",[],{},"x"*4097])
def test_direct_api_cannot_skip_enabled_captcha(captcha,monkeypatch,token):
    monkeypatch.setattr(auth,"verify_password",lambda *a:pytest.fail("Password hash must follow captcha verification"))
    assert attempt(password="password123",captcha_token=token).status_code==400
    assert sql("SELECT COUNT(*) n FROM sessions")[0]["n"]==0
    assert sql("SELECT COUNT(*) n FROM login_attempts")[0]["n"]==1


def test_captcha_replay_is_blocked_locally(captcha,monkeypatch):
    called=[]
    monkeypatch.setattr(auth,"verify_captcha",lambda token:called.append(token))
    assert attempt(password="password123",captcha_token="one-time-token").status_code==200
    assert attempt(password="password123",captcha_token="one-time-token").status_code==400
    assert called==["one-time-token"]
    assert sql("SELECT token_hash FROM captcha_redemptions")[0]["token_hash"]!="one-time-token"


def test_same_captcha_concurrently_creates_one_session(captcha,monkeypatch):
    monkeypatch.setattr(auth,"verify_captcha",lambda token:None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:attempt(password="password123",captcha_token="same-token").status_code,range(2)))
    assert sorted(statuses)==[200,400]
    assert sql("SELECT COUNT(*) n FROM sessions")[0]["n"]==1


@pytest.mark.parametrize("status",[400,503])
def test_provider_rejection_or_outage_never_creates_session(captcha,monkeypatch,status):
    def fail(token):raise ApiError("provider failure",status)
    monkeypatch.setattr(auth,"verify_captcha",fail)
    assert attempt(password="password123",captcha_token="unique-token").status_code==status
    assert sql("SELECT COUNT(*) n FROM sessions")[0]["n"]==0
    assert sql("SELECT COUNT(*) n FROM login_attempts WHERE NOT success")[0]["n"]==1


def test_oversized_credentials_never_hash(monkeypatch):
    monkeypatch.setattr(auth,"verify_password",lambda *a:pytest.fail("Unbounded password"))
    assert attempt(password="x"*1025).status_code==400
    assert attempt(username="x"*65).status_code==400



def test_three_stages_and_no_extension_while_banned(monkeypatch):
    make_user("alice")
    clock=[now_local()]
    monkeypatch.setattr(auth,"now_local",lambda:clock[0])
    monkeypatch.setattr(protection,"now_local",lambda:clock[0])
    for stage,minutes in enumerate([15,600,43200],1):
        for _ in range(3):assert attempt().status_code==401
        row=sql("SELECT * FROM login_bans WHERE username='alice'")[0]
        assert row["stage"]==stage and row["failures"]==0
        assert row["banned_until"]==clock[0]+timedelta(minutes=minutes)
        assert attempt(password="password123").status_code==429
        assert sql("SELECT banned_until FROM login_bans WHERE username='alice'")[0]["banned_until"]==row["banned_until"]
        clock[0]=row["banned_until"]+timedelta(seconds=1)


def test_ip_account_ban_does_not_lock_account_from_another_ip():
    make_user("alice")
    for _ in range(3):assert attempt().status_code==401
    with TestClient(app,client=("192.0.2.99",1)) as c:
        assert c.post("/api/auth/login",json={"username":"alice","password":"password123"},headers={"X-Requested-With":"timelog"}).status_code==200
    assert attempt(password="password123").status_code==429


def test_three_unknown_names_ban_ip_for_24_hours():
    for name in ["typo1","typo2","typo3"]:assert attempt(name).status_code==401
    row=sql("SELECT * FROM login_bans WHERE username=''")[0]
    assert abs((row["banned_until"]-now_local()).total_seconds()-86400)<5
    make_user("alice")
    assert attempt(password="password123").status_code==429


def test_success_resets_partial_typos_and_own_escalation(monkeypatch):
    make_user("alice")
    for _ in range(2):assert attempt("typo").status_code==401
    assert attempt(password="password123").status_code==200
    assert not sql("SELECT * FROM login_bans")
    sql("INSERT INTO login_bans (ip,username,failures,stage,banned_until,updated_at,reason) VALUES ('127.0.0.1','alice',0,2,NULL,now(),'password')")
    assert attempt(password="password123").status_code==200
    assert not sql("SELECT * FROM login_bans WHERE username='alice'")


def test_admin_can_configure_release_and_reset_ban(admin):
    make_user("alice")
    for _ in range(3):assert attempt("alice").status_code==401
    view=admin.get("/api/admin/login-protection").get_json()
    config=view["policy"];config.update({"attempts":4,"durations_minutes":[2,5,20],"unknown_minutes":60,"reset_on_success":False})
    assert admin.put("/api/admin/login-protection",json=config).status_code==200
    ban=view["bans"][0]
    assert admin.post(f"/api/admin/login-protection/{ban['id']}/unblock",json={"reset":False}).status_code==200
    row=sql("SELECT * FROM login_bans")[0]
    assert row["stage"]==1 and row["banned_until"] is None
    assert attempt(password="password123").status_code==200
    assert admin.post(f"/api/admin/login-protection/{ban['id']}/unblock",json={"reset":True}).status_code==200
    assert not sql("SELECT * FROM login_bans")
    assert sql("SELECT COUNT(*) n FROM audit_log WHERE kind IN ('login_policy_changed','login_ban_released')")[0]["n"]==3


def test_regular_user_cannot_read_or_change_security_settings(alice):
    assert alice.get("/api/admin/login-protection").status_code==403
    assert alice.put("/api/admin/login-protection",json={}).status_code==403
    assert alice.post("/api/admin/login-protection/1/unblock",json={"reset":True}).status_code==403


@pytest.mark.parametrize("change",[{"attempts":0},{"attempts":True},{"unknown_minutes":0},{"durations_minutes":[15,10,30]},{"durations_minutes":[15,600]},{"reset_on_success":"true"},{"ip_burst":0}])
def test_invalid_policy_is_atomic(admin,change):
    before=admin.get("/api/admin/login-protection").get_json()["policy"]
    assert admin.put("/api/admin/login-protection",json={**before,**change}).status_code==400
    assert admin.get("/api/admin/login-protection").get_json()["policy"]==before


def test_admin_credentials_change_preserves_data_and_revokes_sessions(admin,bob):
    uid=sql("SELECT id FROM users WHERE username='bob'")[0]["id"]
    created=bob.post("/api/tasks",json={"title":"preserved private record"}).get_json()
    response=admin.put(f"/api/admin/users/{uid}/credentials",json={"username":"mori","password":"New-password-42!","display_name":"Mori","is_admin":False})
    assert response.status_code==200
    assert bob.get("/api/me").status_code==401
    c=Client();assert c.post("/api/auth/login",json={"username":"mori","password":"New-password-42!"}).status_code==200
    assert c.get("/api/tasks").get_json()[0]["id"]==created["id"]
    assert "New-password-42!" not in str(sql("SELECT payload FROM audit_log"))


def test_duplicate_username_rolls_back_password_and_profile(admin,alice,bob):
    uid=sql("SELECT id FROM users WHERE username='bob'")[0]["id"]
    assert admin.put(f"/api/admin/users/{uid}/credentials",json={"username":"alice","password":"Another-password-1!","display_name":"Bad"}).status_code==409
    assert bob.get("/api/me").status_code==200
    assert attempt("bob","password123").status_code==200
    assert sql("SELECT display_name FROM users WHERE id=:id",id=uid)[0]["display_name"]=="bob"


def test_deactivation_and_reactivation_never_delete_task_data(admin,bob):
    uid=sql("SELECT id FROM users WHERE username='bob'")[0]["id"]
    task=bob.post("/api/tasks",json={"title":"keep this forever"}).get_json()
    before=sql("SELECT * FROM tasks WHERE id=:id",id=task["id"])
    assert admin.put(f"/api/admin/users/{uid}",json={"is_active":False}).status_code==200
    assert bob.get("/api/me").status_code==401
    assert sql("SELECT * FROM tasks WHERE id=:id",id=task["id"])==before
    assert admin.delete(f"/api/admin/users/{uid}").status_code==405
    assert admin.put(f"/api/admin/users/{uid}",json={"is_active":True}).status_code==200
    assert attempt("bob","password123").status_code==200
    assert sql("SELECT * FROM tasks WHERE id=:id",id=task["id"])==before


def test_admin_can_choose_initial_password_and_normal_user_cannot_rename(admin,alice):
    r=admin.post("/api/admin/users",json={"username":"chosen","password":"Chosen-password-1!"})
    assert r.status_code==201
    assert attempt("chosen","Chosen-password-1!").status_code==200
    assert alice.put(f"/api/admin/users/{r.get_json()['id']}/credentials",json={"username":"stolen"}).status_code==403


def test_policy_can_keep_escalation_after_success(admin):
    make_user("alice")
    p=admin.get("/api/admin/login-protection").get_json()["policy"]
    p["reset_on_success"]=False
    assert admin.put("/api/admin/login-protection",json=p).status_code==200
    sql("INSERT INTO login_bans (ip,username,failures,stage,updated_at,reason) VALUES ('127.0.0.1','alice',0,2,now(),'password')")
    assert attempt(password="password123").status_code==200
    assert sql("SELECT stage FROM login_bans WHERE username='alice'")[0]["stage"]==2


@pytest.mark.parametrize("password",["short", "abcdefgh", "ABCDEFGH", "Abcdefgh", "Abcdefg1", "abcdef1!", "ABCDEF1!", "Ab1!"+"x"*1021])
def test_password_complexity_enforced_on_every_web_setter(admin,alice,password):
    uid=sql("SELECT id FROM users WHERE username='alice'")[0]["id"]
    assert admin.post("/api/admin/users",json={"username":"newmember","password":password}).status_code==400
    assert admin.put(f"/api/admin/users/{uid}/credentials",json={"password":password}).status_code==400
    assert alice.post("/api/me/password",json={"old":"password123","new":password}).status_code==400
    assert alice.get("/api/me").status_code==200
    assert not sql("SELECT id FROM users WHERE username='newmember'")


def test_generated_passwords_meet_current_policy(admin):
    from app.core.security import validate_password
    r=admin.post("/api/admin/users",json={"username":"generated"})
    assert r.status_code==201
    validate_password(r.get_json()["temp_password"])
    reset=admin.post(f"/api/admin/users/{r.get_json()['id']}/reset-password")
    assert reset.status_code==200
    validate_password(reset.get_json()["temp_password"])



def test_first_login_backup_setup_is_private_and_survives_relogin(alice,bob):
    assert alice.get("/api/settings").get_json()["backup_setup_done"] is False
    assert alice.post("/api/settings",json={"backup_setup_done":True}).status_code==200
    assert alice.get("/api/settings").get_json()["backup_setup_done"] is True
    assert bob.get("/api/settings").get_json()["backup_setup_done"] is False
    assert attempt("alice","password123").status_code==200


def test_bad_sheet_does_not_mark_onboarding_done(alice):
    assert alice.post("/api/settings",json={"backup_setup_done":True,"google_sheet_url":"https://attacker.example"}).status_code==400
    assert alice.get("/api/settings").get_json()["backup_setup_done"] is False
    assert alice.post("/api/settings",json={"backup_setup_done":"true"}).status_code==400
