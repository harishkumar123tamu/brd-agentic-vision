"""Agentic vision loop with saved reasoning traces (Level 1 requirement).

Usage:  python code/agent.py [N_CASES=8]
Needs:  GPU, Qwen/Qwen2.5-VL-7B-Instruct in $HF_HOME, outputs from the pipeline:
        out/ids_cam03.parquet, out/ids_cam01.parquet, out/ids_cam02.parquet, out/activity_minutes.csv,
        out/id_events_cam03.csv, out/brd_risk.csv, ground_truth/zones.json, clips.txt
Writes: out/traces/<case_id>/trace.json   full record: plan, tool calls, images, model answers, self-checks, decision
        out/traces/<case_id>/trace.md     human-readable version
        out/traces/<case_id>/*.jpg        every image the agent looked at
        out/traces/summary.csv

The agent does NOT label in one pass. For each case it:
  1. PLANS which tools it needs (the VLM chooses from the tool list),
  2. CALLS the tools (zoom, look back/forward in time, other camera, zone/neighbour check),
  3. ANSWERS with a behavior + confidence,
  4. SELF-CHECKS: compares with the rule label, the zone geometry and neighbouring minutes;
     if they disagree or confidence is low it picks another tool and re-answers (max 3 rounds),
  5. DECIDES and records why.
Case types: uncertain day minute, night minute, "missed feeding" minute of a top-risk cow,
and an ID-swap check (are these the same two cows before and after they were close?).
"""
import os, sys, re, json, subprocess, time
from datetime import timedelta
import numpy as np, pandas as pd, cv2, torch
from PIL import Image

N_CASES = int(sys.argv[1]) if len(sys.argv) > 1 else 8
OUT = "out/traces"; os.makedirs(OUT, exist_ok=True)
MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
CODE = {"cam03": "003", "cam01": "006", "cam02": "017"}
CLASSES = ["lying", "standing", "walking", "feeding", "drinking", "ruminating_lying", "ruminating_standing",
           "grooming", "social_interaction", "other_not_visible"]
Z = json.load(open("ground_truth/zones.json"))

# ---------------------------------------------------------------- data
clips = []
for l in open("clips.txt"):
    p = l.strip(); m = re.search(r"Event(\d{14})(\d{3})", os.path.basename(p))
    if m: clips.append((p, pd.to_datetime(m.group(1), format="%Y%m%d%H%M%S"), m.group(2)))
clips = pd.DataFrame(clips, columns=["path", "start", "code"]).sort_values("start")
ids = {c: pd.read_parquet(f"out/ids_{c}.parquet") for c in CODE if os.path.exists(f"out/ids_{c}.parquet")}
am = pd.read_csv("out/activity_minutes.csv", parse_dates=["minute"])
risk = pd.read_csv("out/brd_risk.csv").sort_values("rank")
events = pd.read_csv("out/id_events_cam03.csv", parse_dates=["start", "end"]) if os.path.exists("out/id_events_cam03.csv") else pd.DataFrame()

# ---------------------------------------------------------------- model
print("loading", MODEL, flush=True)
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL, torch_dtype=torch.bfloat16, device_map="cuda")
proc = AutoProcessor.from_pretrained(MODEL)


def vlm(images, text, max_new=220):
    content = [{"type": "image", "image": im} for im in images] + [{"type": "text", "text": text}]
    msgs = [{"role": "user", "content": content}]
    prompt = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inp = proc(text=[prompt], images=images or None, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = model.generate(**inp, max_new_tokens=max_new, do_sample=False)
    return proc.batch_decode(out[:, inp.input_ids.shape[1]:], skip_special_tokens=True)[0].strip()


def parse_json(s):
    try:
        return json.loads(s[s.find("{"): s.rfind("}") + 1])
    except Exception:
        return {"_unparsed": s}

# ---------------------------------------------------------------- tools
def _clip_at(cam, t):
    c = clips[(clips.code == CODE[cam]) & (clips.start <= t)]
    if c.empty: return None, None
    r = c.iloc[-1]; off = (t - r.start).total_seconds()
    return (r.path, off) if off < 300 else (None, None)


def _frame(cam, t):
    path, off = _clip_at(cam, t)
    if path is None: return None
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-c:v", "hevc", "-ss", f"{off:.2f}", "-i", path,
           "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"]
    buf = subprocess.run(cmd, capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR) if buf else None


def _box(cam, cow, t, tol=20):
    g = ids.get(cam)
    if g is None: return None
    g = g[g.cow_id == cow]
    if g.empty: return None
    i = (g.ts - t).abs().idxmin()
    return g.loc[i] if abs((g.at[i, "ts"] - t).total_seconds()) <= tol else None


def _crop(img, b, pad=0.35, size=448):
    h, w = img.shape[:2]; bw, bh = b.x2 - b.x1, b.y2 - b.y1
    x1, y1 = int(max(0, b.x1 - pad * bw)), int(max(0, b.y1 - pad * bh))
    x2, y2 = int(min(w, b.x2 + pad * bw)), int(min(h, b.y2 + pad * bh))
    c = img[y1:y2, x1:x2].copy()
    cv2.rectangle(c, (int(b.x1 - x1), int(b.y1 - y1)), (int(b.x2 - x1), int(b.y2 - y1)), (0, 0, 255), 3)
    s = size / max(c.shape[:2]); c = cv2.resize(c, (int(c.shape[1] * s), int(c.shape[0] * s)))
    return Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB))


def tool_view(cow, t, cam="cam03", pad=0.35):
    b = _box(cam, cow, t)
    if b is None: return None, f"{cow} not found in {cam} near {t:%H:%M:%S}"
    img = _frame(cam, b.ts)
    if img is None: return None, "frame decode failed"
    return [_crop(img, b, pad)], f"{cam} crop of {cow} at {b.ts:%H:%M:%S} (red box = {cow})"


def tool_zoom(cow, t, cam="cam03"):
    ims, note = tool_view(cow, t, cam, pad=0.08)
    return ims, note.replace("crop", "tight zoom") if ims else note


def tool_look_time(cow, t, cam="cam03"):
    ims, notes = [], []
    for dt in (-20, -10, 0, 10, 20):
        im, note = tool_view(cow, t + timedelta(seconds=dt), cam)
        if im: ims += im; notes.append(f"{dt:+d}s")
    return (ims or None), f"{cam} crops of {cow} at offsets {', '.join(notes) or 'none found'} (left to right)"


def tool_other_camera(cow, t):
    for cam in ("cam02", "cam01"):
        if _box(cam, cow, t, tol=30) is not None:
            return tool_view(cow, t, cam)
    return None, f"{cow} is not identified in Cam 01/Cam 02 near {t:%H:%M} (only seen at the bunk by those cameras)"


def tool_zone_check(cow, t):
    b = _box("cam03", cow, t)
    if b is None: return None, "no Cam 03 box"
    fu, fv = (b.x1 + b.x2) / 2, b.y2
    def dist(poly):
        return cv2.pointPolygonTest(np.asarray(poly, np.float32).reshape(-1, 1, 2), (float(fu), float(fv)), True)
    g = ids["cam03"]; same = g[g.ts == b.ts]
    others = same[same.cow_id != cow]
    h = max(b.y2 - b.y1, 1)
    nn = (np.hypot((others.x1 + others.x2) / 2 - fu, others.y2 - fv) / h).min() if len(others) else np.nan
    return None, (f"bunk-zone distance {dist(Z['cam03']['feed_bunk']):.0f}px (>=0 inside), "
                  f"waterer distance {dist(Z['cam03']['waterer']):.0f}px, nearest cow {nn:.2f} body-heights away, "
                  f"{len(same)} cows visible in Cam 03 at this moment")


TOOLS = {"view": tool_view, "zoom": tool_zoom, "look_time": tool_look_time,
         "other_camera": tool_other_camera, "zone_check": tool_zone_check}
TOOL_DOC = ("view = crop of the cow in the whole-pen camera; zoom = tight crop for head/jaw detail; "
            "look_time = 5 crops from -20 s to +20 s to see movement or posture change; "
            "other_camera = same moment from the bunk cameras if the cow is there; "
            "zone_check = numbers: distance to feed bunk / waterer and to the nearest cow")

# ---------------------------------------------------------------- one behavior case
def run_behavior_case(case):
    cow, t, rule = case["cow_id"], case["time"], case["rule_label"]
    d = os.path.join(OUT, case["case_id"]); os.makedirs(d, exist_ok=True)
    trace = {"case": {k: str(v) for k, v in case.items()}, "steps": []}
    n_img = 0

    def log(kind, **kw):
        trace["steps"].append({"step": len(trace["steps"]) + 1, "kind": kind, **kw})

    def call(tool):
        nonlocal n_img
        ims, note = TOOLS[tool](cow, t)
        files = []
        for im in ims or []:
            n_img += 1; f = f"img{n_img:02d}_{tool}.jpg"; im.save(os.path.join(d, f)); files.append(f)
        log("tool_call", tool=tool, result=note, images=files)
        return ims or [], note

    # 1. PLAN
    plan_txt = vlm([], (f"You are a cattle-behavior agent watching a feedlot pen with cameras. Task: decide what cow {cow} "
                        f"is doing during the minute starting {t:%Y-%m-%d %H:%M} ({'NIGHT, infrared grayscale' if case['night'] else 'daytime'}). "
                        f"Behavior classes: {', '.join(CLASSES)}. Available tools: {TOOL_DOC}. "
                        f"Reply ONLY JSON: {{\"plan\": [up to 3 tool names in order], \"why\": \"<one sentence>\"}}"), 120)
    plan = parse_json(plan_txt); tools = [x for x in plan.get("plan", []) if x in TOOLS] or ["view", "look_time"]
    if "view" not in tools: tools = ["view"] + tools
    log("plan", model_output=plan_txt, tools=tools[:3])

    images, notes = [], []
    for tl in tools[:3]:
        ims, note = call(tl); images += ims; notes.append(f"[{tl}] {note}")
    answer = {}
    for rnd in range(1, 4):
        # 3. ANSWER
        q = (f"Images show cow {cow} (inside the red box). Tool results: {' | '.join(notes)}. "
             f"Which ONE behavior best describes this minute? Classes: {', '.join(CLASSES)}. "
             "Ruminating = steady rhythmic jaw chewing while not eating; feeding = head in/over the feed bunk; "
             "if the cow is not clearly visible use other_not_visible. "
             "Reply ONLY JSON: {\"behavior\": \"<class>\", \"confidence\": 0.0-1.0, \"evidence\": \"<what you saw, max 25 words>\"}")
        ans_txt = vlm(images[-8:], q); answer = parse_json(ans_txt)
        log("answer", round=rnd, model_output=ans_txt)
        beh, conf = answer.get("behavior"), float(answer.get("confidence", 0) or 0)
        # 4. SELF-CHECK
        checks = []
        if beh not in CLASSES: checks.append("answer is not a valid class")
        if beh and rule and beh.split("_")[0] != rule.split("_")[0] and beh != rule:
            checks.append(f"disagrees with rule label '{rule}'")
        if conf < 0.6: checks.append(f"low confidence {conf:.2f}")
        zone_note = next((n for n in notes if n.startswith("[zone_check]")), None)
        if beh == "feeding" and zone_note and "bunk-zone distance -" in zone_note:
            dval = float(re.search(r"bunk-zone distance (-?\d+)", zone_note).group(1))
            if dval < -250: checks.append("says feeding but the cow is far from the bunk")
        if rule == "feeding" and beh != "feeding" and zone_note:
            dv = float(re.search(r"bunk-zone distance (-?\d+)", zone_note).group(1))
            if dv > -150: checks.append("zone_check says the cow is AT the bunk but answer is not feeding")
        if "jaw" in str(answer.get("evidence", "")).lower() and not any(n.startswith("[zoom]") or n.startswith("[other_camera]") for n in notes):
            checks.append("claims jaw movement without a zoom/close-up view (jaw likely not visible)")
        log("self_check", round=rnd, issues=checks or ["consistent"])
        if not checks: break
        order = ["other_camera", "zone_check", "zoom", "look_time"] if rule == "feeding" else ["zone_check", "zoom", "look_time", "other_camera"]
        unused = [x for x in order if x not in tools]
        if not unused or rnd == 3: break
        nxt = unused[0]; tools.append(nxt)
        ims, note = call(nxt); images += ims; notes.append(f"[{nxt}] {note}")
        notes.append(f"[self-check] previous answer '{beh}' had issues: {'; '.join(checks)}. Re-examine.")
    # 5. DECIDE
    beh, conf = answer.get("behavior"), float(answer.get("confidence", 0) or 0)
    last_issues = next((st["issues"] for st in reversed(trace["steps"]) if st["kind"] == "self_check"), [])
    unresolved = [i for i in last_issues if i != "consistent"]
    if unresolved and beh != rule:
        final, how = rule, "kept_rule_label_conflict_unresolved"
    elif beh in CLASSES and conf >= 0.6:
        final, how = beh, "agent_verified" if beh == rule else "agent_corrected_rule"
    else:
        final, how = rule, "kept_rule_label_agent_uncertain"
    log("decision", final_label=final, method=how, unresolved_issues=unresolved if "unresolved" in dir() else [], rule_label=rule, agent_label=beh, agent_confidence=conf)
    trace["final"] = {"label": final, "method": how, "agent_label": beh, "agent_confidence": conf, "rule_label": rule}
    return trace, d

# ---------------------------------------------------------------- ID-swap case
def run_swap_case(case):
    a, b, t0, t1 = case["cow_a"], case["cow_b"], case["start"], case["end"]
    d = os.path.join(OUT, case["case_id"]); os.makedirs(d, exist_ok=True)
    trace = {"case": {k: str(v) for k, v in case.items()}, "steps": []}
    log = lambda kind, **kw: trace["steps"].append({"step": len(trace["steps"]) + 1, "kind": kind, **kw})
    log("plan", tools=["view before", "view after"], why=f"{a} and {b} came within <1 body-height; check the IDs did not swap")
    ims, files = [], []
    for cow in (a, b):
        for label, tt in (("before", t0 - timedelta(seconds=40)), ("after", t1 + timedelta(seconds=40))):
            im, note = tool_view(cow, tt)
            log("tool_call", tool="view", target=f"{cow} {label}", result=note)
            if im:
                f = f"{cow}_{label}.jpg"; im[0].save(os.path.join(d, f)); ims.append(im[0]); files.append(f)
    if len(ims) < 4:
        log("decision", final="cannot verify (cow not visible before/after)"); trace["final"] = {"swap": "unknown"}
        return trace, d
    q = (f"Four crops of black Angus cows (red box). Image 1 = cow {a} before, image 2 = cow {a} after, "
         f"image 3 = cow {b} before, image 4 = cow {b} after. Compare body size, ear tags, white marks, posture/position. "
         "Did the two labels SWAP (i.e. image 2 looks like the cow in image 3 and image 4 like the cow in image 1)? "
         "Reply ONLY JSON: {\"swapped\": true|false|\"unsure\", \"confidence\": 0.0-1.0, \"evidence\": \"<max 30 words>\"}")
    out = vlm(ims, q); ans = parse_json(out)
    log("answer", model_output=out)
    swapped, conf = ans.get("swapped"), float(ans.get("confidence", 0) or 0)
    issues = [] if conf >= 0.6 and swapped in (True, False) else ["low confidence or unsure -> keep IDs, flag for review"]
    log("self_check", issues=issues or ["consistent"])
    final = "swap IDs after this event" if (swapped is True and conf >= 0.6) else "keep IDs" + (" (flagged)" if issues else "")
    log("decision", final=final)
    trace["final"] = {"swap": swapped, "confidence": conf, "action": final}
    return trace, d

# ---------------------------------------------------------------- case selection
def pick_cases(n):
    cases, top = [], list(risk.cow_id.head(3))
    a2 = am[(am.day == "Day 2") & (am.n_obs >= 15)]
    def add(df, tag, k=1):
        for r in df.head(k).itertuples():
            cases.append(dict(case_id=f"{tag}_{r.cow_id}_{r.minute:%m%d_%H%M}", type="behavior", cow_id=r.cow_id,
                              time=r.minute + timedelta(seconds=30), rule_label=r.behavior,
                              night=bool(r.minute.hour < 6 or r.minute.hour >= 19)))
    day = a2[(a2.minute.dt.hour.between(9, 16))]
    night = a2[(a2.minute.dt.hour < 5)]
    add(day[(day.cow_id.isin(top)) & (day.confidence.between(0.5, 0.75))].sample(frac=1, random_state=1), "day_uncertain", 2)
    add(night[night.behavior.isin(["lying", "standing"])].sample(frac=1, random_state=2), "night", 2)
    add(day[(day.cow_id.isin(top)) & (day.behavior == "feeding")].sample(frac=1, random_state=3), "day_feeding", 1)
    add(day[(day.cow_id.isin(top)) & (day.behavior == "lying")].sample(frac=1, random_state=4), "day_lying", 1)
    if len(events):
        ev = events.sort_values("frames", ascending=False).head(2)
        for r in ev.itertuples():
            cases.append(dict(case_id=f"idswap_{r.cow_a}_{r.cow_b}_{r.start:%m%d_%H%M}", type="swap",
                              cow_a=r.cow_a, cow_b=r.cow_b, start=r.start, end=r.end))
    return cases[:n]


def to_md(trace):
    L = [f"# Agent trace: {trace['case'].get('case_id')}", "", "**Case:** " + json.dumps(trace["case"]), ""]
    for s in trace["steps"]:
        L.append(f"## Step {s['step']}: {s['kind']}")
        for k, v in s.items():
            if k in ("step", "kind"): continue
            if k == "images": L += [f"![]({x})" for x in v]
            else: L.append(f"- **{k}**: {v}")
        L.append("")
    L.append("**Final:** " + json.dumps(trace.get("final")))
    return "\n".join(L)


rows = []
for case in pick_cases(N_CASES):
    t0 = time.time()
    try:
        trace, d = (run_swap_case if case["type"] == "swap" else run_behavior_case)(case)
    except Exception as e:
        print("FAILED", case["case_id"], repr(e), flush=True); continue
    trace["seconds"] = round(time.time() - t0, 1)
    json.dump(trace, open(os.path.join(d, "trace.json"), "w"), indent=1, default=str)
    open(os.path.join(d, "trace.md"), "w").write(to_md(trace))
    rows.append(dict(case_id=case["case_id"], type=case["type"], seconds=trace["seconds"],
                     **{k: str(v) for k, v in trace.get("final", {}).items()}))
    print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv(os.path.join(OUT, "summary.csv"), index=False)
print("saved", len(rows), "traces ->", OUT)
