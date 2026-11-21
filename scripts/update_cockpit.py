#!/usr/bin/env python3
"""Refresh the UNPI 69 cockpit data from Meta Ads connector outputs.

Usage
  python3 scripts/update_cockpit.py need-creatives --raw RAW_DIR
      Prints the ad ids whose creative is not cached yet (one per line).
  python3 scripts/update_cockpit.py build --raw RAW_DIR [--creative-files F ...]
      Rewrites data/meta.json and data/creatives.json, and saves new ad
      visuals in assets/crea/. Prints a short summary.

RAW_DIR holds the outputs of the Avinesh_Ads connector, pasted as returned
(several JSON objects one after the other are fine; "other_actions" may be
left out):
  daily.json      get_performance level=campaign, daily=true, since launch
  ads.json        get_performance level=ad, since launch
  ages.json       get_performance level=account, breakdown=age
  platforms.json  get_performance level=account, breakdown=publisher_platform
  adsets.json     list_adsets (campaign UNPI69_P1_Trafic_LP)
  ads_list.json   list_ads
Creative files are the saved outputs of get_ad_creative (JSON with images
in base64).
"""
import argparse, base64, datetime as dt, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CREA = os.path.join(ROOT, "assets", "crea")
INDEX = os.path.join(DATA, "creative_index.json")
CAMPAIGN_ID = "120249499276520426"
THEMES = {
    "PPL1": "Conseil syndical",
    "PPL2": "Nouveaux propriétaires",
    "PPL3": "Protection du patrimoine",
    "PPL4": "Rénovation énergétique",
    "PPL5": "Revenus locatifs",
}
PLATFORM_NAMES = {"facebook": "Facebook", "instagram": "Instagram",
                  "audience_network": "Audience Network", "messenger": "Messenger",
                  "threads": "Threads"}


def load_objects(path):
    """Read a file holding one JSON value, a list, or several objects in a row."""
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8").read().strip()
    dec, out, i = json.JSONDecoder(), [], 0
    while i < len(text):
        while i < len(text) and text[i] in " \t\r\n,":
            i += 1
        if i >= len(text):
            break
        obj, i = dec.raw_decode(text, i)
        out.extend(obj if isinstance(obj, list) else [obj])
    return out


def num(v, kind=float):
    try:
        return kind(float(v))
    except (TypeError, ValueError):
        return kind(0)


def metrics(o):
    return {
        "spend": round(num(o.get("spend")), 2),
        "impressions": num(o.get("impressions"), int),
        "link_clicks": num(o.get("inline_link_clicks", o.get("link_clicks")), int),
        "lpv": num(o.get("landing_page_views", o.get("lpv")), int),
        "leads": num(o.get("leads_total", o.get("leads")), int),
    }


def theme_of(name):
    m = re.search(r"PPL\s*([1-5])", name or "", re.I)
    return f"PPL{m.group(1)}" if m else None


def load_index():
    return json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {}


def creative_ids(raw):
    """ad_id -> creative_id from list_ads."""
    out = {}
    for a in load_objects(os.path.join(raw, "ads_list.json")):
        if a.get("campaign_id", CAMPAIGN_ID) != CAMPAIGN_ID:
            continue
        cid = (a.get("creative") or {}).get("id") or a.get("creative_id")
        out[str(a["id"] if "id" in a else a["ad_id"])] = str(cid) if cid else None
    return out


def cmd_need(args):
    idx = load_index()
    for ad_id, cid in creative_ids(args.raw).items():
        entry = idx.get(cid or "")
        if not entry or not os.path.exists(os.path.join(ROOT, entry["image"])):
            print(ad_id)


def save_creative(path, idx):
    c = load_objects(path)[0]
    ad_id, cid = str(c["ad_id"]), str(c.get("creative_id") or "")
    imgs = c.get("images") or []
    rel = None
    if any(i.get("base64") for i in imgs):
        from PIL import Image
        # the cockpit shows square cards: keep the visual closest to 1:1
        cands = [Image.open(io.BytesIO(base64.b64decode(i["base64"]))) for i in imgs if i.get("base64")]
        im = min(cands, key=lambda x: abs(x.width / x.height - 1)).convert("RGB")
        im.thumbnail((800, 800))
        rel = f"assets/crea/ad_{ad_id}.jpg"
        os.makedirs(CREA, exist_ok=True)
        im.save(os.path.join(ROOT, rel), "JPEG", quality=85, optimize=True)
    idx[cid or ad_id] = {
        "ad_id": ad_id,
        "image": rel or idx.get(cid, {}).get("image"),
        "headline": c.get("headline") or "",
        "text": c.get("primary_text") or "",
        "link": c.get("link") or "",
        "is_video": bool(c.get("is_video")),
    }
    return ad_id


def target_label(lo, hi):
    if hi and hi >= 65:
        return f"{lo} ans et +"
    return f"{lo}-{hi} ans"


def cmd_build(args):
    raw = args.raw
    old = json.load(open(os.path.join(DATA, "meta.json"), encoding="utf-8"))
    idx = load_index()
    saved = [save_creative(f, idx) for f in (args.creative_files or [])]

    daily = []
    for o in load_objects(os.path.join(raw, "daily.json")):
        if o.get("campaign_id", CAMPAIGN_ID) != CAMPAIGN_ID:
            continue
        r = {"date": o.get("date_start") or o.get("date"), **metrics(o),
             "reach": num(o.get("reach"), int)}
        daily.append({k: r[k] for k in ["date", "spend", "impressions", "reach", "link_clicks", "lpv", "leads"]})
    daily.sort(key=lambda r: r["date"])
    if not daily:
        sys.exit("daily.json is empty: nothing to build")
    today = dt.date.today().isoformat()
    for r in daily:
        if r["date"] >= today:
            r["partial"] = True

    adsets = {}
    for s in load_objects(os.path.join(raw, "adsets.json")):
        if s.get("campaign_id", CAMPAIGN_ID) != CAMPAIGN_ID:
            continue
        t = s.get("targeting") or {}
        adsets[str(s["id"])] = {
            "name": s.get("name", ""),
            "status": s.get("effective_status") or s.get("status"),
            "daily_budget": num(s.get("daily_budget")) / 100,
            "age_min": t.get("age_min"), "age_max": t.get("age_max"),
        }

    cids = creative_ids(raw)
    ads_raw = [o for o in load_objects(os.path.join(raw, "ads.json"))
               if o.get("campaign_id", CAMPAIGN_ID) == CAMPAIGN_ID]
    by_theme = {}
    for o in ads_raw:
        code = theme_of(o.get("adset_name")) or theme_of(o.get("ad_name"))
        by_theme.setdefault(code, []).append(o)

    themes, ads = [], []
    for code, name in THEMES.items():
        rows = by_theme.get(code, [])
        aset = next((v for k, v in adsets.items() if theme_of(v["name"]) == code), {})
        prev = next((t for t in old.get("themes", []) if t["code"] == code), {})
        tot = {k: sum(metrics(o)[k] for o in rows) for k in ["spend", "impressions", "link_clicks", "lpv", "leads"]}
        tot["spend"] = round(tot["spend"], 2)
        # best ad with a visual = most landing page views
        best_key = prev.get("crea", code.lower())
        ranked = sorted(rows, key=lambda o: metrics(o)["lpv"], reverse=True)
        for o in ranked:
            entry = idx.get(cids.get(str(o["ad_id"])) or "")
            if entry and entry.get("image"):
                best_key = f"ad_{o['ad_id']}"
                break
        themes.append({
            "code": code, "name": name,
            "target": target_label(aset.get("age_min"), aset.get("age_max")) if aset.get("age_min") else prev.get("target", ""),
            "daily_budget": aset.get("daily_budget", prev.get("daily_budget", 0)),
            **tot, "crea": best_key,
        })
        multi = len(rows) > 1
        for o in rows:
            m = re.search(r"Copy\s*(\d+)", o.get("ad_name", ""))
            label = f"{code} · variante {int(m.group(1)) + 1}" if m else f"{code} · {name}" + (" (principale)" if multi else "")
            entry = idx.get(cids.get(str(o["ad_id"])) or "", {})
            ads.append({"name": label, "ad_id": str(o["ad_id"]), "theme": code, **metrics(o),
                        **({"crea": f"ad_{o['ad_id']}"} if entry.get("image") else {})})
    ads.sort(key=lambda a: a["spend"], reverse=True)

    ages = []
    for o in load_objects(os.path.join(raw, "ages.json")):
        if (o.get("age") or "").lower() == "unknown":
            continue
        m = metrics(o)
        ages.append({"age": o.get("age"), **{k: m[k] for k in ["spend", "impressions", "link_clicks", "lpv"]}})
    ages.sort(key=lambda a: a["age"])

    platforms = []
    for o in load_objects(os.path.join(raw, "platforms.json")):
        m = metrics(o)
        p = o.get("publisher_platform") or o.get("platform") or ""
        platforms.append({"platform": PLATFORM_NAMES.get(p, p.title()), **{k: m[k] for k in ["spend", "impressions", "link_clicks", "lpv"]}})
    platforms.sort(key=lambda p: p["spend"], reverse=True)

    budget = dict(old.get("budget", {}))
    if adsets:
        budget["daily_total"] = round(sum(v["daily_budget"] for v in adsets.values()
                                          if v["status"] in (None, "ACTIVE")), 2)

    meta = {**old,
            "updated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=1))).isoformat(timespec="minutes"),
            "budget": budget, "daily": daily, "themes": themes, "ads": ads,
            "ages": ages or old.get("ages", []), "platforms": platforms or old.get("platforms", [])}
    json.dump(meta, open(os.path.join(DATA, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # creatives.json: theme keys (legacy ppl1..ppl5) + every ad with a cached visual
    old_c = json.load(open(os.path.join(DATA, "creatives.json"), encoding="utf-8"))
    creas = {k: v for k, v in old_c.items() if k.startswith("ppl")}
    gallery = []
    for a in ads:
        entry = idx.get(cids.get(a["ad_id"]) or "")
        if not entry or not entry.get("image"):
            continue
        key = f"ad_{a['ad_id']}"
        creas[key] = {"ad_name": a["name"], "headline": entry["headline"], "link": entry["link"],
                      "image": entry["image"], "text": entry["text"]}
        gallery.append({"key": key, "ad_id": a["ad_id"], "theme": a["theme"], "name": a["name"]})
    creas["ads"] = gallery
    json.dump(creas, open(os.path.join(DATA, "creatives.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(idx, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    t = {k: sum(r[k] for r in daily) for k in ["spend", "impressions", "link_clicks", "lpv", "leads"]}
    print(f"Données {daily[0]['date']} → {daily[-1]['date']} ({len(daily)} jours) : "
          f"{t['spend']:.2f} €, {t['impressions']} impressions, {t['link_clicks']} clics, "
          f"{t['lpv']} visites, {t['leads']} leads")
    print(f"{len(ads)} annonces, {len(gallery)} avec visuel, {len(saved)} visuel(s) ajouté(s)")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("need-creatives"); a.add_argument("--raw", required=True)
    b = sub.add_parser("build"); b.add_argument("--raw", required=True)
    b.add_argument("--creative-files", nargs="*")
    args = p.parse_args()
    {"need-creatives": cmd_need, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
