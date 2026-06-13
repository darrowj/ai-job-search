"""
resume_generator.py

Opens "Darrow Jason FINAL resume.docx" as a formatting template and replaces
only the dynamic sections (summary + Voya bullets) with content from the
tailored JSON produced by resume_tailor.py.  All margins, fonts, colors,
borders, and static sections are inherited from the template unchanged.

Usage:
    python3 resume_generator.py --input output/tailored_Acme.json
    python3 resume_generator.py --input output/tailored_Acme.json --output personal/Acme_Resume.docx
"""

import argparse
import copy
import json
import os

from docx import Document
from docx.oxml.ns import qn

# ── Args ───────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Generate tailored resume Word doc")
parser.add_argument(
    "--input",
    required=True,
    help="Tailored JSON file (e.g. output/tailored_Acme.json)",
)
parser.add_argument(
    "--output",
    default=os.path.join("personal", "Jason_Darrow_Resume.docx"),
    help="Output filename (default: personal/Jason_Darrow_Resume.docx)",
)
parser.add_argument(
    "--template",
    default=os.path.join("personal", "Darrow Jason FINAL resume.docx"),
    help="Template .docx to use as the formatting base",
)
args = parser.parse_args()

os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
print(f"Template : {args.template}", flush=True)
print(f"Input    : {args.input}", flush=True)

# ── Load data ──────────────────────────────────────────────────────────────

with open(args.input) as f:
    tailored = json.load(f)

# ── Open template ──────────────────────────────────────────────────────────

doc = Document(args.template)

# ── Helpers ────────────────────────────────────────────────────────────────

def replace_para_text(para, new_text):
    """
    Replace all text in a paragraph's runs with new_text, preserving the
    formatting (font, size, color, bold, italic) of the first run.
    """
    if not para.runs:
        para.add_run(new_text)
        return
    para.runs[0].text = new_text
    for run in para.runs[1:]:
        run.text = ""


def remove_para(para):
    """Remove a paragraph element from the document."""
    para._element.getparent().remove(para._element)


def set_xml_para_text(p_elem, text):
    """
    Set the visible text of a raw lxml <w:p> element.
    Clears all runs then sets the first run's <w:t> to text.
    """
    runs = p_elem.findall(".//" + qn("w:r"))
    if not runs:
        return
    for r in runs:
        for t in r.findall(qn("w:t")):
            t.text = ""
    ts = runs[0].findall(qn("w:t"))
    if ts:
        ts[0].text = text
        # xml:space="preserve" prevents Word from stripping leading/trailing spaces
        ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


# ── 0. Strip template-specific page-break layout from generated docs ───────
# The FINAL resume has a hardcoded page break inside the BoA role description
# paragraph that forces a "Page Two" header at a fixed position.  That only
# works when content fills page 1 exactly.  In generated resumes the content
# length varies, so we remove the break and the "Page Two" header line and
# let Word paginate naturally.

PAGE_BREAK_ANCHOR  = "Served as Application Manager"
PAGE_TWO_HEADER    = "Page Two"
BOA_CONTINUED      = "BANK OF AMERICA (Continued)"

# Walk a copy of the list — we may remove items mid-iteration
for para in list(doc.paragraphs):
    txt = para.text.strip()

    # Remove the run containing the page break from the BoA role description
    if PAGE_BREAK_ANCHOR in txt:
        for r in para._element.findall(".//" + qn("w:r")):
            for br in r.findall(qn("w:br")):
                if br.get(qn("w:type")) == "page":
                    r.getparent().remove(r)
                    print("✓ Hardcoded page break removed", flush=True)
                    break

    # Remove the "Page Two" header paragraph entirely
    if PAGE_TWO_HEADER in txt:
        remove_para(para)
        print("✓ Page Two header removed", flush=True)

    # Remove the "BANK OF AMERICA (Continued)" label — redundant without page break
    if txt == BOA_CONTINUED:
        remove_para(para)
        print("✓ BoA (Continued) label removed", flush=True)

# ── 1. Replace the summary paragraph ──────────────────────────────────────
# The summary is the first paragraph whose text starts with the known anchor.

SUMMARY_ANCHOR = "IT Delivery Manager with experience"

for para in doc.paragraphs:
    if para.text.strip().startswith(SUMMARY_ANCHOR):
        replace_para_text(para, tailored["tailored_summary"])
        print("✓ Summary replaced", flush=True)
        break
else:
    print("⚠ Summary paragraph not found — check SUMMARY_ANCHOR", flush=True)

# ── 2. Replace Voya Financial bullets ─────────────────────────────────────
# Collect the tailored Voya bullets from the JSON.

selected_voya = [
    b["bullet"]
    for b in tailored.get("selected_bullets", [])
    if b.get("company") == "Voya Financial"
]

# Walk paragraphs to find:
#   - all existing List Paragraph bullets under the "IT Delivery Manager" role
#   - the BANK OF AMERICA paragraph that follows them (insertion anchor)

in_voya_role = False
voya_bullet_paras = []
boa_para = None

for para in doc.paragraphs:
    txt = para.text.strip()
    style = para.style.name

    # The role line is a Normal paragraph with exactly "IT Delivery Manager"
    if style == "Normal" and txt == "IT Delivery Manager":
        in_voya_role = True
        continue

    if in_voya_role:
        if style == "Normal" and txt.startswith("BANK OF AMERICA"):
            boa_para = para
            in_voya_role = False
            break
        if style == "List Paragraph" and txt:
            voya_bullet_paras.append(para)

if not voya_bullet_paras:
    print("⚠ Voya bullet paragraphs not found", flush=True)
elif not boa_para:
    print("⚠ BANK OF AMERICA anchor paragraph not found", flush=True)
else:
    n_existing = len(voya_bullet_paras)
    n_selected = len(selected_voya)

    if n_selected == 0:
        print("⚠ No Voya bullets in tailored JSON — template bullets left unchanged", flush=True)
    elif n_selected <= n_existing:
        # Replace the first n_selected paragraphs; remove the rest
        for i, para in enumerate(voya_bullet_paras):
            if i < n_selected:
                replace_para_text(para, selected_voya[i])
            else:
                remove_para(para)
        print(
            f"✓ Voya bullets: replaced {n_selected}, removed {n_existing - n_selected}",
            flush=True,
        )
    else:
        # Fill all existing paragraphs, then clone extras before boa_para
        for i, para in enumerate(voya_bullet_paras):
            replace_para_text(para, selected_voya[i])

        template_bullet_elem = voya_bullet_paras[0]._element
        last_elem = voya_bullet_paras[-1]._element  # track insertion point
        for bullet_text in selected_voya[n_existing:]:
            new_p = copy.deepcopy(template_bullet_elem)
            set_xml_para_text(new_p, bullet_text)
            # addnext inserts immediately after the last bullet, before any spacer
            last_elem.addnext(new_p)
            last_elem = new_p  # advance insertion point

        print(
            f"✓ Voya bullets: replaced {n_existing}, added {n_selected - n_existing}",
            flush=True,
        )

# ── Save ───────────────────────────────────────────────────────────────────

doc.save(args.output)
print(f"✓ Resume saved: {args.output}", flush=True)
