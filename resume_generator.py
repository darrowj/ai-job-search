from docx import Document
from docx.shared import Pt, RGBColor, Inches, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import json
import argparse

parser = argparse.ArgumentParser(description="Generate tailored resume Word doc")
parser.add_argument("--input", required=True, help="Tailored JSON file to use")
parser.add_argument("--output", default="Jason_Darrow_Resume.docx", help="Output filename")
args = parser.parse_args()

# ── Load data ──────────────────────────────────────────────────────────────

with open("master_resume.json", "r") as f:
    master = json.load(f)

with open(args.input, "r") as f:
    tailored = json.load(f)

# ── Helpers ────────────────────────────────────────────────────────────────

def set_font(run, bold=False, italic=False, size=10.5, color=None):
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)

def add_paragraph_shading(paragraph, fill_color):
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_color)
    pPr.append(shd)

def add_paragraph_border(paragraph, bottom=True, top=False, color="000000", size=12):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    if bottom:
        bdr = OxmlElement('w:bottom')
        bdr.set(qn('w:val'), 'single')
        bdr.set(qn('w:sz'), str(size))
        bdr.set(qn('w:space'), '0')
        bdr.set(qn('w:color'), color)
        pBdr.append(bdr)
    if top:
        bdr = OxmlElement('w:top')
        bdr.set(qn('w:val'), 'single')
        bdr.set(qn('w:sz'), str(size))
        bdr.set(qn('w:space'), '0')
        bdr.set(qn('w:color'), color)
        pBdr.append(bdr)
    pPr.append(pBdr)

def add_right_tab(paragraph, pos=10204):
    pPr = paragraph._p.get_or_add_pPr()
    tabs = OxmlElement('w:tabs')
    tab = OxmlElement('w:tab')
    tab.set(qn('w:val'), 'right')
    tab.set(qn('w:pos'), str(pos))
    tabs.append(tab)
    pPr.append(tabs)

def add_bullet(doc, text, italic=True, bold=False):
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    set_font(run, italic=italic, bold=bold, size=10.5)
    p.paragraph_format.space_after = Pt(0)
    return p

def add_section_header(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_font(run, bold=True, size=10.5)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_paragraph_shading(p, "D9D9D9")
    add_paragraph_border(p, bottom=True, color="000000", size=12)
    p.paragraph_format.space_after = Pt(0)
    return p

def add_spacer(doc, size=7):
    p = doc.add_paragraph()
    run = p.add_run("")
    run.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(0)
    return p

def add_company_line(doc, company, dates):
    p = doc.add_paragraph()
    r1 = p.add_run(company)
    set_font(r1, size=10.5)
    p.add_run("\t")
    r2 = p.add_run(dates)
    set_font(r2, bold=True, size=10.5)
    p.paragraph_format.space_after = Pt(0)
    add_right_tab(p)
    return p

def add_role_desc(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_font(run, size=10.5)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(2)
    return p

# ── Build Document ─────────────────────────────────────────────────────────

doc = Document()

# Set margins to match original
section = doc.sections[0]
section.page_width    = Inches(8.5)
section.page_height   = Inches(11)
section.top_margin    = Twips(576)
section.bottom_margin = Twips(864)
section.left_margin   = Twips(1008)
section.right_margin  = Twips(1008)

# Clear header
section.header.is_linked_to_previous = False
for p in section.header.paragraphs:
    for r in p.runs:
        r.text = ""

identity = master["identity"]

# ── HEADER ────────────────────────────────────────────────────────────────

for line in [identity["name"], "774-573-8354", identity["location"], identity["email"]]:
    p = doc.add_paragraph()
    run = p.add_run(line)
    set_font(run, bold=True, size=10.5)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_paragraph_shading(p, "F2F2F2")
    p.paragraph_format.space_after = Pt(0)

# Divider line
p = doc.add_paragraph()
add_paragraph_shading(p, "F2F2F2")
add_paragraph_border(p, bottom=True, color="000000", size=24)
p.paragraph_format.space_after = Pt(0)

# Title
p = doc.add_paragraph()
run = p.add_run("IT LEADER")
set_font(run, bold=True, size=13)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(6)

# Subtitle bar
p = doc.add_paragraph()
run = p.add_run("IT Consulting | Data Integrity | Service Management")
set_font(run, bold=True, size=10.5)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
add_paragraph_border(p, top=True, bottom=True, color="D9D9D9", size=4)
p.paragraph_format.space_after = Pt(0)

add_spacer(doc, 6)

# ── SUMMARY ───────────────────────────────────────────────────────────────

p = doc.add_paragraph()
run = p.add_run(tailored["tailored_summary"])
set_font(run, size=10.5)
p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
p.paragraph_format.space_after = Pt(0)

add_spacer(doc)

# ── KEY CONTRIBUTIONS ─────────────────────────────────────────────────────

add_spacer(doc)
add_section_header(doc, "KEY CONTRIBUTIONS")
add_spacer(doc)

key_contribs = [
    "IT Lead for a business project overseeing 30 application teams with a $2M+ budget",
    "Diligently manage and oversee budgets and planning on projects from $250K to $3M.",
    "Architect, Designer and Developer for a project to create an aircraft residual calculator for the Corporate Aircraft Finance Group of Bank of America Leasing responsible for $1.2B in business.",
    "Technical Team Leader for the corporate site www.bankofamericaleasing.com, $32B in managed assets.",
]
for item in key_contribs:
    add_bullet(doc, item, italic=False, bold=True)

add_spacer(doc)

# ── CAREER EXPERIENCE ─────────────────────────────────────────────────────

add_section_header(doc, "CAREER EXPERIENCE")
add_spacer(doc)

# Group selected bullets by company/title
grouped = {}
for b in tailored["selected_bullets"]:
    key = f"{b['company']}||{b['title']}"
    if key not in grouped:
        grouped[key] = []
    grouped[key].append(b["bullet"])

# Voya Financial
add_company_line(doc, "Voya Financial", "October 2018 – Present")
p = doc.add_paragraph()
run = p.add_run("IT Delivery Manager")
set_font(run, bold=True, size=10.5)
p.paragraph_format.space_after = Pt(0)

add_role_desc(doc, "Oversees delivery, and execution of business prioritized IT programs and projects. Responsible for providing guidance and structure to project teams. These teams are comprised of a combination of vendor and FTE resources who are both onshore and offshore.")

for b in grouped.get("Voya Financial||IT Delivery Manager", []):
    add_bullet(doc, b)
add_spacer(doc)

# Bank of America header
add_company_line(doc, "Bank of America", "February 2001 – October 2018")

# Service Delivery Consultant
p = doc.add_paragraph()
r1 = p.add_run("Service Delivery Consultant/Tech Team Manager")
set_font(r1, bold=True, size=10.5)
r2 = p.add_run(", ")
set_font(r2, size=10.5)
r3 = p.add_run("February 2012 – Present")
set_font(r3, italic=True, size=10.5)
p.paragraph_format.space_after = Pt(0)

add_role_desc(doc, "Serve as an application manager supporting different lines of business while overseeing multiple financial and regulatory risk aligned applications. Manage a team of business analysts and developers to support both BAU and Initiative efforts.")

for b in grouped.get("Bank of America||Service Delivery Consultant / Tech Team Manager", []):
    add_bullet(doc, b)
add_spacer(doc)

# Technical Project Team Manager
p = doc.add_paragraph()
r1 = p.add_run("Technical Project Team Manager")
set_font(r1, bold=True, size=10.5)
r2 = p.add_run(", ")
set_font(r2, size=10.5)
r3 = p.add_run("August 2008 – February 2012")
set_font(r3, italic=True, size=10.5)
p.paragraph_format.space_after = Pt(0)

add_role_desc(doc, "Spearheaded technical team's projects during all phases of the SDLC to completion. Managed and oversaw contractors, consultants and fulltime associates located in the U.S. and internationally.")

for b in [
    "Engaged with the Client Onboarding program to implement a document management solution using the Google Search appliance.",
    "Partnered with the Know Your Customer (KYC) program in completing multiple projects to create a front end portal to be used by business partners.",
    "Implemented a new frontend portal for the Party to Account program to drive efficiency and streamline processes.",
]:
    add_bullet(doc, b)
add_spacer(doc)

# Web Application Architect
p = doc.add_paragraph()
r1 = p.add_run("Web Application Architect")
set_font(r1, bold=True, size=10.5)
r2 = p.add_run(", ")
set_font(r2, size=10.5)
r3 = p.add_run("February 2001 – August 2008")
set_font(r3, italic=True, size=10.5)
p.paragraph_format.space_after = Pt(0)

add_role_desc(doc, "Operated as senior developer for an Internet facing web based asset management system built on the Spring Framework, Hibernate and AJAX for the UI.")

for b in [
    "Functioned as Architect, Designer and Developer on a project to create an aircraft residual calculator for the Corporate Aircraft Finance Group of Bank of America Leasing which generated $1.2B in business for 2006.",
    "Served as Technical Team Leader for the corporate site www.bankofamericaleasing.com, a leasing company responsible for $32B in managed assets.",
    "Recognized and selected by CIO to fill the role Leasing Domain Architect.",
    "Implemented Java to pull data from a Data Warehouse, convert to XML and batch process data with a third party financial calculator to give daily snapshots of the company portfolios and their profitability.",
]:
    add_bullet(doc, b)
add_spacer(doc)

# Click2Learn
add_company_line(doc, "Click2Learn.com", "February 2000 – January 2001")
p = doc.add_paragraph()
run = p.add_run("Senior Developer")
set_font(run, bold=True, size=10.5)
p.paragraph_format.space_after = Pt(0)

add_role_desc(doc, "Acted as senior developer for Custom Services Group which provided eLearning software development services for Fortune 1000 companies and was directly involved in major projects throughout the entire life cycle.")

for b in [
    "Completed projects with Microsoft, Prudential, Fidelity, Princeton Review and Data Dimension International.",
    "Used Java, ASP, DHTML, CSS and JavaScript enabled web sites to collect user data.",
]:
    add_bullet(doc, b)

# ── EDUCATION ─────────────────────────────────────────────────────────────

add_spacer(doc)
add_section_header(doc, "EDUCATION/CERTIFICATE")
add_spacer(doc)

for bold_part, normal_part in [
    ("Master of Science, Information Systems (Distinction), ", "Bentley College"),
    ("Bachelor of Science, Management of Information Systems (Magna Cum Laude), ", "Northeastern University"),
]:
    p = doc.add_paragraph()
    r1 = p.add_run(bold_part)
    set_font(r1, bold=True, size=10.5)
    r2 = p.add_run(normal_part)
    set_font(r2, size=10.5)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)

for cert in [
    "Project Management Professional (PMP) certified – Oct 2018 – Oct 2026",
    "Certified ScrumMaster, CSM: Jan. 2018 – Jan. 2026",
    "Retirement Income Certified Professional (RICP) April 2022 – Dec. 2025",
]:
    p = doc.add_paragraph()
    run = p.add_run(cert)
    set_font(run, bold=True, italic=True, size=10.5)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)

# ── Save ──────────────────────────────────────────────────────────────────

doc.save(args.output)
print(f"Resume saved: {args.output}")