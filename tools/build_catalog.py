"""Builds data/catalog.json (schemes, eligibility rules, source documents) from the research notes.

Run: python tools/build_catalog.py
"""
import json
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
R = {x['id']: x for x in json.load(open(ROOT / 'data/research/scheme_research.json'))}

def q(sid, key):
    """quote/location for an eligibility field from the research file"""
    e = (R[sid].get('eligibility') or {}).get(key) or {}
    out = {}
    if e.get('location'): out['location'] = e['location']
    if e.get('quote') and e.get('quote_verbatim'): out['quote'] = e['quote']
    return out

def other(sid, idx):
    it = (R[sid].get('eligibility') or {}).get('other_conditions', [])[idx]
    o = {}
    if it.get('location'): o['location'] = it['location']
    if it.get('quote'): o['quote'] = it['quote']
    return o

C = lambda field, op, value: {'field': field, 'op': op, 'value': value}
ANY = lambda *c: {'any': list(c)}
ALL = lambda *c: {'all': list(c)}
POST_MATRIC = ['class_11_12', 'diploma', 'ug', 'pg', 'phd']
NE = ['AR', 'AS', 'MN', 'ML', 'MZ', 'NL', 'SK', 'TR']
PROF_DEGREE = ANY(ALL(C('level', 'in', ['ug']), C('course_type', 'in', ['technical', 'medical', 'professional_other'])),
                  ALL(C('level', 'in', ['pg']), C('course_type', 'in', ['mba_mca'])))

def rule(rid, label, when, src, extra=None):
    r = {'id': rid, 'label': label, 'when': when, 'source': src}
    if extra: r.update(extra)
    return r

schemes = []
docs = []
def doc(did, title, url, version, schemes_, kind='guidelines', note=None):
    d = {'id': did, 'title': title, 'url': url, 'version': version, 'scheme_ids': schemes_, 'kind': kind}
    if note: d['note'] = note
    docs.append(d)

# ---------------------------------------------------------------- 1 CSSS
s = 'pm-usp-csss'
doc('csss-2024', 'PM-USP Central Sector Scheme of Scholarship: guidelines (updated 07-02-2024)',
    'https://scholarships.gov.in/public/schemeGuidelines/CSSS_GUIDLINES_07022024_updated.pdf', 'Applicable from 2022-23; file dated 07-02-2024', [s])
schemes.append(dict(id=s, name='PM-USP Central Sector Scheme of Scholarship for College and University Students', short='Central Sector Scholarship (CSSS)',
  ministry='Ministry of Education (Higher Education)', kind='central', status='active',
  for_whom='Top 20% scorers in Class 12 going to college', levels='UG and PG (regular degree courses, not diploma)',
  benefit='₹12,000 a year for the first three years of graduation; ₹20,000 a year at postgraduation (and years 4–5 of integrated courses)', benefit_inr_per_year=12000,
  apply_url='https://scholarships.gov.in', window='National Scholarship Portal (NSP), usually June to October',
  rules=[
    rule('income', 'Family income up to ₹4.5 lakh a year', C('income', 'lte', 450000), 'csss-2024', q(s, 'income_ceiling_inr')),
    rule('marks', 'Above the 80th percentile of your Class 12 board, in your stream', C('class12_percentile', 'gt', 80), 'csss-2024', q(s, 'min_marks')),
    rule('course', 'Regular UG or PG degree course (not diploma, not distance mode)', ALL(C('level', 'in', ['ug', 'pg']), C('study_mode', 'eq', 'regular')), 'csss-2024', q(s, 'course_levels')),
    rule('no-other', 'Not receiving another scholarship or fee waiver', C('other_scholarship', 'eq', False), 'csss-2024', {'location': 'Section 4(iv)'}),
  ],
  checks=[{'text': 'Your college must be recognised by AICTE or the relevant regulator.', 'source': 'csss-2024', 'location': 'Section 4(iii)'}],
  notes=['From 2026-27 the NSP lets students hold one merit-based plus welfare-based scholarships, which may relax the "no other scholarship" rule. Confirm on NSP before giving up another scholarship.']))

# ---------------------------------------------------------------- 2 PMS-SC
s = 'pms-sc'
doc('pms-sc-2021', 'Post Matric Scholarship for SC students: guidelines 2020-21 to 2025-26',
    'https://sje.gujarat.gov.in/dscw/assets/downloads/gr6_dscw_sje_02092022.pdf', 'MoSJE guidelines, March 2021 (copy hosted by Govt of Gujarat; the MoSJE PDF is a scanned image)', [s])
schemes.append(dict(id=s, name='Post Matric Scholarship for Students belonging to Scheduled Castes', short='Post-Matric Scholarship (SC)',
  ministry='Ministry of Social Justice & Empowerment', kind='central', status='active',
  for_whom='SC students from Class 11 up to PhD', levels='Class 11–12, ITI/polytechnic, UG, PG, PhD',
  benefit='Compulsory fees (including tuition) plus an academic allowance of ₹2,500–₹13,500 a year depending on course and hostel', benefit_inr_per_year=13500,
  apply_url='https://scholarships.gov.in', window='NSP or your state scholarship portal; state deadlines vary (often October–November)',
  rules=[
    rule('category', 'Belongs to a Scheduled Caste of your State/UT', C('category', 'in', ['sc']), 'pms-sc-2021', q(s, 'categories')),
    rule('income', "Parents' income up to ₹2.5 lakh a year", C('income', 'lte', 250000), 'pms-sc-2021', q(s, 'income_ceiling_inr')),
    rule('level', 'Studying after Class 10 (Class 11 up to PhD)', C('level', 'in', POST_MATRIC), 'pms-sc-2021', {'location': 'Sections 3 and 5.2'}),
    rule('no-other', 'Not holding another scholarship or stipend', C('other_scholarship', 'eq', False), 'pms-sc-2021', other(s, 2)),
  ],
  checks=[{'text': 'Not eligible for a second course at the same stage (e.g. a second graduation).', 'source': 'pms-sc-2021', 'location': 'Section 5.5'}],
  notes=['The guideline period ends with 2025-26, but states are running the scheme for 2026-27. News reports (March 2026) say the income limit may rise to ₹4.5 lakh; that is not official yet.']))

# ---------------------------------------------------------------- 3 YASASVI PMS
s = 'pm-yasasvi-pms-obc-ebc-dnt'
doc('yasasvi-pms', 'PM YASASVI: Post Matric Scholarship for OBC, EBC and DNT students (guidelines)',
    'https://scholarships.gov.in//public/schemeGuidelines/HP_state_scheme/Centrally%20Sponsored%20Scheme%20of%20Post%20Matric%20Scholarship%20Scheme%20for%20OBC_scheme.pdf', '2021-22 to 2025-26', [s])
schemes.append(dict(id=s, name='PM YASASVI Post-Matric Scholarship for OBC, EBC and DNT Students', short='PM YASASVI Post-Matric (OBC/EBC/DNT)',
  ministry='Ministry of Social Justice & Empowerment', kind='central', status='active',
  for_whom='OBC, EBC and DNT students after Class 10', levels='Class 11–12, ITI/polytechnic, UG, PG, PhD',
  benefit='₹5,000 to ₹20,000 a year (academic allowance plus tuition), depending on course group', benefit_inr_per_year=20000,
  apply_url='https://scholarships.gov.in', window='NSP or your state portal; state deadlines vary',
  rules=[
    rule('category', 'OBC, EBC or DNT', C('category', 'in', ['obc', 'ebc', 'dnt']), 'yasasvi-pms', {'location': 'Clause 5(i)'}),
    rule('income', "Parents' income up to ₹2.5 lakh a year", C('income', 'lte', 250000), 'yasasvi-pms', q(s, 'income_ceiling_inr')),
    rule('level', 'Studying after Class 10', C('level', 'in', POST_MATRIC), 'yasasvi-pms', {'location': 'Clause 5(iii)'}),
  ],
  checks=[{'text': 'Only two boys of the same parents can get it (no such limit for girls).', 'source': 'yasasvi-pms', 'location': 'Section 16.4 of the umbrella guidelines'},
          {'text': 'Correspondence/online students do not get the academic allowance.', 'source': 'yasasvi-pms', 'location': 'Note 1 under 7.1'}],
  notes=['Guideline period ends with 2025-26; states are still running it in 2026-27.']))

# ---------------------------------------------------------------- 4 YASASVI top class school
s = 'pm-yasasvi-top-class-school'
doc('yasasvi-tcs', 'PM YASASVI: Top Class Education in Schools for OBC, EBC and DNT students',
    'https://scholarships.gov.in/public/schemeGuidelines/3061_G.pdf', 'NSP guideline (current)', [s])
schemes.append(dict(id=s, name='PM YASASVI Top Class Education in Schools for OBC, EBC and DNT Students', short='PM YASASVI Top Class School',
  ministry='Ministry of Social Justice & Empowerment', kind='central', status='active',
  for_whom='OBC, EBC and DNT students in Class 9–12 at notified top schools', levels='Class 9–12',
  benefit='Up to ₹75,000 a year (Class 9–10) or ₹1,25,000 a year (Class 11–12) for tuition, hostel and school charges', benefit_inr_per_year=75000,
  apply_url='https://scholarships.gov.in', window='NSP; slots announced around April',
  rules=[
    rule('category', 'OBC, EBC or DNT', C('category', 'in', ['obc', 'ebc', 'dnt']), 'yasasvi-tcs', q(s, 'categories')),
    rule('income', 'Household income below ₹2.5 lakh a year', C('income', 'lt', 250000), 'yasasvi-tcs', q(s, 'income_ceiling_inr')),
    rule('level', 'In Class 9, 10, 11 or 12', C('level', 'in', ['class_9_10', 'class_11_12']), 'yasasvi-tcs', {'location': 'Section 1'}),
  ],
  checks=[{'text': 'Your school must be on the list of Top Class Schools identified under the scheme.', 'source': 'yasasvi-tcs', 'location': 'Section 2'},
          {'text': 'Selection is on merit, by marks in the previous class.', 'source': 'yasasvi-tcs', 'location': 'Sections 3(e), 3(g)'}],
  notes=[]))

# ---------------------------------------------------------------- 5 YASASVI top class college
s = 'pm-yasasvi-top-class-college'
doc('yasasvi-tcc', 'PM YASASVI: Top Class Education in College for OBC, EBC and DNT students',
    'https://scholarships.gov.in/public/schemeGuidelines/ApprovedmodifieddraftofTopClassCollege.pdf', 'NSP guideline (current)', [s])
schemes.append(dict(id=s, name='PM YASASVI Top Class Education in College for OBC, EBC and DNT Students', short='PM YASASVI Top Class College',
  ministry='Ministry of Social Justice & Empowerment', kind='central', status='active',
  for_whom='OBC, EBC and DNT students at IITs, IIMs, NITs, AIIMS and other notified institutes', levels='UG and PG at notified institutions',
  benefit='Full tuition (up to ₹2 lakh a year at private institutes), ₹3,000 a month living allowance, ₹5,000 a year for books, and a one-time laptop grant up to ₹45,000', benefit_inr_per_year=200000,
  apply_url='https://scholarships.gov.in', window='NSP; apply every year, including renewals',
  rules=[
    rule('category', 'OBC, EBC or DNT', C('category', 'in', ['obc', 'ebc', 'dnt']), 'yasasvi-tcc', {'location': 'Section 3'}),
    rule('income', 'Family income up to ₹2.5 lakh a year', C('income', 'lte', 250000), 'yasasvi-tcc', q(s, 'income_ceiling_inr')),
    rule('institute', 'Full-time course at a notified institution (IITs, IIMs, IIITs, AIIMS, NITs, NIFTs, NIDs and other listed institutes)', ALL(C('top_institution', 'eq', True), C('level', 'in', ['ug', 'pg'])), 'yasasvi-tcc', q(s, 'course_levels')),
  ],
  checks=[{'text': 'At most two siblings per family.', 'source': 'yasasvi-tcc', 'location': 'Section 3(vi)'}],
  notes=[]))

# ---------------------------------------------------------------- 6 Top class SC
s = 'top-class-education-sc'
doc('tces-2021', 'Top Class Education for SC Students: scheme guidelines 2021-22 to 2025-26',
    'https://socialjustice.gov.in/writereaddata/UploadFile/Top%20Class%20Education%20for%20SC%20Students_2021_22637744907806702333.pdf', '2021-22 to 2025-26', [s])
schemes.append(dict(id=s, name='Central Sector Scholarship Scheme of Top Class Education for SC Students', short='Top Class Education (SC)',
  ministry='Ministry of Social Justice & Empowerment', kind='central', status='active',
  for_whom='SC students at IITs, IIMs, NITs, AIIMS and other notified institutes', levels='UG and PG at notified institutions',
  benefit='Full tuition and fees (up to ₹2 lakh a year at private institutes) plus ₹86,000 in the first year and ₹41,000 a year after that for living costs, books and a computer', benefit_inr_per_year=200000,
  apply_url='https://scholarships.gov.in', window='NSP; institutes verify by 31 October',
  rules=[
    rule('category', 'Scheduled Caste', C('category', 'in', ['sc']), 'tces-2021', {'location': 'Section 2'}),
    rule('income', 'Family income up to ₹8 lakh a year', C('income', 'lte', 800000), 'tces-2021', q(s, 'income_ceiling_inr')),
    rule('institute', 'Full-time course at a notified institution', ALL(C('top_institution', 'eq', True), C('level', 'in', ['ug', 'pg'])), 'tces-2021', q(s, 'course_levels')),
    rule('no-other', 'Not taking any other scholarship', C('other_scholarship', 'eq', False), 'tces-2021', other(s, 1)),
  ],
  checks=[{'text': 'Not more than two siblings in a family.', 'source': 'tces-2021', 'location': 'Section 2(f)'}],
  notes=['Guideline period ends with 2025-26; the scheme is still listed on NSP.']))

# ---------------------------------------------------------------- 7 NMMSS
s = 'nmmss'
doc('nmmss-2022', 'National Means-cum-Merit Scholarship Scheme: guidelines',
    'https://dsel.education.gov.in/sites/default/files/NMMSS_Guidelines_22.pdf', 'Department of School Education guidelines (2022)', [s])
schemes.append(dict(id=s, name='National Means-cum-Merit Scholarship Scheme', short='NMMSS',
  ministry='Ministry of Education (School Education)', kind='central', status='active',
  for_whom='Government-school students who clear the state NMMS exam in Class 8', levels='Class 9–12',
  benefit='₹12,000 a year (₹1,000 a month) from Class 9 to 12', benefit_inr_per_year=12000,
  apply_url='https://scholarships.gov.in', window='NMMS exam in November of Class 8; NSP applications usually June–October',
  rules=[
    rule('income', "Parents' income up to ₹3.5 lakh a year", C('income', 'lte', 350000), 'nmmss-2022', q(s, 'income_ceiling_inr')),
    rule('level', 'In Class 9 to 12', C('level', 'in', ['class_9_10', 'class_11_12']), 'nmmss-2022', {'location': 'Section 1.2'}),
    rule('school', 'Regular student of a government, government-aided or local body school (KVs, JNVs, residential and private schools are excluded)', C('school_type', 'in', ['government', 'govt_aided', 'local_body']), 'nmmss-2022', other(s, 0)),
  ],
  checks=[{'text': 'You must have cleared the NMMS selection exam conducted by your State in Class 8 (it needs 55% in Class 7; 50% for SC/ST).', 'source': 'nmmss-2022', 'location': 'Sections 2.2, 3.1, 3.2'},
          {'text': 'To continue in Class 11 you need at least 60% in Class 10 (55% for SC/ST).', 'source': 'nmmss-2022', 'location': 'Sections 4.3, 4.4'}],
  notes=[]))

# ---------------------------------------------------------------- 8-10 AICTE
for s, did, url, short, name, extra_rules, checks, benefit_note, for_whom in [
  ('aicte-pragati', 'aicte-pragati-g', 'https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2010_G.pdf', 'AICTE Pragati (girls)',
   'AICTE Pragati Scholarship Scheme for Girl Students (Technical Degree & Diploma)',
   [rule('gender', 'Girl student', C('gender', 'in', ['female']), 'aicte-pragati-g', {'location': 'Scheme title and Section 2.0'})],
   [{'text': 'Apply in the first year of the course (or second year through lateral entry).', 'source': 'aicte-pragati-g', 'location': 'Section 2.0(1)'},
    {'text': 'At most two girl children per family.', 'source': 'aicte-pragati-g', 'location': 'Section 2.0(2)'}],
   '', 'Girls in AICTE-approved engineering, pharmacy and other technical courses'),
  ('aicte-saksham', 'aicte-saksham-g', 'https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf', 'AICTE Saksham (disability)',
   'AICTE Saksham Scholarship Scheme for Specially-Abled Students (Technical Degree & Diploma)',
   [rule('disability', 'Disability of 40% or more', C('disability_pct', 'gte', 40), 'aicte-saksham-g', q('aicte-saksham', 'disability'))],
   [{'text': 'Apply in the first year (or second year through lateral entry); gap after the qualifying exam not more than 2 years.', 'source': 'aicte-saksham-g', 'location': 'Sections 2.0(1), 8.1'}],
   '', 'Students with 40%+ disability in AICTE-approved technical courses'),
  ('aicte-swanath', 'aicte-swanath-g', 'https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_3039_G.pdf', 'AICTE Swanath',
   'AICTE Swanath Scholarship Scheme (Technical Degree & Diploma)',
   [rule('situation', 'Orphan, lost a parent to Covid-19, or ward of Armed Forces/CAPF personnel martyred in action', C('flags', 'has_any', ['orphan', 'parent_died_covid', 'ward_martyred_armed_forces']), 'aicte-swanath-g', q('aicte-swanath', 'categories')),
    rule('no-other', 'Not holding another Central/State/AICTE scholarship', C('other_scholarship', 'eq', False), 'aicte-swanath-g', {'location': 'Section 2.0(4)'})],
   [], '', 'Orphans, Covid-bereaved students and wards of martyrs in technical courses'),
]:
    doc(did, f'{name}: guidelines', url, 'NSP-hosted guideline' + (' (2020-21 edition)' if s != 'aicte-swanath' else ' (May 2025)'), [s])
    schemes.append(dict(id=s, name=name, short=short, ministry='AICTE (Ministry of Education)', kind='central', status='active',
      for_whom=for_whom, levels='Technical diploma or degree at an AICTE-approved institution',
      benefit='₹50,000 a year, for up to 4 years (degree) or 3 years (diploma/lateral entry)', benefit_inr_per_year=50000,
      apply_url='https://scholarships.gov.in', window='NSP; 2026-27 last date 31 October 2026',
      rules=extra_rules + [
        rule('income', 'Family income up to ₹8 lakh a year', C('income', 'lte', 800000), did, q(s, 'income_ceiling_inr')),
        rule('course', 'Technical degree or diploma at an AICTE-approved institution', ALL(C('level', 'in', ['diploma', 'ug']), C('course_type', 'in', ['technical'])), did, q(s, 'course_levels')),
      ], checks=checks, notes=[]))

# ---------------------------------------------------------------- 11 PMSS MHA
s = 'pmss-mha-capf-ar-state-police'
doc('pmss-mha-rev', "Prime Minister's Scholarship Scheme (MHA) for wards of CAPF & Assam Rifles: revised guidelines",
    'https://scholarships.gov.in//public/schemeGuidelines/MoHA-(WARB)-RevisedGuidelines_PMSS(MHA).pdf', '2020-21 revision (the 2023-24 PDF on NSP is a scanned image)', [s])
schemes.append(dict(id=s, name="Prime Minister's Scholarship Scheme for wards of CAPF, Assam Rifles and State Police personnel", short='PM Scholarship (CAPF & Assam Rifles)',
  ministry='Ministry of Home Affairs', kind='central', status='active',
  for_whom='Children and widows of CAPF/Assam Rifles personnel (below officer rank) and of State Police killed in terror/Naxal attacks', levels='First professional degree; MBA/MCA',
  benefit='₹3,000 a month for girls, ₹2,500 a month for boys', benefit_inr_per_year=36000,
  apply_url='https://scholarships.gov.in', window='NSP annual cycle',
  rules=[
    rule('ward', 'Ward or widow of CAPF/Assam Rifles personnel, or of State Police martyred in terror/Naxal attacks', C('flags', 'has_any', ['ward_capf_ar', 'ward_police_martyred']), 'pmss-mha-rev', q(s, 'categories')),
    rule('marks', 'At least 60% in the qualifying exam', C('qualifying_marks_pct', 'gte', 60), 'pmss-mha-rev', q(s, 'min_marks')),
    rule('course', 'First professional degree (BE/B.Tech, MBBS, BDS, B.Ed, etc.) or MBA/MCA, in India, regular mode', ALL(PROF_DEGREE, C('studying_abroad', 'eq', False), C('study_mode', 'eq', 'regular')), 'pmss-mha-rev', q(s, 'course_levels')),
    rule('no-other', 'Not availing another scholarship or stipend', C('other_scholarship', 'eq', False), 'pmss-mha-rev', {'location': 'Section 10'}),
  ],
  checks=[{'text': 'Only two children per family.', 'source': 'pmss-mha-rev', 'location': 'Section 4(IV)'}],
  notes=['Amounts are from the 2020-21 revised guidelines; the newer 2023-24 document is a scanned image and could not be read automatically.']))

# ---------------------------------------------------------------- 12 PMSS KSB
s = 'pmss-ksb-ex-servicemen'
doc('ksb-brochure-2024', "Prime Minister's Scholarship Scheme (KSB): information brochure 2024-25",
    'https://swd.hp.gov.in/wp-content/uploads/2024/08/Information-Brochure-2024-25.pdf', '2024-25 brochure (hosted by HP Sainik Welfare Department)', [s])
schemes.append(dict(id=s, name="Prime Minister's Scholarship Scheme for wards and widows of Ex-Servicemen and Ex-Coast Guard personnel", short='PM Scholarship (Ex-Servicemen, KSB)',
  ministry='Ministry of Defence (Kendriya Sainik Board)', kind='central', status='active',
  for_whom='Children and widows of ex-servicemen and ex-Coast Guard personnel', levels='First professional degree; MBA/MCA',
  benefit='₹36,000 a year for girls, ₹30,000 a year for boys', benefit_inr_per_year=36000,
  apply_url='https://online.ksb.gov.in', window='Apply soon after first-year admission (2024-25 student deadline: 30 November)',
  rules=[
    rule('ward', 'Dependent ward or widow of an ex-serviceman or ex-Coast Guard personnel', C('flags', 'has_any', ['ward_ex_servicemen']), 'ksb-brochure-2024', {'location': 'para 3'}),
    rule('marks', 'At least 60% in the minimum educational qualification', C('qualifying_marks_pct', 'gte', 60), 'ksb-brochure-2024', q(s, 'min_marks')),
    rule('course', 'First professional degree (including integrated) or MBA/MCA, in India', ALL(PROF_DEGREE, C('studying_abroad', 'eq', False), C('study_mode', 'eq', 'regular')), 'ksb-brochure-2024', q(s, 'course_levels')),
  ],
  checks=[{'text': 'Only students admitted to the first year in the current academic year; lateral entry is excluded.', 'source': 'ksb-brochure-2024', 'location': 'p.2 para 3(a)'}],
  notes=['Latest official document found is the 2024-25 brochure; confirm 2026-27 dates on online.ksb.gov.in.']))

# ---------------------------------------------------------------- 13 Ishan Uday
s = 'ugc-ishan-uday'
doc('ishan-uday-2324', 'UGC Ishan Uday Special Scholarship Scheme for North Eastern Region: guidelines',
    'https://scholarships.gov.in/public/schemeGuidelines/Guidelines_ISHAN%20UDAY_2324.pdf', '2023-24 guidelines', [s])
schemes.append(dict(id=s, name='Ishan Uday Special Scholarship Scheme for the North Eastern Region', short='UGC Ishan Uday (North-East)',
  ministry='UGC (Ministry of Education)', kind='central', status='active',
  for_whom='Students from the North-Eastern states going to college', levels='First undergraduate degree (regular)',
  benefit='₹8,000 a month for 10 months a year, for the whole UG course', benefit_inr_per_year=80000,
  apply_url='https://scholarships.gov.in', window='NSP, once a year',
  rules=[
    rule('domicile', 'Domicile of a North-Eastern state', C('state', 'in', NE), 'ishan-uday-2324', q(s, 'state_or_region')),
    rule('income', "Parents' income below ₹4.5 lakh a year", C('income', 'lt', 450000), 'ishan-uday-2324', q(s, 'income_ceiling_inr')),
    rule('course', 'First UG degree in regular/full-time mode', ALL(C('level', 'in', ['ug']), C('study_mode', 'eq', 'regular')), 'ishan-uday-2324', q(s, 'course_levels')),
  ],
  checks=[{'text': 'Class 12 must be passed from a school in the North-Eastern region.', 'source': 'ishan-uday-2324', 'location': 'Section 2(X)'},
          {'text': 'Not for students who already hold a degree, or who were admitted through management quota.', 'source': 'ishan-uday-2324', 'location': 'Sections 2(IV), 2(VIII)'}],
  notes=[]))

# ---------------------------------------------------------------- 14 NSPG
s = 'ugc-nspg'
doc('nspg-2324', 'UGC National Scholarship for Post Graduate Studies: guidelines',
    'https://scholarships.gov.in/public/schemeGuidelines/Guidelines_NATIONAL_SCHOLARSHIP_FOR_POSTGRADUATE_STUDIES_UGC_2324.pdf', '2023-24 guidelines', [s])
schemes.append(dict(id=s, name='UGC National Scholarship for Post Graduate Studies (includes the former PG Indira Gandhi Scholarship for Single Girl Child)', short='UGC PG Scholarship (NSPG)',
  ministry='UGC (Ministry of Education)', kind='central', status='active',
  for_whom='Students starting their first PG degree; single girl children get first claim on the 30% women’s slots', levels='First PG degree (regular)',
  benefit='₹15,000 a month for 10 months a year, for 2 years', benefit_inr_per_year=150000,
  apply_url='https://scholarships.gov.in', window='NSP, usually August–November',
  rules=[
    rule('level', 'First year of your first PG degree, regular/full-time', ALL(C('level', 'in', ['pg']), C('study_mode', 'eq', 'regular')), 'nspg-2324', q(s, 'course_levels')),
    rule('age', 'Below 30 years on the date of admission', C('age', 'lt', 30), 'nspg-2324', q(s, 'age_limit')),
  ],
  checks=[{'text': 'Selection is on all-India merit by UG marks. Holders of another scholarship must give it up.', 'source': 'nspg-2324', 'location': 'pp.2-4'}],
  notes=['The PG Indira Gandhi Scholarship for Single Girl Child no longer runs on its own: it was merged into this scheme from 2023-24.']))

# ---------------------------------------------------------------- 15 NOS
s = 'nos-sc'
doc('nos-2526', 'National Overseas Scholarship for SC etc. candidates: guidelines 2025-26',
    'https://nosmsje.gov.in/nosmsje/public/images/Scheme-guidelines-2025-26.pdf', 'Applicable from 2025-26', [s])
schemes.append(dict(id=s, name='National Overseas Scholarship for SC etc. Candidates', short='National Overseas Scholarship (SC)',
  ministry='Ministry of Social Justice & Empowerment', kind='central', status='active',
  for_whom="SC, DNT and landless-labourer families' students going abroad for a Master's or PhD", levels="Master's or PhD abroad",
  benefit='Tuition at actuals, about US$15,400 a year maintenance (£9,900 in the UK), contingency, visa fee and airfare', benefit_inr_per_year=1500000,
  apply_url='https://nosmsje.gov.in', window='Two rounds a year (around Feb–Mar and Sep–Oct), 40 days each',
  rules=[
    rule('category', 'SC or Denotified/Nomadic/Semi-Nomadic tribe (some awards also for landless agricultural labourer families)', C('category', 'in', ['sc', 'dnt']), 'nos-2526', {'location': 'Section 2(b)-(c)'}),
    rule('income', 'Family income up to ₹8 lakh a year', C('income', 'lte', 800000), 'nos-2526', q(s, 'income_ceiling_inr')),
    rule('abroad', "Master's or PhD at a university abroad", ALL(C('level', 'in', ['pg', 'phd']), C('studying_abroad', 'eq', True)), 'nos-2526', q(s, 'course_levels')),
    rule('marks', 'At least 60% in the qualifying exam', C('qualifying_marks_pct', 'gte', 60), 'nos-2526', q(s, 'min_marks')),
    rule('age', 'Not more than 35 years on 1 April of the selection year', C('age', 'lte', 35), 'nos-2526', q(s, 'age_limit')),
  ],
  checks=[{'text': 'The university must be in the QS World top 500.', 'source': 'nos-2526', 'location': 'Sections 2(i), 9(a)'},
          {'text': 'At most two children of the same parents.', 'source': 'nos-2526', 'location': 'Section 7'}],
  notes=[]))

# ---------------------------------------------------------------- 16 DEPwD (3 parts)
doc('depwd-2024', 'Scholarships for Students with Disabilities (Pre-Matric, Post-Matric, Top Class): revised guidelines',
    'https://scholarships.gov.in/public/schemeGuidelines/DEPDGuidelines_1.pdf', 'Revised by OM dated 25 September 2024', ['depwd-pre-matric', 'depwd-post-matric', 'depwd-top-class'])
dis = rule('disability', 'Benchmark disability of 40% or more', C('disability_pct', 'gte', 40), 'depwd-2024', q('depwd-scholarships-swd', 'disability'))
dno = rule('no-other', 'Not taking another scholarship or stipend', C('other_scholarship', 'eq', False), 'depwd-2024', {'location': 'Section 2(vi), p.4'})
for sid, short, name, lv, inc, benefit, val, extra in [
  ('depwd-pre-matric', 'Pre-Matric Scholarship (disability)', 'Pre-Matric Scholarship for Students with Disabilities', ['class_9_10'], 250000,
   '₹800/₹500 a month (hostel/day scholar), disability allowance up to ₹4,000 and ₹1,000 book grant a year', 9600, []),
  ('depwd-post-matric', 'Post-Matric Scholarship (disability)', 'Post-Matric Scholarship for Students with Disabilities', POST_MATRIC, 250000,
   'Tuition up to ₹1.4 lakh a year, ₹1,200/₹650 a month, disability allowance up to ₹4,000 and ₹1,500 book grant a year', 140000, []),
  ('depwd-top-class', 'Top Class Education (disability)', 'Top Class Education Scholarship for Students with Disabilities', ['ug', 'pg'], 800000,
   'Tuition up to ₹1.9 lakh a year plus living, book and equipment allowances', 190000,
   [rule('institute', 'Degree or diploma at a notified Institute of Excellence (full-time)', ALL(C('top_institution', 'eq', True), C('study_mode', 'eq', 'regular')), 'depwd-2024', {'location': 'Section 6.1, p.8'})]),
]:
    schemes.append(dict(id=sid, name=name, short=short, ministry='Department of Empowerment of Persons with Disabilities', kind='central', status='active',
      for_whom='Students with 40%+ disability', levels={'depwd-pre-matric': 'Class 9–10', 'depwd-post-matric': 'Class 11 up to PhD', 'depwd-top-class': 'UG/PG at notified institutes'}[sid],
      benefit=benefit, benefit_inr_per_year=val, apply_url='https://scholarships.gov.in', window='NSP annual cycle',
      rules=[dis, rule('income', f"Parents' income up to ₹{inc/100000:g} lakh a year", C('income', 'lte', inc), 'depwd-2024', {'location': 'Section 3 table, p.5'}),
             rule('level', 'Studying at this level', C('level', 'in', lv), 'depwd-2024', {'location': 'Sections 4.1, 5(a), 6.1'})] + extra + [dno],
      checks=[{'text': 'At most two children with disabilities of the same parents (twins exempt).', 'source': 'depwd-2024', 'location': 'Section 2(iv), p.4'}],
      notes=['50% of slots in each part are reserved for girls.']))

# ---------------------------------------------------------------- 17 PMS-ST
s = 'pms-st'
doc('pms-st-nsp', 'Post Matric Scholarship for ST students: scheme document on NSP',
    'https://scholarships.gov.in/public/schemeGuidelines/EDUPostMatricScholarshipPMSforSTstudents.pdf', 'NSP-hosted document (older allowance rates)', [s])
schemes.append(dict(id=s, name='Post Matric Scholarship for Scheduled Tribe Students', short='Post-Matric Scholarship (ST)',
  ministry='Ministry of Tribal Affairs', kind='central', status='active',
  for_whom='ST students after Class 10', levels='Class 11–12, ITI/diploma, UG, PG, PhD',
  benefit='Compulsory fees plus a monthly maintenance allowance that depends on course group and hostel', benefit_inr_per_year=14400,
  apply_url='https://scholarships.gov.in', window='State-specific; often registration April–September',
  rules=[
    rule('category', 'Scheduled Tribe', C('category', 'in', ['st']), 'pms-st-nsp', q(s, 'categories')),
    rule('income', "Parents' income up to ₹2.5 lakh a year", C('income', 'lte', 250000), 'pms-st-nsp', q(s, 'income_ceiling_inr')),
    rule('level', 'Studying after Class 10', C('level', 'in', POST_MATRIC), 'pms-st-nsp', {'location': 'Eligibility'}),
    rule('no-other', 'Not holding another scholarship or stipend', C('other_scholarship', 'eq', False), 'pms-st-nsp', {'location': 'Eligibility'}),
  ], checks=[], notes=['The allowance rates in the NSP document are old; your state portal will show current amounts.']))

# ---------------------------------------------------------------- 18 INSPIRE-SHE (paused)
s = 'inspire-she'
doc('inspire-she-2024', 'INSPIRE Scholarship for Higher Education (SHE): call for applications 2024',
    'https://ubse.uk.gov.in/files/Call_for_Application_Inspire(SHE)_2024_NOTIFICATION_1.pdf', '2024 call (copy hosted by Uttarakhand Board)', [s])
schemes.append(dict(id=s, name='INSPIRE Scholarship for Higher Education (SHE)', short='INSPIRE-SHE',
  ministry='Department of Science & Technology', kind='central', status='paused',
  status_note='DST said in July 2026 that the scheme is being redesigned; no call for 2025 had been issued.',
  for_whom='Top science students doing B.Sc, BS or integrated M.Sc in natural sciences', levels='UG / integrated MSc in natural and basic sciences',
  benefit='₹80,000 a year (₹5,000 a month plus a ₹20,000 mentorship grant) under the 2024 call', benefit_inr_per_year=80000,
  apply_url='https://online-inspire.gov.in', window='Not currently open',
  rules=[
    rule('course', 'B.Sc, BS or integrated M.Sc in natural or basic sciences', ALL(C('level', 'in', ['ug']), C('course_type', 'in', ['general'])), 'inspire-she-2024', {'location': 'Eligibility'}),
    rule('marks', 'Top 1% of your Class 12 board (or JEE/NEET top 10,000, or KVPY/NTSE/Olympiad routes)', C('class12_percentile', 'gte', 99), 'inspire-she-2024', q(s, 'min_marks')),
    rule('age', 'Aged 17 to 22', ALL(C('age', 'gte', 17), C('age', 'lte', 22)), 'inspire-she-2024', q(s, 'age_limit')),
  ], checks=[{'text': 'Must have passed Class 12 in the current year.', 'source': 'inspire-she-2024', 'location': 'Eligibility'}],
  notes=['Do not apply yet: wait for DST to announce the redesigned scheme.']))

# ---------------------------------------------------------------- 19 TN Pudhumai Penn
s = 'tn-pudhumai-penn'
doc('tn-pp-2023', 'Pudhumai Penn scheme: Government of Tamil Nadu press release (July 2023)',
    'https://kygcms.tn.gov.in/cms_migrated/document/press_release/pr290723_e_1513.pdf', 'Press release, July 2023', [s])
schemes.append(dict(id=s, name='Pudhumai Penn (Moovalur Ramamirtham Ammaiyar Higher Education Assurance Scheme), Tamil Nadu', short='Pudhumai Penn (Tamil Nadu)',
  ministry='Government of Tamil Nadu', kind='state', status='active',
  for_whom='Girls who studied Class 6–12 in Tamil Nadu government schools and go on to college', levels='UG, diploma, ITI',
  benefit='₹1,000 a month by direct transfer until the course is completed', benefit_inr_per_year=12000,
  apply_url='https://pudhumaipenn.tn.gov.in', window='Register through your college’s nodal officer',
  rules=[
    rule('state', 'Studying in Tamil Nadu', C('state', 'in', ['TN']), 'tn-pp-2023', {'location': 'Press release'}),
    rule('gender', 'Girl student', C('gender', 'in', ['female', 'transgender']), 'tn-pp-2023', q(s, 'state_or_region')),
    rule('school', 'Studied Class 6 to 12 in Tamil Nadu government schools', C('flags', 'has_any', ['tn_govt_school_6_12']), 'tn-pp-2023', q(s, 'state_or_region')),
    rule('course', 'In a UG degree, diploma or ITI course', C('level', 'in', ['diploma', 'ug']), 'tn-pp-2023', {'location': 'Press release'}),
  ], checks=[], notes=['News reports say it was extended to government-aided schools (Dec 2024) and to transgender students (June 2025); confirm with your college.']))

# ---------------------------------------------------------------- 20-21 discontinued
doc('ls-au1662', 'Lok Sabha Unstarred Question 1662 (10 Dec 2025): minority scholarships',
    'https://eparlib.sansad.in/bitstream/123456789/3019088/1/AU1662_E60DrS.pdf', '10 December 2025', ['moma-minority-scholarships'], kind='status')
doc('ls-au2590', 'Lok Sabha Unstarred Question 2590 (11 Dec 2024): Begum Hazrat Mahal scholarship',
    'https://eparlib.sansad.in/bitstream/123456789/2985510/1/AU2590_ol1Z4J.pdf', '11 December 2024', ['begum-hazrat-mahal'], kind='status')
schemes.append(dict(id='moma-minority-scholarships', name='Pre-Matric, Post-Matric and Merit-cum-Means Scholarships for Minorities', short='Minority scholarships (MoMA)',
  ministry='Ministry of Minority Affairs', kind='central', status='discontinued',
  status_note='Not approved for implementation beyond 2021-22 (Lok Sabha answer, December 2025).',
  for_whom='Minority-community students', levels='Class 9 to PG', benefit='—', benefit_inr_per_year=0, apply_url='', window='Not open',
  rules=[], checks=[], notes=['Minority students can still qualify for other schemes here based on income, category, course or disability.']))
schemes.append(dict(id='begum-hazrat-mahal', name='Begum Hazrat Mahal National Scholarship', short='Begum Hazrat Mahal Scholarship',
  ministry='Ministry of Minority Affairs (Maulana Azad Education Foundation, closed 2024)', kind='central', status='discontinued',
  status_note='Merged into the minority Pre/Post-Matric schemes from 2022-23 (Lok Sabha answer, December 2024); the foundation that ran it closed in February 2024.',
  for_whom='Minority girls in Class 9–12', levels='Class 9–12', benefit='—', benefit_inr_per_year=0, apply_url='', window='Not open',
  rules=[], checks=[], notes=[]))

out = {'generated_from': 'Research of official scheme documents, October 2026. Always confirm on the official portal before applying.',
       'documents': docs, 'schemes': schemes}
json.dump(out, open(ROOT / 'data/catalog.json', 'w'), ensure_ascii=False, indent=1)
print(len(schemes), 'schemes,', len(docs), 'documents')
# sanity: every rule source exists
ids = {d['id'] for d in docs}
for s in schemes:
    for r in s['rules']: assert r['source'] in ids, (s['id'], r['source'])
    for c in s['checks']: assert c['source'] in ids
print('ok')
