# test_notes_complex.py
# Synthetic clinical notes for robust de-identification testing (US healthcare).
# Each NOTE_* is a single string with rich PHI variations:
# - Names, initials & nicknames; relatives
# - Addresses (street, city, state, ZIP/ZIP+4), facilities
# - Dates in multiple formats, times, relative dates
# - Phone/Fax (various formats), Email, URL (with query params), IP
# - SSN, MRN (different site patterns), Encounter/Account/Claim IDs, Health plan IDs
# - License numbers, Vehicle VIN, Device serials/implants
# - Biometric references, Photo filenames
# - Ages (incl. >= 90), labs/vitals units to test numeric whitelist
# - OCR-ish noise, tables, bullet lists, EHR boilerplate

NOTE_PROGRESS_T2DM_HTN = """
Mercy River Medical Center — Outpatient Progress Note
Patient Name: Johnathan M. Carter (aka "Johnny")
DOB: 03/12/1958   MRN: 54782934   Encounter ID: ENC-2025-09-05-233
Address: 2456 Oakwood Drive, Springfield, IL 62704-3311
Phone: (217) 555-0187   Email: john.m.carter@example.com
Primary Care Provider: Linda Thompson, MD  |  NPI: 1336155559  |  License: IL D1234567
Date of Service: 09/05/2025 14:05

Chief Complaint:
Follow-up for type 2 diabetes mellitus and hypertension.

HPI:
J.M. Carter reports adherence to metformin 1000 mg BID and lisinopril 20 mg daily.
Occasional morning dizziness; increased thirst x 2 weeks. No CP/SOB/vision changes.
Home logs: fasting 145–170 mg/dL; post-prandial occasionally >200 mg/dL.

Vitals:
BP 152/92 mmHg, HR 78 bpm, Temp 98.6 F, BMI 29.4 kg/m^2

Labs (08/15/2025):
A1c 8.2%, LDL 124 mg/dL, Cr 1.1 mg/dL

Assessment/Plan:
1) T2DM, suboptimal control (A1c 8.2). Continue metformin; consider SGLT2 add-on next visit.
2) HTN, uncontrolled (152/92). Increase lisinopril to 40 mg daily; daily home BP log.
3) Hyperlipidemia: continue atorvastatin 40 mg nightly.
Orders: BMP in 4 weeks to monitor kidney function.
Patient education: DASH diet; 150 min/wk brisk walking.
Follow-up: 3 months (12/05/2025).

Other identifiers for test:
SSN: 123-45-6789 | Health Plan: BCBS-IL ID HZN-IL-12345678 | Account #: ACC-9876543
URL: https://portal.mercyriver.org/patient?mrn=54782934&appt=2025-12-05
IP: 192.168.1.77
Full-face photo on file: face-photo-2020-03-13.jpg
Biometric: fingerprint-template-id FPT-998877
Vehicle to transport: VIN 1HGCM82633A004352
Device: CGM SN-MD9A7Z-55621
"""

NOTE_DISCHARGE_MI_CABG = """
CardioHealth University Hospital
Discharge Summary | Admit: 02/11/2025 08:22 | Discharge: 02/18/2025 16:05
Patient: Smith, Robert J.  (R.J. Smith)   Age: 67 yrs   DOB 1958-06-14
MRN 000912345  |  FIN/Account: 2025-0009-ACCT  |  Medicare ID: 1EG4-TE5-MK72
Address: 88 Westmoreland Ave., Columbus, OH 43215
Phone 614.555.4400   Email: rjsmith@samplemail.com   SSN 912-34-5678

Principal Diagnosis: NSTEMI -> triple-vessel disease.
Procedure: CABG x3 on 02/13/2025 by Dr. Amelia J. Lee (License OH L-9988776).

Hospital Course:
Uncomplicated post-op. Temporary pacing wires removed POD#2. Small left pleural effusion resolved.

Discharge Meds:
- Aspirin 81 mg PO daily
- Clopidogrel 75 mg PO daily
- Metoprolol succinate 50 mg PO daily
- Atorvastatin 80 mg PO nightly

Follow-up:
- CT surgery clinic 02/25/2025 09:00 at CardioHealth University Hospital (Suite 410).
- PCP Dr. Michael J. Bolton in 2 weeks.

Safety/IDs for test:
Encounter ID: ENC-CHUH-2025-0211-001
Health Plan Beneficiary #: HICN-CH-5566-7788
URL: http://discharge.cardiohealth.edu/visit?id=ENC-CHUH-2025-0211-001&mrn=000912345
IP: 10.0.25.12  |  Photo: selfie-RJ-2025-02-14.jpg
"""

NOTE_AVS_T2DM_EDUCATION = """
After Visit Summary — Endocrine Clinic
Patient: Nguyen, Alice (A.N.)   DOB: 01/02/1989   MRN: MRN-AZ-44-22119
Visit Date: 7/2/2025 3:15 PM  Provider: Priya Desai, MD (License AZ 45321)
Contact: Mobile +1 480-555-0033, alt (480)555-7788; Email: alice.nguyen+endocrine@gmail.com
Address: 2100 E University Dr., Tempe, AZ 85281-2044

Instructions:
— Check fasting glucose daily; record in app.
— Start GLP-1 RA 0.25 mg once weekly; reassess in 4 weeks.
— Schedule retinal exam by 08/15/2025.

Education links:
https://endocrinecenter.org/learn/t2dm?patient=MRN-AZ-44-22119&city=Tempe
Family contact (husband): Daniel Nguyen (dnguyen@workmail.biz | 480.555.1111)

Other IDs:
Insurance Plan: AETNA-AZ-992233 | Employer Account: EMP-ACC-0003312
Portal IP: 172.16.8.45 | Photo on file: face-ALICE-2019.jpg
Device: Insulin pen lot SN: PEN-SN-8891AZ
"""

NOTE_ED_TRIAGE_STROKE = """
Emergency Department Triage Note
Facility: St. Gabriel Regional Medical Center (Level II Trauma)
Patient Initials: J.S. (legal: Joseph Samuel)
Age: 92-year-old male  |  DOB 02/29/1933 (reported)
Arrival: 08/01/2025 11:42 AM via EMS  |  Room: ED-07B
Address per ID: 14 Willow Bend Ct, Richmond, VA 23220
Next of kin: daughter Mary Samuel, (804) 555-0909

Chief Complaint:
Right-sided weakness, last known well ~09:30 AM.

Brief Exam:
BP 188/102, HR 96, RR 18, SpO2 96% RA, Glucose 168 mg/dL
Cincinnati stroke scale positive.

IDs for test:
SSN: 222-45-6789
MRN ED TEMP: ED-MRN-009912  |  Encounter: ED-ENC-2025-0801-1142
URL in EMS narrative: http://ems.city.gov/report?enc=ED-ENC-2025-0801-1142
IP from EMS tablet: 100.64.12.9
Photo attached: face-photo-stroke-in-ambulance.jpg
"""

NOTE_RADIOLOGY_CXR = """
Radiology Report — Chest X-Ray PA/LAT
Institution: Westview Imaging Clinic (WIC)
Patient: Hernandez, Miguel (M. Hernandez)  DOB 1990/11/05  MRN 44556677
Study Date: 2025-06-01 08:05  Accession: ACC-IMG-993377

Technique: PA and lateral chest radiographs.
Findings: Cardiomediastinal silhouette normal. No focal consolidation, no pleural effusion.
Impression: No acute cardiopulmonary disease.

Administrative:
Ordering Provider: Dr. Olivia Rhodes (License CA A1223344)
Contact: (310) 555-2020  |  Fax: 310.555.2021  |  Email: orhodes@westviewimaging.com
URL (PACS): https://pacs.wic.example/series?acc=ACC-IMG-993377&mrn=44556677
IP: 172.20.12.2  |  Photo ref: face-miguel-2018.jpg
"""

NOTE_REFERRAL_ENDOCRINE = """
Referral Letter
From: Greenfield Family Medicine, 100 Main St, Boston, MA 02110
To: Endocrinology, Boston General Hospital, 1 Patriot Way, Boston, MA 02114
Patient: Ms. Kayla O'Neil, DOB 12/05/1976, MRN BGH-0099-7766
Phone: (617) 555-2444  Email: kayla.oneil@sample.org
Reason: Poorly controlled T1DM with recurrent hypoglycemia.

Pertinent details:
— CGM alarms overnight; basal likely too high.
— A1c 9.1% (05/2025). LDL 154 mg/dL.

IDs:
Insurer: HARVARD-PILGRIM-PLN-778899
Account: ACC-PL-00921  |  Claim: CLM-2025-7788-55
Provider License (referring): MA LIC # MA-554433A
URL: http://referrals.greenfieldfm.com/new?pid=BGH-0099-7766
"""

NOTE_OPERATIVE_NOTE = """
Operative Note
Facility: Silver Oaks Surgery Center
Patient: Patel, Rina  DOB 07-07-1984  MRN: SOSC-221144  Encounter: OR-2025-08-20-001
Pre/Post Dx: Symptomatic cholelithiasis
Procedure: Laparoscopic cholecystectomy (08/20/2025) by Dr. Ethan Wu, MD (License CA C778899)

Findings:
Gallbladder distended; no CBD injury. EBL 50 mL.

Implants/Devices:
Hem-o-lok clips; Device serial logged: DEV-SN-CHOL-7XZ1-99231

Contacts:
Spouse: Arjun Patel — mobile 415.555.3232
Discharge to: 455 Maple Ln., San Mateo, CA 94403

Other IDs:
Account 7788332200 | Health Plan: KAISER-CA-PLN-4455
URL PACS stills: https://so-sc.org/pacs/img?id=OR-2025-08-20-001
"""

NOTE_HOME_HEALTH_NURSING = """
Home Health Nursing Visit
Agency: Sunrise Home Health LLC
Patient: Eleanor P. Greene (E.P. Greene), 90-year-old, DOB 09/09/1935 (reported)
Service Date: 2025/09/01

Address Verified: 17 Bayberry Rd., Charleston, SC 29407
Primary Contact: grandson Alex Greene, 843-555-8821, email: alex.greene@work.biz

Assessment:
— BP 138/86. HR 72. Capillary glucose 132 mg/dL before lunch.
— Ambulates with cane; mild edema ankles.

Safety/Devices:
— Insulin syringes present; Lot SN: SYR-LOT-CAROLINA-0091
— Front door keypad code (will be changed): 0919

Agency IDs:
Client #: HH-CL-229911 | Account: ACC-HH-442210
Visit Photos: face-greene-porch.jpg
URL case note: http://sunrisehh.net/case?cl=HH-CL-229911
"""

NOTE_PORTAL_MESSAGE = """
Patient Portal Secure Message
From: michael.b.roberts@gmail.com (Michael B. Roberts)
To: Diabetes Care Team — Northbrook Medical Group
Subject: Meter readings & refill

Hello,
My meter (DexPro) uploads to https://readings.dexpro.example/u?uid=MBR-556677&mrn=NB-0099
Glucose last 7 days avg 162 mg/dL. Please refill metformin 1000 mg tabs.
My pharmacy: 411 Lakeview Rd., Northbrook, IL 60062. Phone (847) 555-6611.
Thanks,
Mike
Account NB-ACCT-00991  |  IP when sending: 203.0.113.9
"""

NOTE_OCR_NOISE = """
Scanned Intake Form (OCR)
PATlENT NAME: "SARAH 0'CONN0R"   (note: OCR swaps O/0, I/l)
D0B: 0l/0l/1980   MRN: l2lOOO99l  (handwritten)
Address: 55 “Elm” Street Apt #4B, New Haven, CT 06511-2217
Phone: 203.555.0909  Alt: +1-203-555-0910
SSN (self-reported): 987-65-4321
Emergency Contact: Father, Patrick O'Connor, 203 555 2211
Device listed: "Pump SN-MD00l-CT-77Z"
Health Plan: CTCARE-GOLD-7782
URL scrawl: http://patient.ctcare.org/join?mrn=l2lOOO99l
IP captured by kiosk: 198.51.100.45
Photo pasted: face-scan-sarah-2017.jpg
"""

# Optional: group them for iteration in tests
ALL_NOTES = {
    "progress_t2dm_htn": NOTE_PROGRESS_T2DM_HTN,
    "discharge_mi_cabg": NOTE_DISCHARGE_MI_CABG,
    "avs_t2dm_education": NOTE_AVS_T2DM_EDUCATION,
    "ed_triage_stroke": NOTE_ED_TRIAGE_STROKE,
    "radiology_cxr": NOTE_RADIOLOGY_CXR,
    "referral_endocrine": NOTE_REFERRAL_ENDOCRINE,
    "operative_note": NOTE_OPERATIVE_NOTE,
    "home_health_nursing": NOTE_HOME_HEALTH_NURSING,
    "portal_message": NOTE_PORTAL_MESSAGE,
    "ocr_noise": NOTE_OCR_NOISE,
}