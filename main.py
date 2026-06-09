import os, csv, json, datetime as dt, urllib.request, urllib.parse

AUTH    = os.environ["KMA_KEY"]
WEBHOOK = os.environ.get("WEBHOOK")      # Slack/Discord 웹훅 (선택)
STN     = "820"      # ⚠ 가까운 AWS 지점번호로 교체
RN_COL  = 9           # ⚠ 강수량 컬럼 인덱스(endpoint마다 다름) 교체
CSV     = "data.csv"

# --- 기준값 ---
RN_MIN, MIT_H, DUR_MIN, INT_MIN = 0.1, 6, 3, 10
#  강우판정(mm)  무강우분리(h) 지속(h)  최대시간강도(mm/h)

def fetch():
    now = dt.datetime.now()
    p = {"tm1": (now-dt.timedelta(hours=48)).strftime("%Y%m%d%H00"),
         "tm2": now.strftime("%Y%m%d%H00"), "stn": STN, "help": 0, "authKey": AUTH}
    # ⚠ URL은 API허브에서 활용신청한 AWS 시간자료 샘플 URL로 교체
    url = "https://apihub.kma.go.kr/api/typ01/url/awsh.php?var=RN&tm=201508121500&help=1&authKey=Ib0uINXMRBi9LiDVzCQYHw" + urllib.parse.urlencode(p)
    raw = urllib.request.urlopen(url, timeout=30).read().decode("euc-kr", "ignore")
    out = []
    for ln in raw.splitlines():
        if not ln or ln.startswith("#"): continue
        c = ln.split()
        try:
            t = dt.datetime.strptime(c[0], "%Y%m%d%H%M")
            rn = max(float(c[RN_COL]), 0.0)
            out.append((t, rn))
        except: pass
    return out

def load():
    if not os.path.exists(CSV): return {}
    return {t: float(r) for t, r in csv.reader(open(CSV))}

def events(series):
    evs, cur, gap = [], [], 0
    for t, rn in series:
        if rn >= RN_MIN: cur.append((t, rn)); gap = 0
        elif cur:
            gap += 1
            if gap >= MIT_H: evs.append(cur); cur, gap = [], 0
    if cur: evs.append(cur)
    res = []
    for e in evs:
        dur = int((e[-1][0]-e[0][0]).total_seconds()//3600)+1
        res.append({"s": e[0][0], "e": e[-1][0], "tot": round(sum(r for _, r in e), 1),
                    "dur": dur, "imax": max(r for _, r in e)})
    return res

def alert(msg):
    print(msg)
    if WEBHOOK:
        req = urllib.request.Request(WEBHOOK, json.dumps({"text": msg}).encode(),
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)

d = load()
for t, rn in fetch(): d[t.isoformat()] = rn
with open(CSV, "w", newline="") as f:
    csv.writer(f).writerows(sorted(d.items()))

seen = set(open("seen.txt").read().split()) if os.path.exists("seen.txt") else set()
series = [(dt.datetime.fromisoformat(t), rn) for t, rn in sorted(d.items())]
for e in events(series):
    k = e["s"].isoformat()
    if e["dur"] >= DUR_MIN and e["imax"] >= INT_MIN and k not in seen:
        alert(f"[강우기준 충족] {e['s']:%m-%d %H시}~{e['e']:%m-%d %H시} "
              f"총{e['tot']}mm·지속{e['dur']}h·최대{e['imax']}mm/h → 촬영 검토")
        seen.add(k)
open("seen.txt", "w").write("\n".join(sorted(seen)))
