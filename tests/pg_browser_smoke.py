"""Secure PostgreSQL browser acceptance with distinct analyst/admin and reviewer logins.
Uses only an ephemeral PostgreSQL CI test database and synthetic merchants.
"""
import os
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect
from psycopg import connect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.pg_identity import bootstrap_admin, hash_password
URL="http://127.0.0.1:8766"

def wait_server():
    for _ in range(80):
        try:
            with urlopen(URL+"/",timeout=1) as result:
                if result.status==200:return
        except OSError:time.sleep(.25)
    raise RuntimeError("PostgreSQL API did not start")

def main():
    dsn=os.environ["PG_TEST_DSN"]
    suffix=uuid4().hex[:9]
    admin_email=f"browser-admin-{suffix}@example.org"
    reviewer_email=f"browser-reviewer-{suffix}@example.org"
    admin_password="Synthetic strong password 12345"
    reviewer_password="Different synthetic password 98765"
    org=bootstrap_admin(dsn,"Browser Test "+suffix,admin_email,admin_password)
    with connect(dsn) as db:
        reviewer_id=uuid4()
        db.execute("INSERT INTO ms.user_accounts(id,email,password_hash) VALUES(%s,%s,%s)",
                   (reviewer_id,reviewer_email,hash_password(reviewer_password)))
        db.execute("INSERT INTO ms.memberships(org_id,user_id,role) VALUES(%s,%s,'reviewer')",
                   (org["org_id"],reviewer_id))
    env=os.environ.copy()
    env["MERCHANTSCOPE_AUTH_DSN"]=dsn
    env["MERCHANTSCOPE_DATA_DSN"]=dsn
    server=subprocess.Popen([sys.executable,"-m","uvicorn","app.pg_api:app","--host","127.0.0.1","--port","8766"],
                            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        wait_server()
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,args=["--no-sandbox"])
            page=browser.new_page(viewport={"width":1440,"height":900},locale="ar")
            page.goto(URL,wait_until="domcontentloaded")
            expect(page.locator("#loginForm")).to_be_visible()
            def login(email,password):
                page.locator('#loginForm input[name="email"]').fill(email)
                page.locator('#loginForm input[name="password"]').fill(password)
                page.locator('#loginForm input[name="org_id"]').fill(org["org_id"])
                page.locator('#loginForm button').click()
                expect(page.locator("#workspace")).to_be_visible(timeout=15000)
            login(admin_email,admin_password)
            expect(page.locator("#identity")).to_contain_text("admin")
            # Candidate import is explicitly staged and never grants outreach permission.
            page.locator('button[data-panel="researchPanel"]').click()
            sample={
              "collected_on":datetime.now(timezone.utc).date().isoformat(),
              "records":[{"name":"تاجر تجريبي لفحص الباحث","city":"صنعاء",
                          "category":"هدايا","source_url":"https://happynew.day/vendor/synthetic-browser-candidate"}]
            }
            page.locator("#candidateFile").set_input_files({
                "name":"synthetic.json","mimeType":"application/json",
                "buffer":json.dumps(sample,ensure_ascii=False).encode("utf-8")
            })
            expect(page.locator("#candidatePreview")).to_contain_text("تاجر تجريبي لفحص الباحث")
            page.locator("#candidatePreview .research-include").check()
            page.once("dialog",lambda dialog:dialog.accept())
            page.locator("#candidatePreview button").click()
            expect(page.locator("#alerts")).to_contain_text("أُدخل 1",timeout=15000)
            expect(page.locator("#candidateList")).to_contain_text("تاجر تجريبي لفحص الباحث")
            page.locator('button[data-panel="merchantPanel"]').click()
            page.locator('#createBox summary').click()
            page.locator('#createForm input[name="name"]').fill("تاجر اختبار المتصفح")
            page.locator('#createForm input[name="city"]').fill("صنعاء")
            page.locator('#createForm input[name="category"]').fill("تجزئة")
            page.locator('#createForm button').click()
            expect(page.locator('#merchantDetail')).to_contain_text("تاجر اختبار المتصفح",timeout=15000)
            for n in (2,15,30):
                page.locator('#merchantDetail input[name="platform"]').fill("web")
                page.locator('#merchantDetail input[name="source_url"]').fill(f"https://example.org/marketing-post/{n}")
                at=(datetime.now(timezone.utc)-timedelta(days=n)).strftime("%Y-%m-%dT%H:%M")
                page.locator('#merchantDetail input[name="observed_at"]').fill(at)
                page.locator('#merchantDetail textarea[name="text"]').fill("منشور تجريبي قصير")
                page.locator('#merchantDetail form button').click()
                expect(page.locator("#merchantDetail")).to_contain_text(f"marketing-post/{n}",timeout=15000)
            page.locator('#merchantDetail .toolbar button').first.click()
            expect(page.locator("#alerts")).to_contain_text("تم إنشاء",timeout=15000)
            page.locator('button[data-panel="reviewsPanel"]').click()
            expect(page.locator("#reviews article").first).to_be_visible(timeout=15000)
            shots=Path(os.environ.get("MERCHANTSCOPE_SCREENSHOT_DIR",tempfile.gettempdir()))
            shots.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(shots/"secure-admin-review.png"),full_page=True)
            page.locator("#logout").click()
            expect(page.locator("#loginForm")).to_be_visible()
            login(reviewer_email,reviewer_password)
            expect(page.locator("#identity")).to_contain_text("reviewer")
            expect(page.locator("#alerts")).to_contain_text("تم تسجيل الدخول",timeout=15000)
            page.locator('button[data-panel="merchantPanel"]').click()
            expect(page.locator("#createBox")).to_be_hidden()
            page.locator('button[data-panel="reviewsPanel"]').click()
            expect(page.locator("#reviews article").first).to_be_visible(timeout=15000)
            page.locator("#reviews article textarea").first.fill("الدليل مرتبط بالعينة ويحتاج متابعة")
            expect(page.locator("#reviews article textarea").first).to_have_value("الدليل مرتبط بالعينة ويحتاج متابعة")
            page.locator("#reviews article button").first.click()
            expect(page.locator("#alerts")).to_contain_text("تم تسجيل",timeout=15000)
            page.screenshot(path=str(shots/"secure-reviewer.png"),full_page=True)
            page.locator('button[data-panel="researchPanel"]').click()
            expect(page.locator("#candidateList")).to_contain_text("تاجر تجريبي لفحص الباحث",timeout=15000)
            note=page.locator('#candidateList article textarea').first
            note.fill("صفحة الدليل متاحة، والمصدر يحتاج مراجعة نشاط إضافية")
            expect(note).to_have_value("صفحة الدليل متاحة، والمصدر يحتاج مراجعة نشاط إضافية")
            page.locator('#candidateList article button').first.click()
            expect(page.locator("#alerts")).to_contain_text("تم حفظ قرار المراجعة",timeout=15000)
            expect(page.locator("#candidateList")).to_contain_text("reviewed",timeout=15000)
            page.screenshot(path=str(shots/"secure-candidate-review.png"),full_page=True)
            page.locator("#logout").click()
            expect(page.locator("#loginForm")).to_be_visible()
            login(admin_email,admin_password)
            page.locator('button[data-panel="researchPanel"]').click()
            expect(page.locator("#candidateList")).to_contain_text("تاجر تجريبي لفحص الباحث",timeout=15000)
            page.once("dialog",lambda dialog:dialog.accept())
            page.locator('#candidateList button').filter(has_text="نقل إلى سجل التجار").first.click()
            expect(page.locator("#alerts")).to_contain_text("أُضيف ملف التاجر",timeout=15000)
            page.locator('button[data-panel="merchantPanel"]').click()
            expect(page.locator("#merchantList")).to_contain_text("تاجر تجريبي لفحص الباحث")
            page.screenshot(path=str(shots/"secure-candidate-promoted.png"),full_page=True)
            browser.close()
        print("PASS: secure PostgreSQL auth, merchant+evidence, analysis and independent human review")
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill()

if __name__=="__main__":main()
