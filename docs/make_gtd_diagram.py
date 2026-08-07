#!/usr/bin/env python3
"""
Builds the AI Weekly Organizer / Daily Brief architecture diagram.

Rebuilt 2026-07-28 from data/daily_brief.py itself.  The first version was drawn
from the README summary and got three things wrong: it showed two Notion
databases instead of three, it claimed two Ollama calls when there are four, and
worst of all it said the model decides what matters most.  It does not.
`deterministic_most_important()` is a pure-Python priority ladder; the model only
writes the sentence.  That split is the whole point of the diagram now.

Same technique as docs/architecture.svg in ai-job-search:
  - static SVG, no <defs>, no markers (rasterizers and HTML sanitizers strip them)
  - arrowheads are literal <polygon> elements
  - every white string sits inside a dark <rect>, so the diagram is legible on
    a white GitHub README and on the dark jasondarrow.com background
  - no Mermaid: it does not render in local markdown viewers or plain HTML
"""

W, H = 1040, 940

STAGE = ("#4c3f91", "#6b5cb8")   # pipeline stage        purple
RULES = ("#1a6b5a", "#2a8b76")   # deterministic Python  green
HUMAN = ("#8a5a00", "#b87b0a")   # my step               amber
SOURCE = ("#4a4a4a", "#6b6b6b")  # external input        grey
OUT = ("#1e3a8a", "#3355b5")     # generated data        blue
AI = ("#7a2318", "#a3392a")      # model                 red
LABEL = "#7c848d"
LINE = "#9aa0a6"

p = []


def box(x, y, w, h, colors, title, sub=None, lines=None, title_y=None):
    fill, stroke = colors
    p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    cx = x + w / 2
    body = ([sub] if sub else []) + list(lines or [])
    if title_y:
        ty = title_y
    elif body:
        ty = y + h / 2 - (len(body) * 8) + 4
    else:
        ty = y + h / 2 + 5
    p.append(f'<text x="{cx}" y="{ty}" text-anchor="middle" fill="#fff" '
             f'font-size="13.5" font-weight="600">{title}</text>')
    for i, s in enumerate(body):
        p.append(f'<text x="{cx}" y="{ty + 17 + i * 15}" text-anchor="middle" '
                 f'fill="#e3e3e3" font-size="11">{s}</text>')


def badge(x, y, text, colors=AI, w=76):
    fill, stroke = colors
    ink = "#ffd9d2" if colors is AI else "#cdf2e6"
    p.append(f'<rect x="{x}" y="{y}" width="{w}" height="17" rx="8.5" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
    p.append(f'<text x="{x + w / 2}" y="{y + 12.5}" text-anchor="middle" fill="{ink}" '
             f'font-size="9.5" font-weight="700" letter-spacing="0.4">{text}</text>')


def label(x, y, text):
    p.append(f'<text x="{x}" y="{y}" fill="{LABEL}" font-size="10.5" '
             f'font-weight="700" letter-spacing="1.5">{text}</text>')


def down(x, y1, y2):
    p.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 9}" stroke="{LINE}" stroke-width="1.6"/>')
    p.append(f'<polygon points="{x},{y2} {x - 3.6},{y2 - 9} {x + 3.6},{y2 - 9}" fill="{LINE}"/>')


def right(y, x1, x2):
    p.append(f'<line x1="{x1}" y1="{y}" x2="{x2 - 9}" y2="{y}" stroke="{LINE}" stroke-width="1.6"/>')
    p.append(f'<polygon points="{x2},{y} {x2 - 9},{y + 3.6} {x2 - 9},{y - 3.6}" fill="{LINE}"/>')


def left(y, x1, x2):
    p.append(f'<line x1="{x1}" y1="{y}" x2="{x2 + 9}" y2="{y}" stroke="{LINE}" stroke-width="1.6"/>')
    p.append(f'<polygon points="{x2},{y} {x2 + 9},{y + 3.6} {x2 + 9},{y - 3.6}" fill="{LINE}"/>')


# ---------------------------------------------------------------- geometry
LX, LW = 30, 232
CX, CW = 330, 380
RX, RW = 778, 232
CC = CX + CW / 2

label(LX, 32, "MY DATA  ·  READ ONLY")
label(CX, 32, "GREEN DECIDES  ·  RED ONLY WRITES")
label(RX, 32, "TRIGGER  &amp;  APP DATA")

# ---- 1 Collect, spanning the three sources
box(CX, 48, CW, 142, STAGE, "1 · Collect",
    "data/daily_brief.py — one job, five reads", title_y=92)

box(LX, 48, LW, 42, SOURCE, "Google Calendar", "today's events")
box(LX, 98, LW, 42, SOURCE, "Gmail", "unread, primary inbox")
box(LX, 148, LW, 42, SOURCE, "Notion", "Tasks · Network · Jobs")
for y in (69, 119, 169):
    right(y, LX + LW, CX)

box(RX, 48, RW, 42, SOURCE, "Weekday cron", "6:00 AM Eastern")
left(69, RX, CX + CW)

# ---- 2 Filter
down(CC, 190, 220)
box(CX, 220, CW, 62, STAGE, "2 · Filter the inbox",
    "narrow promo regex, then one batched model call",
    lines=["when it is unsure it keeps the mail"])
badge(CX + 292, 228, "MODEL")

# ---- 3 Decide  (the point of the whole diagram)
down(CC, 282, 312)
box(CX, 312, CW, 104, RULES, "3 · Decide what matters",
    "a fixed priority ladder in Python, no model involved",
    lines=["HIGH task &gt; live job stage &gt; interview on the calendar",
           "&gt; overdue task &gt; urgent email &gt; first event of the day"])
badge(CX + 274, 320, "PYTHON ONLY", colors=RULES, w=94)

# ---- 4 Write
down(CC, 416, 446)
box(CX, 446, CW, 62, STAGE, "4 · Write the words",
    "the sentence, prep notes, the narrative paragraph",
    lines=["canned text if the model is unavailable"])
badge(CX + 292, 454, "MODEL")

# ---- 5 Publish
down(CC, 508, 538)
box(CX, 538, CW, 52, OUT, "5 · Publish",
    "data/daily-brief.json — atomic replace, no history")

# ---- the card
down(CC, 590, 620)
box(CX, 620, CW, 52, STAGE, "Daily Brief card",
    "Next.js planner reads GET /api/brief")

box(RX, 620, RW, 52, RULES, "SQLite · gtd.db", "calendar, habits, goals")
left(646, RX, CX + CW)

# ---- me
down(CC, 672, 702)
box(CX, 702, CW, 38, HUMAN, "ME · read it with the first coffee")

# ---------------------------------------------------------------- footer band
label(LX, 786, "ALL OF THE ABOVE RUNS ON ONE LINUX BOX IN MY HOME OFFICE")

box(30, 800, 326, 54, AI, "Ollama · llama3.1:8b",
    "four narrow calls, my hardware, no API")
box(372, 800, 326, 54, SOURCE, "Ubuntu · PM2 · cron",
    "restarts on reboot, no babysitting")
box(714, 800, 326, 54, RULES, "No subscription",
    "and no calendar or mail leaves the network")

p.append(f'<text x="30" y="892" fill="{LABEL}" font-size="11.5">'
         'The model never chooses the priority.  Python ranks the day from a fixed ladder, then the model is handed the winner '
         'and asked only to phrase it.</text>')
p.append(f'<text x="30" y="912" fill="{LABEL}" font-size="11.5">'
         'Every model call has a deterministic fallback, so a dead model degrades the brief instead of breaking it.</text>')

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
    f'role="img" aria-labelledby="gttl gdsc">\n'
    '<title id="gttl">AI Weekly Organizer daily brief architecture</title>\n'
    '<desc id="gdsc">A weekday cron job runs one Python script that reads Google Calendar, Gmail, '
    'and three Notion databases. A narrow regex plus one batched local-model call filters the inbox. '
    'A fixed priority ladder written in Python then decides which single item matters most, with no '
    'model involved. Only after that is a locally hosted Llama 3.1 model asked to phrase the sentence, '
    'write prep notes, and draft a narrative paragraph, each with a deterministic fallback. The result '
    'is one JSON file the Next.js planner renders as a Daily Brief card. Everything runs on a '
    'self-hosted Linux server with no subscription and no data leaving the home network.</desc>\n'
    + "\n".join(p) + "\n</svg>\n"
)

open("gtd-architecture.svg", "w").write(svg)
print("wrote gtd-architecture.svg", len(svg), "bytes")
