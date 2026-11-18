"""Bounded, read-only merchant discovery from OpenStreetMap Overpass.
OSM data is licensed ODbL; always attribute © OpenStreetMap contributors.
No social scraping or personal data extraction.
"""
import json
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from fastapi import HTTPException

URL="https://overpass-api.de/api/interpreter"
ATTRIBUTION="© OpenStreetMap contributors (ODbL) — https://www.openstreetmap.org/copyright"
MAX_RESULTS=50
_last_call=0.0
_lock=threading.Lock()
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def discover(lat:float,lon:float,radius_m:int,category:str):
    global _last_call
    if category not in {"shop","restaurant","cafe","pharmacy"}:
        raise HTTPException(422,"Unsupported category")
    if not (-90<=lat<=90 and -180<=lon<=180 and 100<=radius_m<=3000):
        raise HTTPException(422,"Coordinates/radius out of bounds")
    with _lock:
        if time.monotonic()-_last_call < 65:
            raise HTTPException(429,"Public Overpass endpoint rate-limited: retry later")
        _last_call=time.monotonic()
    if category=="shop":
        selector='["shop"]'
    else:
        selector=f'["amenity"="{category}"]'
    query=f'[out:json][timeout:20];nwr(around:{radius_m},{lat:.6f},{lon:.6f}){selector}["name"];out center {MAX_RESULTS};'
    request=Request(URL,data=urlencode({"data":query}).encode(),
                    headers={"User-Agent":"MerchantScopeLocalPilot/0.2 (read-only; OSM attribution)", "Accept":"application/json"},method="POST")
    opener=build_opener(ProxyHandler({}),NoRedirect())
    try:
        with opener.open(request,timeout=25) as response:
            if response.status!=200: raise HTTPException(502,"Upstream OSM service error")
            raw=response.read(1_000_001)
            if len(raw)>1_000_000: raise HTTPException(502,"OSM response too large")
        payload=json.loads(raw)
    except (HTTPError,URLError,TimeoutError,OSError,ValueError) as exc:
        raise HTTPException(503,"OSM discovery unavailable; use manual CSV import") from exc
    results=[]
    for entry in payload.get("elements",[]):
        tags=entry.get("tags") or {}
        name=tags.get("name")
        kind=entry.get("type")
        identifier=entry.get("id")
        if not isinstance(name,str) or not name.strip() or kind not in ("node","way","relation") or not isinstance(identifier,int):
            continue
        results.append({"name":name.strip()[:200],
                       "category":tags.get("shop") or tags.get("amenity") or "غير مصنف",
                       "source_url":f"https://www.openstreetmap.org/{kind}/{identifier}",
                       "lat":entry.get("lat") or (entry.get("center") or {}).get("lat"),
                       "lon":entry.get("lon") or (entry.get("center") or {}).get("lon")})
        if len(results)>=MAX_RESULTS: break
    return {"results":results,"source":"OpenStreetMap Overpass","attribution":ATTRIBUTION,
            "accuracy":"OSM coverage varies; listing does not verify current opening or ownership.",
            "imported":False}
