"""End-to-end browser acceptance smoke for the local pilot.
Requires: pip install playwright && python -m playwright install chromium
Runs only against an isolated loopback process and synthetic merchant records.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
HOST="127.0.0.1"
PORT=8765
URL=f"http://{HOST}:{PORT}"

def await_health(timeout=20):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        try:
            with urlopen(URL+"/api/health",timeout=1) as r:
                if r.status==200:return
        except OSError:
            time.sleep(.25)
    raise RuntimeError("Local test service did not start")

def main():
    with tempfile.TemporaryDirectory() as directory:
        env=os.environ.copy()
        env["MERCHANTSCOPE_ADMIN_TOKEN"]="browser-smoke-test-token"
        env["MERCHANTSCOPE_LOCAL_ONLY"]="1"
        env["MERCHANTSCOPE_DB"]=str(Path(directory)/"browser-smoke.db")
        env.pop("MERCHANTSCOPE_REVIEWER_TOKEN",None)
        server=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host",HOST,
                                 "--port",str(PORT)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE)
        try:
            await_health()
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
                page=browser.new_page(viewport={"width":1365,"height":900},locale="ar")
                page.goto(URL,wait_until="domcontentloaded")
                expect(page.locator("h1")).to_contain_text("مرصد التجار")
                page.locator("#secret").fill("browser-smoke-test-token")
                page.locator("#reload").click()
                expect(page.locator("#notice")).to_contain_text("تم التحديث")
                page.locator('button[data-tab="merchants"]').click()
                page.locator('#merchantForm input[name="name"]').fill("متجر الاختبار الاصطناعي")
                page.locator('#merchantForm input[name="city"]').fill("صنعاء")
                page.locator('#merchantForm input[name="category"]').fill("تجزئة")
                page.locator('#merchantForm button[type="submit"], #merchantForm button').first.click()
                expect(page.locator('#merchantList')).to_contain_text("متجر الاختبار الاصطناعي")
                page.locator('[data-merchant]').first.click()
                expect(page.locator('#dossier')).to_contain_text("متجر الاختبار الاصطناعي")
                page.locator('button[data-tab="reports"]').click()
                page.locator("#reportRun").click()
                expect(page.locator("#reportKpis")).to_contain_text("1")
                expect(page.locator("#reportRows")).to_contain_text("متجر الاختبار الاصطناعي")
                page.emulate_media(media="print")
                page.evaluate("document.body.classList.add('print-portfolio')")
                assert page.locator("#reports").evaluate("(x) => getComputedStyle(x).display") != "none"
                assert page.locator("#merchants").evaluate("(x) => getComputedStyle(x).display") == "none"
                page.emulate_media(media="screen")
                page.evaluate("document.body.classList.remove('print-portfolio')")
                page.locator('button[data-tab="merchants"]').click()
                page.evaluate("document.body.classList.add('print-merchant')")
                page.emulate_media(media="print")
                assert page.locator("#merchants").evaluate("(x) => getComputedStyle(x).display") != "none"
                assert page.locator("#reports").evaluate("(x) => getComputedStyle(x).display") == "none"
                page.emulate_media(media="screen")
                page.screenshot(path=str(Path(directory)/"smoke.png"))
                browser.close()
                print("PASS: Arabic dashboard, synthetic merchant, dossier, portfolio metrics and print modes")
        finally:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill()

if __name__=="__main__":
    main()
