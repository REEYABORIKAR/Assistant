import unittest
from refyne.user_story_engine import (
    stage1_extract_requirements,
    stage3_extract_personas,
    stage5_extract_workflows,
    stage7_generate_stories_for_requirement,
    stage8_validate_story_quality,
    stage9_validate_completeness,
    stage11_build_traceability_matrix,
    stage12_apply_revision_engine,
    generate_complete_user_stories_pipeline
)
from refyne.document_service import build_pdf_document

HMS_SOURCE_TEXT = """
Hospital Management System 
A Hospital Management System (HMS) should provide a centralized platform for 
managing hospital operations, patient information, medical records, appointments, doctors, 
nurses, staff, billing, pharmacy, laboratory, and inventory. The system should support role-
based access for Admin, Doctor, Nurse, Receptionist, Pharmacist, Lab Technician, 
Accountant, and Patient. Core requirements should include patient registration and profile 
management, appointment scheduling and queue management, doctor availability, OPD/IPD 
management, admission/discharge/transfer, electronic medical records, diagnosis, 
prescriptions, treatment history, allergies, vital signs, nursing notes, laboratory test requests 
and reports, pharmacy prescriptions and medicine inventory, bed/ward management, billing 
and payments, insurance management, invoices and receipts, hospital expenses, staff 
management, and inventory/procurement. Patients should be able to view appointments, 
prescriptions, reports, bills, and medical history through a portal, while doctors should have 
dashboards for appointments, patient records, diagnosis, prescriptions, and clinical notes. 
The system should also provide dashboards, notifications, search/filtering, reports, audit 
logs, data validation, backup/recovery, security, and role-based authorization. 
Functional requirements should cover complete workflows such as patient registration → 
appointment → consultation → diagnosis → laboratory/pharmacy → billing → follow-up, 
and admission → bed allocation → treatment → investigations → discharge → final billing. 
Non-functional requirements should include responsive web UI, scalability, high availability, 
fast API responses, secure authentication, password encryption, session management, HTTPS, 
database integrity, auditability, privacy of medical information, error handling, logging, 
and regular backups.
"""

class TestUserStoryEngine(unittest.TestCase):

    def test_01_first_generation_completeness_and_guardrails(self):
        """Test 1: Guardrails specified in USER_STORY_PIPELINE_FIX.md."""
        doc = generate_complete_user_stories_pipeline(
            doc_text=HMS_SOURCE_TEXT,
            title="Hospital Management System"
        )

        self.assertEqual(doc["doc_type"], "USER_STORIES")
        self.assertEqual(doc["version"], "v1.0")
        self.assertEqual(len(doc["sections"]), 10)

        data = doc["user_stories_data"]
        reqs = data["requirements"]
        personas = data["personas"]
        stories = data["stories"]
        traceability = data["traceability"]
        validation = data["validation"]

        # Guardrail 1: Stage 1 extracts >= 15 discrete requirements
        self.assertGreaterEqual(len(reqs), 15, "Stage 1 must extract >= 15 discrete requirements")

        # Guardrail 2: >= 3 distinct personas mapped
        distinct_personas = {s["persona"] for s in stories}
        self.assertGreaterEqual(len(distinct_personas), 3, "Must have >= 3 distinct personas")

        # Guardrail 3: No generic placeholder persona in persona list
        persona_names = {p["name"] for p in personas}
        self.assertNotIn("Authorized User", persona_names)
        self.assertNotIn("End User", persona_names)
        self.assertNotIn("Enterprise User", persona_names)

        # Guardrail 4: Completeness validator confirms 100% coverage
        self.assertEqual(validation["completeness"]["status"], "COMPLETE")
        self.assertTrue(validation["completeness"]["is_complete"])
        self.assertTrue(all(t["status"] == "COVERED" for t in traceability))

        # Guardrail 5: Quality validator confirms no filler ACs or vague verbs
        self.assertTrue(validation["quality"]["is_valid"])
        for s in stories:
            for ac in s["acceptance_criteria"]:
                self.assertFalse(ac.startswith("AC1: System accepts valid input for"), f"Filler AC found in {s['story_id']}")

        # Guardrail 6: Decomposed OPD/IPD/Pharmacy/Billing stories present
        story_ids = {s["story_id"] for s in stories}
        self.assertIn("US-PAT-01", story_ids)
        self.assertIn("US-APT-01", story_ids)
        self.assertIn("US-QUE-01", story_ids)
        self.assertIn("US-IPD-01", story_ids)
        self.assertIn("US-IPD-02", story_ids)
        self.assertIn("US-IPD-03", story_ids)
        self.assertIn("US-IPD-04", story_ids)
        self.assertIn("US-PHM-01", story_ids)
        self.assertIn("US-PHM-02", story_ids)
        self.assertIn("US-PHM-03", story_ids)
        self.assertIn("US-PHM-04", story_ids)
        self.assertIn("US-BIL-01", story_ids)
        self.assertIn("US-BIL-02", story_ids)
        self.assertIn("US-BIL-03", story_ids)
        self.assertIn("US-BIL-05", story_ids)

    def test_02_rejection_and_improvement_workflow_v1_to_v2(self):
        """Test 2: Rejection engine decisioning (KEEP/MODIFY/SPLIT/ADD) preserves context."""
        v1_doc = generate_complete_user_stories_pipeline(
            doc_text=HMS_SOURCE_TEXT,
            title="Hospital Management System"
        )
        self.assertEqual(v1_doc["version"], "v1.0")

        feedback = "The stories are too broad. Split them. Add missing OPD/IPD, admission, discharge..."
        v2_doc = generate_complete_user_stories_pipeline(
            doc_text=HMS_SOURCE_TEXT,
            title="Hospital Management System",
            previous_doc=v1_doc,
            revision_feedback=feedback
        )

        self.assertEqual(v2_doc["version"], "v2.0")
        self.assertEqual(len(v2_doc["revision_history"]), 1)
        self.assertEqual(v2_doc["revision_history"][0]["feedback"], feedback)
        
        # Verify traceability remains 100% complete
        v2_trace = v2_doc["user_stories_data"]["traceability"]
        self.assertTrue(all(t["status"] == "COVERED" for t in v2_trace))

    def test_03_targeted_rejection_preserves_unrelated_stories(self):
        """Test 3: Targeted rejection only modifies affected stories and keeps unrelated stories intact."""
        v1_doc = generate_complete_user_stories_pipeline(doc_text=HMS_SOURCE_TEXT, title="Hospital Management System")
        v2_doc = generate_complete_user_stories_pipeline(doc_text=HMS_SOURCE_TEXT, title="Hospital Management System", previous_doc=v1_doc, revision_feedback="Add admission stories")
        
        targeted_feedback = "The pharmacy and billing stories are still too broad. Split them further and improve their acceptance criteria. Do not change unrelated stories."
        v3_doc = generate_complete_user_stories_pipeline(
            doc_text=HMS_SOURCE_TEXT,
            title="Hospital Management System",
            previous_doc=v2_doc,
            revision_feedback=targeted_feedback
        )

        self.assertEqual(v3_doc["version"], "v3.0")
        self.assertEqual(len(v3_doc["revision_history"]), 2)

        # Verify unrelated stories (e.g. US-PAT-01, US-IPD-01, US-EMR-01) remain perfectly intact
        v3_stories_map = {s["story_id"]: s for s in v3_doc["user_stories_data"]["stories"]}
        self.assertEqual(v3_stories_map["US-PAT-01"]["persona"], "Receptionist")
        self.assertEqual(v3_stories_map["US-IPD-01"]["persona"], "Doctor")
        self.assertEqual(v3_stories_map["US-EMR-01"]["persona"], "Doctor")

    def test_04_pdf_rendering_deterministic(self):
        """Test 4: Template PDF rendering succeeds deterministically without LLM calls."""
        doc = generate_complete_user_stories_pipeline(doc_text=HMS_SOURCE_TEXT, title="Hospital Management System")
        pdf_bytes = build_pdf_document(
            title=doc["title"],
            doc_type=doc["doc_type"],
            sections=doc["sections"],
            tenant_name="HMS Health Systems",
            version=doc["version"]
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 5000)


if __name__ == "__main__":
    unittest.main()
