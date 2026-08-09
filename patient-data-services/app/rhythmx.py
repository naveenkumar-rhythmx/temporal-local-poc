"""RhythmX AI panel — rules-based clinical decision support over AIREADY data.

This is an *educational* engine for a local prototype running on synthetic
patients. It is deterministic and offline: no LLM keys, no external calls, and
every suggestion carries the data points that triggered it so the logic stays
auditable. In production, this layer is an LLM/insight service reading the same
AIREADY collections.

NOT FOR CLINICAL USE.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app import repository

DISCLAIMER = (
    "Educational prototype running on synthetic data. Rules-based suggestions only — "
    "not medical advice and not for clinical use. All decisions require a licensed clinician."
)

# LOINC-style codes used by the synthetic seed data.
LAB_A1C = "4548-4"
LAB_LDL = "13457-7"
LAB_CREATININE = "2160-0"
LAB_EGFR = "48642-3"
LAB_POTASSIUM = "2823-3"
LAB_TSH = "3016-3"

ANTIHYPERTENSIVE_CLASSES = {
    "ace-inhibitor",
    "arb",
    "calcium-channel-blocker",
    "thiazide-diuretic",
    "beta-blocker",
    "loop-diuretic",
    "mra",
}

# Allergy substance -> drug classes that should not be given.
ALLERGY_CLASS_CONFLICTS = {
    "penicillin": {"penicillin-antibiotic"},
    "sulfa": {"thiazide-diuretic"},
    "nsaid": {"nsaid"},
    "aspirin": {"antiplatelet", "nsaid"},
    "statin": {"statin"},
    "ace inhibitor": {"ace-inhibitor"},
}


def _today() -> dt.date:
    return dt.date.today()


def _parse_date(value: Any) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _days_since(value: Any) -> int | None:
    parsed = _parse_date(value)
    return (_today() - parsed).days if parsed else None


def _age_years(dob: Any) -> int | None:
    born = _parse_date(dob)
    if not born:
        return None
    today = _today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _latest_lab(latest_labs: list[dict], code: str) -> dict | None:
    for lab in latest_labs:
        if lab.get("code") == code:
            return lab
    return None


def _lab_value(latest_labs: list[dict], code: str) -> float | None:
    lab = _latest_lab(latest_labs, code)
    if lab is None or lab.get("value_num") is None:
        return None
    return float(lab["value_num"])


def _lab_evidence(latest_labs: list[dict], code: str) -> str | None:
    lab = _latest_lab(latest_labs, code)
    if lab is None:
        return None
    unit = lab.get("unit") or ""
    return f"{lab['display']}: {lab.get('value_num')} {unit}".strip() + f" ({lab.get('collected_at')})"


def _active(rows: list[dict], key: str = "status") -> list[dict]:
    return [r for r in rows if (r.get(key) or "active") == "active"]


def _has_condition(conditions: list[dict], prefixes: tuple[str, ...]) -> dict | None:
    for cond in conditions:
        code = (cond.get("code") or "").upper()
        if code.startswith(prefixes) and (cond.get("clinical_status") or "active") == "active":
            return cond
    return None


def _med_classes(medications: list[dict]) -> set[str]:
    return {
        (m.get("drug_class") or "").lower()
        for m in _active(medications)
        if m.get("drug_class")
    }


def _rec(
    rec_id: str,
    category: str,
    severity: str,
    title: str,
    detail: str,
    evidence: list[str | None],
    options: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": rec_id,
        "category": category,
        "severity": severity,
        "title": title,
        "detail": detail,
        "suggested_options": options or [],
        "evidence": [e for e in evidence if e],
    }


def build_history_summary(
    patient: dict,
    conditions: list[dict],
    medications: list[dict],
    allergies: list[dict],
    latest_labs: list[dict],
    vitals: list[dict],
    notes: list[dict],
) -> str:
    """Short narrative a clinician can read in a few seconds."""
    age = _age_years(patient.get("date_of_birth"))
    gender = (patient.get("gender") or "patient").lower()
    name = f"{patient.get('first_name')} {patient.get('last_name')}"

    parts: list[str] = []
    header = f"{name} is a {age}-year-old {gender}" if age else f"{name} is a {gender}"

    active_conditions = [c for c in conditions if (c.get("clinical_status") or "active") == "active"]
    if active_conditions:
        problems = ", ".join(
            f"{c['display']}"
            + (f" (since {str(c['onset_date'])[:4]})" if c.get("onset_date") else "")
            for c in active_conditions[:6]
        )
        parts.append(f"{header} with an active problem list of {problems}.")
    else:
        parts.append(f"{header} with no active problems recorded.")

    active_meds = _active(medications)
    if active_meds:
        parts.append(
            f"Currently on {len(active_meds)} active medication(s): "
            + ", ".join(m["name"] for m in active_meds[:6])
            + "."
        )

    if allergies:
        parts.append(
            "Allergies: "
            + ", ".join(
                f"{a['substance']}" + (f" ({a['reaction']})" if a.get("reaction") else "")
                for a in allergies
            )
            + "."
        )
    else:
        parts.append("No known allergies recorded.")

    abnormal = [
        f"{lab['display']} {lab.get('value_num')} {lab.get('unit') or ''}".strip()
        for lab in latest_labs
        if lab.get("abnormal_flag") in ("H", "L")
    ]
    if abnormal:
        parts.append("Recent out-of-range results: " + ", ".join(abnormal[:6]) + ".")

    if vitals:
        v = vitals[0]
        bits = []
        if v.get("systolic") and v.get("diastolic"):
            bits.append(f"BP {v['systolic']}/{v['diastolic']}")
        if v.get("heart_rate"):
            bits.append(f"HR {v['heart_rate']}")
        if v.get("bmi"):
            bits.append(f"BMI {v['bmi']}")
        if bits:
            parts.append(f"Latest vitals ({v.get('recorded_at')}): " + ", ".join(bits) + ".")

    if notes and notes[0].get("summary"):
        parts.append(f"Last note ({notes[0].get('note_date')}): {notes[0]['summary']}")

    return " ".join(parts)


def build_recommendations(
    patient: dict,
    conditions: list[dict],
    medications: list[dict],
    allergies: list[dict],
    latest_labs: list[dict],
    vitals: list[dict],
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []

    age = _age_years(patient.get("date_of_birth")) or 0
    classes = _med_classes(medications)
    active_meds = _active(medications)
    allergy_names = {(a.get("substance") or "").lower() for a in allergies}

    diabetes = _has_condition(conditions, ("E11", "E10"))
    hypertension = _has_condition(conditions, ("I10", "I11", "I12", "I13"))
    ckd = _has_condition(conditions, ("N18",))
    asthma_copd = _has_condition(conditions, ("J44", "J45"))
    hypothyroid = _has_condition(conditions, ("E03",))
    ascvd = _has_condition(conditions, ("I25", "I21", "I63"))

    a1c = _lab_value(latest_labs, LAB_A1C)
    ldl = _lab_value(latest_labs, LAB_LDL)
    egfr = _lab_value(latest_labs, LAB_EGFR)
    creatinine = _lab_value(latest_labs, LAB_CREATININE)
    potassium = _lab_value(latest_labs, LAB_POTASSIUM)
    tsh = _lab_value(latest_labs, LAB_TSH)

    latest_vitals = vitals[0] if vitals else {}
    systolic = latest_vitals.get("systolic")
    diastolic = latest_vitals.get("diastolic")

    def blocked_by_allergy(target_classes: set[str]) -> str | None:
        for substance in allergy_names:
            conflicts = ALLERGY_CLASS_CONFLICTS.get(substance, set())
            overlap = conflicts & target_classes
            if overlap:
                return f"Documented {substance} allergy conflicts with {', '.join(sorted(overlap))}"
        return None

    # --- Diabetes control -------------------------------------------------
    if diabetes and a1c is not None and a1c >= 8.0:
        options = []
        if "sglt2-inhibitor" not in classes:
            options.append("SGLT2 inhibitor (cardiorenal benefit)")
        if "glp1-agonist" not in classes:
            options.append("GLP-1 receptor agonist (weight benefit)")
        if "biguanide" not in classes:
            options.append("Metformin, if not contraindicated")
        recs.append(
            _rec(
                "dm-intensify",
                "Medication",
                "high",
                "Diabetes above target — consider intensifying therapy",
                f"HbA1c is {a1c}% with {len(classes & {'biguanide', 'sulfonylurea', 'sglt2-inhibitor', 'glp1-agonist', 'insulin'})} "
                "glucose-lowering class(es) on board. Review adherence first, then consider add-on therapy.",
                [
                    _lab_evidence(latest_labs, LAB_A1C),
                    f"Active problem: {diabetes['display']}",
                    "Current classes: " + (", ".join(sorted(classes)) or "none"),
                ],
                options,
            )
        )
    elif diabetes and a1c is not None and a1c < 7.0:
        recs.append(
            _rec(
                "dm-at-goal",
                "Monitoring",
                "low",
                "Diabetes appears at goal — continue current regimen",
                f"HbA1c {a1c}% is within a typical target range. Reassess in 3–6 months.",
                [_lab_evidence(latest_labs, LAB_A1C), f"Active problem: {diabetes['display']}"],
            )
        )

    # --- Statin / lipids --------------------------------------------------
    if (diabetes or ascvd) and age >= 40 and "statin" not in classes:
        blocked = blocked_by_allergy({"statin"})
        recs.append(
            _rec(
                "lipid-statin",
                "Medication",
                "moderate",
                "No statin on the active medication list",
                "Guideline-style risk reduction usually includes a statin for diabetes or established ASCVD in this age group."
                + (f" Caution: {blocked}." if blocked else ""),
                [
                    f"Age {age}",
                    f"Active problem: {(diabetes or ascvd)['display']}",
                    _lab_evidence(latest_labs, LAB_LDL),
                ],
                [] if blocked else ["Moderate-intensity statin", "Repeat lipid panel in 8–12 weeks"],
            )
        )
    elif ldl is not None and ldl >= 100 and "statin" in classes:
        recs.append(
            _rec(
                "lipid-intensify",
                "Medication",
                "moderate",
                "LDL above target on current statin",
                f"LDL is {ldl} mg/dL despite statin therapy. Review adherence and consider intensification.",
                [_lab_evidence(latest_labs, LAB_LDL), "Statin already active"],
                ["Increase statin intensity", "Consider ezetimibe add-on"],
            )
        )

    # --- Blood pressure ---------------------------------------------------
    if systolic and diastolic and (systolic >= 140 or diastolic >= 90):
        bp_classes = classes & ANTIHYPERTENSIVE_CLASSES
        options: list[str] = []
        if diabetes and not (classes & {"ace-inhibitor", "arb"}):
            options.append("ACE inhibitor or ARB (preferred with diabetes)")
        if len(bp_classes) < 2:
            options.append("Add a second antihypertensive class")
        options.append("Confirm with repeat/home BP readings")
        recs.append(
            _rec(
                "htn-uncontrolled",
                "Medication",
                "high" if systolic >= 160 or diastolic >= 100 else "moderate",
                "Blood pressure above target",
                f"Latest BP {systolic}/{diastolic} mmHg with {len(bp_classes)} antihypertensive class(es) active.",
                [
                    f"BP {systolic}/{diastolic} on {latest_vitals.get('recorded_at')}",
                    f"Active problem: {hypertension['display']}" if hypertension else None,
                    "Antihypertensive classes: " + (", ".join(sorted(bp_classes)) or "none"),
                ],
                options,
            )
        )

    # --- Renal safety -----------------------------------------------------
    renal_concern = (egfr is not None and egfr < 45) or (
        creatinine is not None and creatinine > 1.3
    )
    if renal_concern:
        detail_bits = []
        if "biguanide" in classes:
            detail_bits.append("metformin dose review")
        if "nsaid" in classes:
            detail_bits.append("stop/avoid NSAIDs")
        recs.append(
            _rec(
                "renal-review",
                "Safety",
                "high" if (egfr is not None and egfr < 30) else "moderate",
                "Reduced renal function — review renally-cleared medications",
                "Renal markers are outside range. Recommended review: "
                + (", ".join(detail_bits) if detail_bits else "recheck renal panel and dose-adjust as needed")
                + ".",
                [
                    _lab_evidence(latest_labs, LAB_EGFR),
                    _lab_evidence(latest_labs, LAB_CREATININE),
                    f"Active problem: {ckd['display']}" if ckd else None,
                ],
                ["Recheck renal function panel", "Adjust doses for eGFR"],
            )
        )

    if potassium is not None and potassium > 5.2 and (classes & {"ace-inhibitor", "arb", "mra"}):
        recs.append(
            _rec(
                "hyperkalemia-watch",
                "Safety",
                "high",
                "Elevated potassium with RAAS-acting therapy",
                f"Potassium is {potassium} mmol/L while on {', '.join(sorted(classes & {'ace-inhibitor', 'arb', 'mra'}))}. Repeat and review dosing.",
                [_lab_evidence(latest_labs, LAB_POTASSIUM)],
                ["Repeat potassium", "Review ACEi/ARB/MRA dose"],
            )
        )

    # --- Allergy conflicts on the current list ----------------------------
    for med in active_meds:
        med_class = (med.get("drug_class") or "").lower()
        for substance in allergy_names:
            if med_class and med_class in ALLERGY_CLASS_CONFLICTS.get(substance, set()):
                recs.append(
                    _rec(
                        f"allergy-conflict-{med['name'].lower().replace(' ', '-')}",
                        "Safety",
                        "high",
                        f"Possible allergy conflict: {med['name']}",
                        f"{med['name']} ({med_class}) appears to conflict with a documented {substance} allergy. Verify before continuing.",
                        [
                            f"Active medication: {med['name']} {med.get('dose') or ''}".strip(),
                            f"Allergy: {substance}",
                        ],
                        ["Verify allergy history", "Consider an alternative class"],
                    )
                )

    # --- Interaction / duplication ---------------------------------------
    if "anticoagulant" in classes and (classes & {"nsaid", "antiplatelet"}):
        recs.append(
            _rec(
                "bleeding-risk",
                "Safety",
                "high",
                "Bleeding risk from overlapping therapy",
                "An anticoagulant is combined with an NSAID/antiplatelet. Confirm the combination is intended and time-limited.",
                ["Active classes: " + ", ".join(sorted(classes & {"anticoagulant", "nsaid", "antiplatelet"}))],
                ["Reassess indication", "Consider gastroprotection"],
            )
        )

    seen_classes: dict[str, str] = {}
    for med in active_meds:
        cls = (med.get("drug_class") or "").lower()
        if not cls:
            continue
        if cls in seen_classes:
            recs.append(
                _rec(
                    f"duplicate-{cls}",
                    "Safety",
                    "moderate",
                    f"Duplicate therapy in class: {cls}",
                    f"{seen_classes[cls]} and {med['name']} are both {cls}. Confirm this is intentional.",
                    [f"Active: {seen_classes[cls]}", f"Active: {med['name']}"],
                    ["Reconcile medication list"],
                )
            )
        else:
            seen_classes[cls] = med["name"]

    if len(active_meds) >= 8:
        recs.append(
            _rec(
                "polypharmacy",
                "Monitoring",
                "moderate",
                "Polypharmacy — consider a medication review",
                f"{len(active_meds)} active medications recorded. A structured reconciliation may reduce risk.",
                [f"Active medication count: {len(active_meds)}"],
                ["Deprescribing review"],
            )
        )

    # --- Respiratory / thyroid -------------------------------------------
    if asthma_copd and "saba" in classes and "inhaled-corticosteroid" not in classes:
        recs.append(
            _rec(
                "resp-controller",
                "Medication",
                "moderate",
                "Reliever inhaler without a controller",
                "A short-acting bronchodilator is active with no inhaled corticosteroid on the list. Consider controller therapy.",
                [f"Active problem: {asthma_copd['display']}", "Active class: saba"],
                ["Inhaled corticosteroid-containing controller", "Review inhaler technique"],
            )
        )

    if hypothyroid and tsh is not None and tsh > 4.5:
        recs.append(
            _rec(
                "thyroid-dose",
                "Medication",
                "moderate",
                "TSH above range — review levothyroxine dose",
                f"TSH is {tsh} mIU/L, suggesting under-replacement.",
                [_lab_evidence(latest_labs, LAB_TSH), f"Active problem: {hypothyroid['display']}"],
                ["Review levothyroxine dose", "Repeat TSH in 6–8 weeks"],
            )
        )

    # --- Care gaps --------------------------------------------------------
    if diabetes:
        a1c_age = _days_since((_latest_lab(latest_labs, LAB_A1C) or {}).get("collected_at"))
        if a1c_age is None or a1c_age > 120:
            recs.append(
                _rec(
                    "gap-a1c",
                    "Care gap",
                    "moderate",
                    "HbA1c is due",
                    "No HbA1c in the last ~4 months for a patient with diabetes."
                    if a1c_age is not None
                    else "No HbA1c on record for a patient with diabetes.",
                    [f"Days since last HbA1c: {a1c_age}" if a1c_age is not None else "No HbA1c result"],
                    ["Order HbA1c"],
                )
            )

    ldl_age = _days_since((_latest_lab(latest_labs, LAB_LDL) or {}).get("collected_at"))
    if (diabetes or ascvd) and (ldl_age is None or ldl_age > 365):
        recs.append(
            _rec(
                "gap-lipids",
                "Care gap",
                "low",
                "Lipid panel is due",
                "No lipid panel within the last year for a patient with cardiometabolic risk.",
                [f"Days since last LDL: {ldl_age}" if ldl_age is not None else "No LDL result"],
                ["Order lipid panel"],
            )
        )

    if not vitals:
        recs.append(
            _rec(
                "gap-vitals",
                "Care gap",
                "low",
                "No vitals recorded",
                "No vital signs are available for this patient.",
                ["air_vitals is empty"],
                ["Record vitals at next visit"],
            )
        )

    severity_rank = {"high": 0, "moderate": 1, "low": 2}
    recs.sort(key=lambda r: severity_rank.get(r["severity"], 3))
    return recs


def analyze(patient_id: str) -> dict[str, Any] | None:
    """Assemble the RhythmX AI panel for one patient from AIREADY data."""
    patient = repository.get_patient(patient_id)
    if patient is None:
        return None

    conditions = repository.get_conditions(patient_id)
    medications = repository.get_medications(patient_id)
    allergies = repository.get_allergies(patient_id)
    latest_labs = repository.get_latest_labs(patient_id)
    vitals = repository.get_vitals(patient_id)
    notes = repository.get_notes(patient_id)

    recommendations = build_recommendations(
        patient, conditions, medications, allergies, latest_labs, vitals
    )
    history_summary = build_history_summary(
        patient, conditions, medications, allergies, latest_labs, vitals, notes
    )

    high = sum(1 for r in recommendations if r["severity"] == "high")
    moderate = sum(1 for r in recommendations if r["severity"] == "moderate")
    if high:
        risk_level = "high"
    elif moderate:
        risk_level = "moderate"
    else:
        risk_level = "low"

    return {
        "patient_id": patient_id,
        "display_name": f"{patient.get('first_name')} {patient.get('last_name')}",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "engine": "rules-v1 (deterministic, offline)",
        "risk_level": risk_level,
        "counts": {
            "high": high,
            "moderate": moderate,
            "low": sum(1 for r in recommendations if r["severity"] == "low"),
        },
        "history_summary": history_summary,
        "problem_highlights": [
            c["display"] for c in conditions if (c.get("clinical_status") or "active") == "active"
        ],
        "recommendations": recommendations,
        "data_sources": [
            "air_conditions",
            "air_medications",
            "air_allergies",
            "air_labs",
            "air_vitals",
            "air_clinical_notes",
        ],
        "disclaimer": DISCLAIMER,
    }
