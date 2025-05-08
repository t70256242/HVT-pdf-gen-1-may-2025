import os
from datetime import datetime, timedelta
import pycountry
import streamlit as st
# from internship_template_edit import fill_pdf_template
# from internship_docx_edit import replace_docx_placeholders
from nda_edit import nda_edit
# from contract_edit import replace_docx_placeholders
from docx_pdf_converter import main_converter
from edit_proposal_cover import EditTextFile
from merge_pdf import Merger
import tempfile
from firebase_conf import auth, rt_db, bucket, firestore_db

LOAD_LOCALLY = True


def fetch_and_organize_templates(firestore_db, base_temp_dir=None):
    # Base temp dir
    if not base_temp_dir:
        base_temp_dir = tempfile.mkdtemp()

    # Main collection reference
    collection_ref = firestore_db.collection("hvt_generator")

    # Iterate through each document type (e.g., Proposal, NDA, etc.)
    doc_types = collection_ref.stream()
    for doc in doc_types:
        doc_type = doc.id  # e.g., "Proposal", "NDA", etc.
        templates_ref = collection_ref.document(doc_type).collection("templates")
        templates = templates_ref.stream()

        for template in templates:
            data = template.to_dict()
            file_url = data["download_url"]
            file_name = data["name"]

            if doc_type == "Proposal" and "proposal_section_type" in data:
                # Subdir structure for proposals
                subfolder = data["proposal_section_type"].lower() + "_templates"
                target_dir = os.path.join(base_temp_dir, "proposal", subfolder)
            else:
                target_dir = os.path.join(base_temp_dir, doc_type.lower().replace(" ", "_"))

            os.makedirs(target_dir, exist_ok=True)

            file_path = os.path.join(target_dir, file_name)

            try:
                # Download the file
                response = requests.get(file_url)
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                else:
                    print(f"Failed to download {file_name} (HTTP {response.status_code})")
            except Exception as e:
                print(f"Error downloading {file_name}: {str(e)}")

    return base_temp_dir


# def handle_internship_offer():
#     st.title("📄 Internship Offer Form")
#
#     # Initialize session state for multi-page form
#     if 'form_step' not in st.session_state:
#         st.session_state.form_step = 1
#         st.session_state.offer_data = {}
#
#     if st.session_state.form_step == 1:
#         # Step 1: Collect information
#         with st.form("internship_offer_form"):
#             name = st.text_input("Candidate Name")
#             position = st.selectbox(
#                 "Internship Position",
#                 ["UI UX Designer", "AI Automations Developer", "Sales and Marketing"],
#                 index=0
#             )
#             start_date = st.date_input("Start Date")
#             # end_date = st.date_input("End Date")
#             stipend_input = st.text_input("Stipend (write out digits, no commas or dot)")
#             if stipend_input.strip().isdigit():
#                 # stipend = "{:,.2f}".format(int(stipend_input))
#                 stipend = "{:,}".format(int(stipend_input))
#             else:
#                 stipend = "0.00"
#             hours = st.text_input("Work Hours per week")
#             duration = st.number_input("Internship Duration (In Months)", min_value=1, max_value=24, step=1)
#             first_paycheck = st.date_input("First Paycheck Date")
#
#             if st.form_submit_button("Generate Offer"):
#                 st.session_state.offer_data = {
#                     "name": name,
#                     "position": position,
#                     "start_date": start_date,
#                     # "end_date": end_date,
#                     "stipend": stipend,
#                     "hours": hours,
#                     "duration": duration,
#                     "first_paycheck": first_paycheck
#                 }
#                 st.session_state.form_step = 2
#                 st.experimental_rerun() if LOAD_LOCALLY else st.rerun()
#
#     elif st.session_state.form_step == 2:
#         # Step 2: Preview and download
#         st.success("Offer generated successfully!")
#         st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'form_step', 1))
#
#         # replacements_docx = {
#         #     "_Date_": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
#         #     "_Name_": st.session_state.offer_data["name"],
#         #     "_Position_": st.session_state.offer_data["position"],
#         #     "_Stipend_": str(st.session_state.offer_data["stipend"]),
#         #     "_Hrs_": str(st.session_state.offer_data["hours"]),
#         #     "_Internship_Duration_": str(st.session_state.offer_data["duration"]),
#         #     "_First_Pay_Cheque_Date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y")
#         # }
#         context = {
#             "date": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
#             "name": st.session_state.offer_data["name"],
#             "position": st.session_state.offer_data["position"],
#             "stipend": str(st.session_state.offer_data["stipend"]),
#             "hours": str(st.session_state.offer_data["hours"]),
#             "internship_duration": str(st.session_state.offer_data["duration"]),
#             "first_paycheck_date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y"),
#         }
#
#         # nda_edit("internship_template.docx", "wowo.docx", context)
#
#         # Generate temporary files
#         pdf_output = "temp_offer.pdf"
#         docx_output = "temp_offer.docx"
#
#
#         # replace_docx_placeholders("Internship Offer Letter Template.docx", docx_output, replacements_docx)
#         nda_edit("internship_template.docx", docx_output, context)
#         main_converter(docx_output, pdf_output)
#
#         # Preview section
#         st.subheader("Preview")
#         st.write(f"**Candidate Name:** {st.session_state.offer_data['name']}")
#         st.write(f"**Position:** {st.session_state.offer_data['position']}")
#         st.write(f"**Duration:** {st.session_state.offer_data['duration']} months")
#         st.write(f"**Stipend:** ₹{st.session_state.offer_data['stipend']}/month")
#
#         # PDF preview (requires pdfplumber)
#         try:
#             import pdfplumber
#             with pdfplumber.open(pdf_output) as pdf:
#                 preview_page = pdf.pages[0]
#                 st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
#         except:
#             st.warning("Couldn't generate PDF preview. PDF file not available now.")
#
#         # Download buttons
#         st.subheader("Download Documents")
#         col1, col2 = st.columns(2)
#         # Check if files exist before trying to open them
#         pdf_exists = os.path.exists(pdf_output) if pdf_output else False
#         docx_exists = os.path.exists(docx_output) if docx_output else False
#
#         with col1:
#             if pdf_exists:
#                 with open(pdf_output, "rb") as f_pdf:
#                     st.download_button(
#                         "⬇️ Download PDF",
#                         f_pdf,
#                         file_name=
#                         f"{st.session_state.offer_data['name']}_"
#                         f"{st.session_state.offer_data['position']}_Offer_Letter.pdf",
#                         mime="application/pdf"
#                     )
#             else:
#                 st.warning("PDF file not available for download")
#
#         with col2:
#             if docx_exists:
#                 with open(docx_output, "rb") as f_docx:
#                     st.download_button(
#                         "⬇️ Download DOCX",
#                         f_docx,
#                         file_name=
#                         f"{st.session_state.offer_data['name']}_"
#                         f"{st.session_state.offer_data['position']}_Offer_Letter.docx",
#                         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
#                     )
#             else:
#                 st.warning("DOCX file not available for download")
#
#         # Clean up temp files
#         try:
#             os.remove(pdf_output)
#             os.remove(docx_output)
#         except:
#             pass

from firebase_admin import storage
import tempfile


# def handle_internship_offer():
#     st.title("📄 Internship Offer Form")
#
#     # Initialize session state for multi-page form
#     if 'form_step' not in st.session_state:
#         st.session_state.form_step = 1
#         st.session_state.offer_data = {}
#
#     if st.session_state.form_step == 1:
#         # Step 1: Collect information (unchanged)
#         with st.form("internship_offer_form"):
#             name = st.text_input("Candidate Name")
#             position = st.selectbox(
#                 "Internship Position",
#                 ["UI UX Designer", "AI Automations Developer", "Sales and Marketing"],
#                 index=0
#             )
#             start_date = st.date_input("Start Date")
#             stipend_input = st.text_input("Stipend (write out digits, no commas or dot)")
#             if stipend_input.strip().isdigit():
#                 stipend = "{:,}".format(int(stipend_input))
#             else:
#                 stipend = "0.00"
#             hours = st.text_input("Work Hours per week")
#             duration = st.number_input("Internship Duration (In Months)", min_value=1, max_value=24, step=1)
#             first_paycheck = st.date_input("First Paycheck Date")
#
#             if st.form_submit_button("Generate Offer"):
#                 st.session_state.offer_data = {
#                     "name": name,
#                     "position": position,
#                     "start_date": start_date,
#                     "stipend": stipend,
#                     "hours": hours,
#                     "duration": duration,
#                     "first_paycheck": first_paycheck
#                 }
#                 st.session_state.form_step = 2
#                 st.experimental_rerun() if LOAD_LOCALLY else st.rerun()
#
#     elif st.session_state.form_step == 2:
#         # Step 2: Preview and download
#         st.success("Offer generated successfully!")
#         st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'form_step', 1))
#
#         context = {
#             "date": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
#             "name": st.session_state.offer_data["name"],
#             "position": st.session_state.offer_data["position"],
#             "stipend": str(st.session_state.offer_data["stipend"]),
#             "hours": str(st.session_state.offer_data["hours"]),
#             "internship_duration": str(st.session_state.offer_data["duration"]),
#             "first_paycheck_date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y"),
#         }
#
#         # Get template from Firestore
#         doc_type = "Internship Offer"
#         try:
#             template_ref = firestore_db.collection("hvt_generator").document(doc_type)
#             templates = template_ref.collection("templates").order_by("order_number").limit(1).get()
#
#             if not templates:
#                 st.error("No templates found in the database for Internship Offer")
#                 return
#
#             # Get the first template (order_number = 1)
#             template_doc = templates[0]
#             template_data = template_doc.to_dict()
#
#             # Check if storage_path exists (this is the key change)
#             if 'storage_path' not in template_data:
#                 st.error("Template storage path not found in the database")
#                 return
#             if template_data.get(
#                     'file_type') != 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
#                 st.error("Template is not a Word document (.docx)")
#                 return
#             if template_data.get('visibility') != 'Public':
#                 st.error("This template is not publicly available")
#                 return
#
#             # Download the template file from Firebase Storage
#             bucket = storage.bucket()
#             blob = bucket.blob(template_data['storage_path'])
#
#             # Create a temporary file for the template
#             with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_template:
#                 blob.download_to_filename(temp_template.name)
#                 template_path = temp_template.name
#
#         except Exception as e:
#             st.error(f"Error fetching template: {str(e)}")
#             return
#
#         # Generate temporary files
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf, \
#                 tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_docx:
#
#             pdf_output = temp_pdf.name
#             docx_output = temp_docx.name
#
#             # Use the downloaded template
#             nda_edit(template_path, docx_output, context)
#             main_converter(docx_output, pdf_output)
#
#             # Preview section
#             st.subheader("Preview")
#             st.write(f"**Candidate Name:** {st.session_state.offer_data['name']}")
#             st.write(f"**Position:** {st.session_state.offer_data['position']}")
#             st.write(f"**Duration:** {st.session_state.offer_data['duration']} months")
#             st.write(f"**Stipend:** ₹{st.session_state.offer_data['stipend']}/month")
#
#             # PDF preview (requires pdfplumber)
#             try:
#                 import pdfplumber
#                 with pdfplumber.open(pdf_output) as pdf:
#                     preview_page = pdf.pages[0]
#                     st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
#             except:
#                 st.warning("Couldn't generate PDF preview. PDF file not available now.")
#
#             # Download buttons
#             st.subheader("Download Documents")
#             col1, col2 = st.columns(2)
#
#             with col1:
#                 with open(pdf_output, "rb") as f_pdf:
#                     st.download_button(
#                         "⬇️ Download PDF",
#                         f_pdf,
#                         file_name=f"{st.session_state.offer_data['name']}_{st.session_state.offer_data['position']}_Offer_Letter.pdf",
#                         mime="application/pdf"
#                     )
#
#             with col2:
#                 with open(docx_output, "rb") as f_docx:
#                     st.download_button(
#                         "⬇️ Download DOCX",
#                         f_docx,
#                         file_name=f"{st.session_state.offer_data['name']}_{st.session_state.offer_data['position']}_Offer_Letter.docx",
#                         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
#                     )
#
#         # Clean up temp files
#         try:
#             import os
#             os.unlink(template_path)
#             os.unlink(pdf_output)
#             os.unlink(docx_output)
#         except:
#             pass

def handle_internship_offer():
    st.title("📄 Internship Offer Form")

    # Initialize session state for multi-page form
    if 'form_step' not in st.session_state:
        st.session_state.form_step = 1
        st.session_state.offer_data = {}

    # Step 1: Collect information
    if st.session_state.form_step == 1:
        with st.form("internship_offer_form"):
            name = st.text_input("Candidate Name", placeholder="John Doe")
            position = st.selectbox(
                "Internship Position",
                ["UI UX Designer", "AI Automations Developer", "Sales and Marketing"],
                index=0
            )
            start_date = st.date_input("Start Date", value=datetime.now().date())
            stipend_input = st.text_input("Stipend (write out digits, no commas or dot)", placeholder="15000")

            # Validate stipend input
            if stipend_input.strip().isdigit():
                stipend = "{:,}".format(int(stipend_input))
            else:
                stipend = "0.00"
                st.warning("Please enter a valid stipend amount (digits only)")

            hours = st.text_input("Work Hours per week", placeholder="40")
            duration = st.number_input("Internship Duration (In Months)", min_value=1, max_value=24, step=1, value=3)
            first_paycheck = st.date_input("First Paycheck Date", value=datetime.now().date() + timedelta(days=30))

            if st.form_submit_button("Generate Offer"):
                # Validate required fields
                if not name.strip():
                    st.error("Please enter candidate name")
                    st.stop()

                st.session_state.offer_data = {
                    "name": name.strip(),
                    "position": position,
                    "start_date": start_date,
                    "stipend": stipend,
                    "hours": hours,
                    "duration": duration,
                    "first_paycheck": first_paycheck
                }
                st.session_state.form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # Step 2: Preview and download
    elif st.session_state.form_step == 2:
        st.success("Offer generated successfully!")
        st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'form_step', 1))

        # Prepare context data for template
        context = {
            "date": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
            "name": st.session_state.offer_data["name"],
            "position": st.session_state.offer_data["position"],
            "stipend": str(st.session_state.offer_data["stipend"]),
            "hours": str(st.session_state.offer_data["hours"]),
            "internship_duration": str(st.session_state.offer_data["duration"]),
            "first_paycheck_date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y"),
        }

        try:
            # Create temp directory
            temp_dir = os.path.join(tempfile.gettempdir(), "hvt_offer")
            os.makedirs(temp_dir, exist_ok=True)

            # Get template from Firestore
            doc_type = "Internship Offer"
            template_ref = firestore_db.collection("hvt_generator").document(doc_type)
            templates = template_ref.collection("templates").order_by("order_number").limit(1).get()

            if not templates:
                st.error("No templates found in the database for Internship Offer")
                return

            template_doc = templates[0]
            template_data = template_doc.to_dict()

            # Validate template data
            if 'storage_path' not in template_data:
                st.error("Template storage path not found in the database")
                return
            if template_data.get(
                    'file_type') != 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                st.error("Template is not a Word document (.docx)")
                return
            if template_data.get('visibility') != 'Public':
                st.error("This template is not publicly available")
                return

            # Download template from Firebase Storage
            bucket = storage.bucket()
            blob = bucket.blob(template_data['storage_path'])

            # Use absolute path for template
            template_path = os.path.join(temp_dir, "template.docx")
            blob.download_to_filename(template_path)

            # Verify download
            if not os.path.exists(template_path):
                st.error("Failed to download template file")
                return

            # Generate output files with absolute paths
            docx_output = os.path.join(temp_dir, "offer.docx")
            pdf_output = os.path.join(temp_dir, "offer.pdf")

            # Process documents
            nda_edit(template_path, docx_output, context)
            main_converter(docx_output, pdf_output)

            # Preview section
            st.subheader("Preview")
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Candidate Name:** {st.session_state.offer_data['name']}")
                st.write(f"**Position:** {st.session_state.offer_data['position']}")
                st.write(f"**Start Date:** {st.session_state.offer_data['start_date'].strftime('%B %d, %Y')}")

            with col2:
                st.write(f"**Duration:** {st.session_state.offer_data['duration']} months")
                st.write(f"**Stipend:** ₹{st.session_state.offer_data['stipend']}/month")
                st.write(f"**First Paycheck:** {st.session_state.offer_data['first_paycheck'].strftime('%B %d, %Y')}")

            # PDF preview
            try:
                import pdfplumber
                with pdfplumber.open(pdf_output) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(
                        preview_page.to_image(resolution=150).original,
                        caption="Offer Letter Preview",
                        use_column_width=True
                    )
            except Exception as e:
                st.warning(f"Couldn't generate PDF preview: {str(e)}")

            # Download buttons
            st.subheader("Download Documents")
            col1, col2 = st.columns(2)

            # Generate download file names
            file_prefix = f"{st.session_state.offer_data['name'].replace(' ', '_')}_{st.session_state.offer_data['position'].replace(' ', '_')}"

            with col1:
                if os.path.exists(pdf_output):
                    with open(pdf_output, "rb") as f_pdf:
                        st.download_button(
                            "⬇️ Download PDF",
                            f_pdf,
                            file_name=f"{file_prefix}_Offer_Letter.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.warning("PDF file not available")

            with col2:
                if os.path.exists(docx_output):
                    with open(docx_output, "rb") as f_docx:
                        st.download_button(
                            "⬇️ Download DOCX",
                            f_docx,
                            file_name=f"{file_prefix}_Offer_Letter.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                else:
                    st.warning("DOCX file not available")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please try again or contact support if the problem persists.")

        finally:
            # Clean up temporary files
            try:
                files_to_remove = [template_path, docx_output, pdf_output]
                for file_path in files_to_remove:
                    if file_path and os.path.exists(file_path):
                        os.unlink(file_path)
            except Exception as e:
                st.warning(f"Could not clean up temporary files: {str(e)}")


def handle_nda():
    st.title("📄 NDA Form")

    # Initialize session state for multi-page form
    if 'nda_form_step' not in st.session_state:
        st.session_state.nda_form_step = 1
        st.session_state.nda_data = {}

    if st.session_state.nda_form_step == 1:
        # Step 1: Collect information
        with st.form("nda_form"):
            date = st.date_input("Agreement Date")
            client_company_name = st.text_input("Client Company Name")
            client_company_address = st.text_area("Client Company Address")

            if st.form_submit_button("Generate NDA"):
                st.session_state.nda_data = {
                    "date": date.strftime("%B %d, %Y"),
                    "client_company_name": client_company_name,
                    "client_company_address": client_company_address
                }
                st.session_state.nda_form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.nda_form_step == 2:
        # Step 2: Preview and download
        st.success("NDA generated successfully!")
        st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'nda_form_step', 1))

        # Generate documents
        replacements_docx = {
            "date": st.session_state.nda_data["date"],
            "client_company_name": st.session_state.nda_data["client_company_name"],
            "client_company_address": st.session_state.nda_data["client_company_address"]
        }

        # Get template from Firestore
        doc_type = "NDA"  # Changed to match your collection name
        try:
            template_ref = firestore_db.collection("hvt_generator").document(doc_type)
            templates = template_ref.collection("templates").order_by("order_number").limit(1).get()

            if not templates:
                st.error("No templates found in the database for NDA")
                return

            # Get the first template (order_number = 1)
            template_doc = templates[0]
            template_data = template_doc.to_dict()

            # Visibility check
            if template_data.get('visibility', 'Private') != 'Public':
                st.error("This NDA template is not currently available")
                return

            # File type check
            if template_data.get(
                    'file_type') != 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                st.error("Template is not a valid Word document (.docx)")
                return

            # Check if storage_path exists
            if 'storage_path' not in template_data:
                st.error("Template storage path not found in the database")
                return

            # Download the template file from Firebase Storage
            bucket = storage.bucket()
            blob = bucket.blob(template_data['storage_path'])

            # Create a temporary file for the template
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_template:
                blob.download_to_filename(temp_template.name)
                template_path = temp_template.name

        except Exception as e:
            st.error(f"Error fetching template: {str(e)}")
            return

        # Generate temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf, \
                tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_docx:

            pdf_output = temp_pdf.name
            docx_output = temp_docx.name

            # Use the downloaded template
            nda_edit(template_path, docx_output, replacements_docx)
            main_converter(docx_output, pdf_output)

            # Preview section
            st.subheader("Preview")
            st.write(f"**Agreement Date:** {st.session_state.nda_data['date']}")
            st.write(f"**Client Company Name:** {st.session_state.nda_data['client_company_name']}")
            st.write(f"**Client Address:** {st.session_state.nda_data['client_company_address']}")

            # PDF preview (requires pdfplumber)
            try:
                import pdfplumber
                with pdfplumber.open(pdf_output) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
            except:
                st.warning("Couldn't generate PDF preview for now.")

            # Download buttons
            st.subheader("Download Documents")
            col1, col2 = st.columns(2)

            with col1:
                with open(pdf_output, "rb") as f_pdf:
                    st.download_button(
                        "⬇️ Download PDF",
                        f_pdf,
                        file_name=f"{st.session_state.nda_data['client_company_name']}_NDA.pdf",
                        mime="application/pdf"
                    )

            with col2:
                with open(docx_output, "rb") as f_docx:
                    st.download_button(
                        "⬇️ Download DOCX",
                        f_docx,
                        file_name=f"{st.session_state.nda_data['client_company_name']}_NDA.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

        # Clean up temp files
        try:
            import os
            os.unlink(template_path)
            os.unlink(pdf_output)
            os.unlink(docx_output)
        except:
            pass


# def handle_contract():
#     st.title("📄 Contract Form")
#
#     # Initialize session state for multi-page form
#     if 'contract_form_step' not in st.session_state:
#         st.session_state.contract_form_step = 1
#         st.session_state.contract_data = {}
#
#     if st.session_state.contract_form_step == 1:
#         # Step 1: Collect information
#         with st.form("contract_form"):
#             date = st.date_input("Contract Date")
#             client_company_name = st.text_input("Client Company Name")
#             client_company_address = st.text_area("Client Company Address")
#             contract_end = st.date_input("Contract End Date")
#
#             if st.form_submit_button("Generate Contract"):
#                 st.session_state.contract_data = {
#                     "date": date.strftime("%B %d, %Y"),
#                     "client_company_name": client_company_name,
#                     "client_company_address": client_company_address,
#                     "contract_end": contract_end.strftime("%B %d, %Y")
#                 }
#                 st.session_state.contract_form_step = 2
#                 st.experimental_rerun() if LOAD_LOCALLY else st.rerun()
#
#     elif st.session_state.contract_form_step == 2:
#         # Step 2: Preview and download
#         st.success("Contract generated successfully!")
#         st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'contract_form_step', 1))
#
#         # Generate documents
#
#         # replacements_docx = {
#         #     "_Date_": st.session_state.contract_data["date"],
#         #     "_Client Company Name_": st.session_state.contract_data["client_company_name"],
#         #     "_Client Company Address_": st.session_state.contract_data["client_company_address"],
#         #     "_Contract End_": st.session_state.contract_data["contract_end"]
#         # }
#         context = {
#             "date": st.session_state.contract_data["date"],
#             "client_company_name": st.session_state.contract_data["client_company_name"],
#             "client_address": st.session_state.contract_data["client_company_address"],
#             "contract_end": st.session_state.contract_data["contract_end"],
#         }
#
#         # Generate temporary files
#         pdf_output = "temp_contract.pdf"
#         docx_output = "temp_contract.docx"
#
#         # Call function
#         # replace_docx_placeholders(
#         #     input_path="Contract Template_Format_.docx",
#         #     output_path=docx_output,
#         #     replacements=replacements_docx
#         # )
#         nda_edit("contract_template.docx", docx_output, context)
#         main_converter(docx_output, pdf_output)
#
#         # Preview section
#         st.subheader("Preview")
#         st.write(f"**Contract Date:** {st.session_state.contract_data['date']}")
#         st.write(f"**Client Company Name:** {st.session_state.contract_data['client_company_name']}")
#         st.write(f"**Client Address:** {st.session_state.contract_data['client_company_address']}")
#         st.write(f"**Contract End Date:** {st.session_state.contract_data['contract_end']}")
#
#         # PDF preview (requires pdfplumber)
#         try:
#             import pdfplumber
#             with pdfplumber.open(pdf_output) as pdf:
#                 preview_page = pdf.pages[0]
#                 st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
#         except:
#             st.warning("Couldn't generate PDF preview now.")
#
#         # Download buttons
#         st.subheader("Download Documents")
#         col1, col2 = st.columns(2)
#         pdf_exists = os.path.exists(pdf_output) if pdf_output else False
#         docx_exists = os.path.exists(docx_output) if docx_output else False
#
#         with col1:
#             if pdf_exists:
#                 with open(pdf_output, "rb") as f_pdf:
#                     st.download_button(
#                         "⬇️ Download PDF",
#                         f_pdf,
#                         file_name=f"{st.session_state.contract_data['client_company_name']}_Contract.pdf",
#                         mime="application/pdf"
#                     )
#             else:
#                 st.warning("PDF file not available for download")
#
#         with col2:
#             if docx_exists:
#                 with open(docx_output, "rb") as f_docx:
#                     st.download_button(
#                         "⬇️ Download DOCX",
#                         f_docx,
#                         file_name=f"{st.session_state.contract_data['client_company_name']}_Contract.docx",
#                         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
#                     )
#             else:
#                 st.warning("DOCX file not available for download")
#
#
#         # Clean up temp files
#         try:
#             os.remove(pdf_output)
#             os.remove(docx_output)
#         except:
#             pass

def handle_contract():
    st.title("📄 Contract Form")

    # Initialize session state for multi-page form
    if 'contract_form_step' not in st.session_state:
        st.session_state.contract_form_step = 1
        st.session_state.contract_data = {}

    if st.session_state.contract_form_step == 1:
        # Step 1: Collect information
        with st.form("contract_form"):
            date = st.date_input("Contract Date")
            client_company_name = st.text_input("Client Company Name")
            client_company_address = st.text_area("Client Company Address")
            contract_end = st.date_input("Contract End Date")

            if st.form_submit_button("Generate Contract"):
                st.session_state.contract_data = {
                    "date": date.strftime("%B %d, %Y"),
                    "client_company_name": client_company_name,
                    "client_company_address": client_company_address,
                    "contract_end": contract_end.strftime("%B %d, %Y")
                }
                st.session_state.contract_form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.contract_form_step == 2:
        # Step 2: Preview and download
        st.success("Contract generated successfully!")
        st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'contract_form_step', 1))

        # Prepare context data
        context = {
            "date": st.session_state.contract_data["date"],
            "client_company_name": st.session_state.contract_data["client_company_name"],
            "client_address": st.session_state.contract_data["client_company_address"],
            "contract_end": st.session_state.contract_data["contract_end"],
        }

        # Get template from Firestore
        doc_type = "Contract"  # Adjust if your collection name is different
        try:
            template_ref = firestore_db.collection("hvt_generator").document(doc_type)
            templates = template_ref.collection("templates").order_by("order_number").limit(1).get()

            if not templates:
                st.error(f"No templates found in the database for {doc_type}")
                return

            # Get the first template (order_number = 1)
            template_doc = templates[0]
            template_data = template_doc.to_dict()

            # Visibility check
            if template_data.get('visibility', 'Private') != 'Public':
                st.error("This contract template is not currently available")
                return

            # File type check
            if template_data.get(
                    'file_type') != 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                st.error("Template is not a valid Word document (.docx)")
                return

            # Check if storage_path exists
            if 'storage_path' not in template_data:
                st.error("Template storage path not found in the database")
                return

            # Download the template file from Firebase Storage
            bucket = storage.bucket()
            blob = bucket.blob(template_data['storage_path'])

            # Create a temporary file for the template
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_template:
                blob.download_to_filename(temp_template.name)
                template_path = temp_template.name

        except Exception as e:
            st.error(f"Error fetching template: {str(e)}")
            return

        # Generate temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf, \
                tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_docx:

            pdf_output = temp_pdf.name
            docx_output = temp_docx.name

            # Use the downloaded template
            nda_edit(template_path, docx_output, context)
            main_converter(docx_output, pdf_output)

            # Preview section
            st.subheader("Preview")
            st.write(f"**Contract Date:** {st.session_state.contract_data['date']}")
            st.write(f"**Client Company Name:** {st.session_state.contract_data['client_company_name']}")
            st.write(f"**Client Address:** {st.session_state.contract_data['client_company_address']}")
            st.write(f"**Contract End Date:** {st.session_state.contract_data['contract_end']}")

            # PDF preview (requires pdfplumber)
            try:
                import pdfplumber
                with pdfplumber.open(pdf_output) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
            except:
                st.warning("Couldn't generate PDF preview now.")

            # Download buttons
            st.subheader("Download Documents")
            col1, col2 = st.columns(2)

            with col1:
                with open(pdf_output, "rb") as f_pdf:
                    st.download_button(
                        "⬇️ Download PDF",
                        f_pdf,
                        file_name=f"{st.session_state.contract_data['client_company_name']}_Contract.pdf",
                        mime="application/pdf"
                    )

            with col2:
                with open(docx_output, "rb") as f_docx:
                    st.download_button(
                        "⬇️ Download DOCX",
                        f_docx,
                        file_name=f"{st.session_state.contract_data['client_company_name']}_Contract.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

        # Clean up temp files
        try:
            import os
            os.unlink(template_path)
            os.unlink(pdf_output)
            os.unlink(docx_output)
        except Exception as e:
            st.warning(f"Error cleaning up temporary files: {str(e)}")


def fetch_proposal_templates_to_temp_dir(firestore_db, bucket):
    """
    Downloads all Proposal templates into subfolders within a temp directory.

    Returns:
        dict: A mapping of normalized template parts to their respective folder paths.
    """
    base_temp_dir = tempfile.mkdtemp(prefix="proposal_templates_")

    templates_ref = firestore_db.collection("hvt_generator").document("Proposal").collection("templates")
    templates = templates_ref.stream()

    # Display name → normalized folder key
    subdir_map = {
        "Cover Templates": "cover_templates",
        "Index Templates": "index_templates",
        "Page 3 to Page 6": "p3_to_p6_templates",
        "Business Requirements Templates": "br_templates",
        "Page 14 optional": "p_14_templates",
        "Content Templates": "content_templates"
    }

    folder_paths = {}

    for doc in templates:
        data = doc.to_dict()

        if not data.get("storage_path") or not data.get("template_part"):
            continue

        folder_key = subdir_map.get(data["template_part"], "other_templates")
        target_dir = os.path.join(base_temp_dir, folder_key)
        os.makedirs(target_dir, exist_ok=True)

        # Track path
        folder_paths[folder_key] = target_dir

        filename = f"{data.get('original_name', doc.id)}"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        target_path = os.path.join(target_dir, filename)

        try:
            blob = bucket.blob(data["storage_path"])
            blob.download_to_filename(target_path)
        except Exception as e:
            print(f"❌ Failed to download {data['storage_path']}: {e}")

    return folder_paths


























def handle_proposal():
    import os
    st.title("📄 Proposal Form")
    folder_paths = fetch_proposal_templates_to_temp_dir(firestore_db, bucket)

    # Initialize session state for multi-page form
    if 'proposal_form_step' not in st.session_state:
        st.session_state.proposal_form_step = 1
        st.session_state.proposal_data = {}

    # Step 1: Basic Information
    if st.session_state.proposal_form_step == 1:
        with st.form("proposal_form_step1"):
            st.subheader("Client Information")
            name = st.text_input("Client Name / Company Name")
            # company = st.text_input("Company Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            countries = sorted([country.name for country in pycountry.countries])
            country = st.selectbox("Select Country", countries)
            # st.subheader("Proposal Details")
            # project_name = st.text_input("Project Name")
            proposal_date = st.date_input("Proposal Date")
            # validity_days = st.number_input("Proposal Validity (Days)", min_value=1, max_value=365, value=30)

            if st.form_submit_button("Next: Select Cover Page"):
                st.session_state.proposal_data = {
                    "client_name": name,
                    # "company_name": company,
                    "email": email,
                    "phone": phone,
                    "country": country,
                    # "project_name": project_name,
                    "proposal_date": proposal_date.strftime("%B %d, %Y"),
                    # "validity_days": validity_days,
                    # "valid_until": (proposal_date + timedelta(days=validity_days)).strftime("%B %d, %Y")
                }
                st.session_state.proposal_form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # Step 2: Select Cover Page Template
    elif st.session_state.proposal_form_step == 2:
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 1))

        with st.form("proposal_form_step2"):
            st.subheader("Select Cover Page Template")

            folder_paths = fetch_proposal_templates_to_temp_dir(firestore_db, bucket)
            cover_templates_dir = folder_paths.get("cover_templates")
            print(f"cover temp _dir{cover_templates_dir}")

            cover_options = {}
            print(f"cover_temp path: {os.path.exists(cover_templates_dir)}")

            if cover_templates_dir and os.path.exists(cover_templates_dir):
                files = [f for f in os.listdir(cover_templates_dir) if f.endswith(".pdf")]
                if files:
                    for f in files:
                        cover_options[os.path.splitext(f)[0]] = os.path.join(cover_templates_dir, f)
                else:
                    st.warning("No cover templates found in cover_templates folder.")
            else:
                st.warning("Cover templates folder not available.")

            # cover_options = {
            #     "Modern": "proposal_index_template.pdf",
            #     # "Professional": "professional_cover.pdf",
            #     # "Creative": "creative_cover.pdf",
            #     # "Minimal": "minimal_cover.pdf"
            # }

            # Adjust layout based on number of options
            if len(cover_options) > 3:
                horizontal = True
            else:
                horizontal = False

            selected_cover = st.radio(
                "Choose a cover page style:",
                list(cover_options.keys()),
                horizontal=horizontal,
                index=0  # Default to first option
            )

            # Process the selected template
            template_path = cover_options[selected_cover]
            output_pdf = "temp_cover.pdf"
            pdf_editor = EditTextFile(template_path)

            modifications = {
                "Name:": f": {st.session_state.proposal_data['client_name']}",
                "Email:": f": {st.session_state.proposal_data['email']}",
                "Phone": f": {st.session_state.proposal_data['phone']}",
                "Country": f": {st.session_state.proposal_data['country']}",
                "14 April 2025": f"{st.session_state.proposal_data['proposal_date']}"
            }

            # Apply modifications and show preview
            pdf_editor.modify_pdf_fields(output_pdf, modifications, 8)

            # Display preview of the modified PDF
            try:
                import pdfplumber
                with pdfplumber.open(output_pdf) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(
                        preview_page.to_image(resolution=150).original,
                        caption=f"Preview of {selected_cover} Template",
                        use_column_width=True
                    )
            except Exception as e:
                st.warning(f"Could not generate preview: {str(e)}")
                st.info("Will use selected template for final generation")

            if st.form_submit_button("Next: Select Index Page"):
                st.session_state.proposal_data["cover_template"] = output_pdf
                st.session_state.proposal_form_step = 3
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # Step 3: Select Index Page Template
    elif st.session_state.proposal_form_step == 3:
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 2))

        # Initialize selected_index if not set


        # folder_paths = fetch_proposal_templates_to_temp_dir(firestore_db, bucket)
        index_templates_dir = folder_paths.get("index_templates")
        print(f"index temp _dir{index_templates_dir}")

        index_options = {}
        print(f"cover_temp path: {os.path.exists(index_templates_dir)}")

        if index_templates_dir and os.path.exists(index_templates_dir):
            files = [f for f in os.listdir(index_templates_dir) if f.endswith(".pdf")]
            if files:
                for f in files:
                    index_options[os.path.splitext(f)[0]] = os.path.join(index_templates_dir, f)
            else:
                st.warning("No index templates found in index_templates folder.")
        else:
            st.warning("Index templates folder not available.")

        # Define index options
        # index_options = {
        #     "Detailed": "index_type_1.pdf",
        #     "Simple": "index_type_2.pdf",
        #     "Tabular": "index_type_3.pdf",
        #     "Elegant": "index_type_4.pdf",
        #     "Tabular_2": "index_type_5.pdf",
        # }

        st.subheader("Select Index Page Template")

        # Create layout columns
        col1, col2 = st.columns([1, 2])
        if 'selected_index' not in st.session_state:
            st.session_state.selected_index = None

        options_list = list(index_options.keys())

        if (
                st.session_state.selected_index is not None
                and st.session_state.selected_index in options_list
        ):
            initial_index = options_list.index(st.session_state.selected_index)
        else:
            initial_index = 0

        with col1:
            # Select box outside the form for dynamic updates
            selected_index = st.selectbox(
                "Choose an index page style:",
                options=options_list,
                index=initial_index
            )
            # Save current selection in session state
            # st.session_state.selected_p3_p6 = selected_index
            # if 'selected_p3_p6' not in st.session_state:
            #     st.session_state.selected_p3_p6 = "p3_to_p6.pdf"

        with col2:
            # Show preview of selected index
            try:
                import pdfplumber
                with pdfplumber.open(index_options[selected_index]) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(
                        preview_page.to_image(resolution=150).original,
                        caption=f"Preview: {selected_index}",
                        use_column_width=True
                    )
            except Exception as e:
                st.warning(f"Preview not available: {str(e)}")
                st.info("Will use selected template for final generation")

        # Now wrap the submission button in the form
        with st.form("proposal_form_step3"):
            # Just the submit button
            if st.form_submit_button("Next: Select Business Requirements Sections"):
                st.info("Adding Pages 3 to 6")
                st.session_state.proposal_data["index_template"] = index_options[selected_index]
                p3_to_p6_templates_dir = folder_paths.get("p3_to_p6_templates")
                files = sorted([f for f in os.listdir(p3_to_p6_templates_dir) if not f.startswith('.')])
                first_file = files[0]
                first_file_path = os.path.join(p3_to_p6_templates_dir, first_file)

                st.session_state.proposal_data["p3_p6_template"] = first_file_path
                st.session_state.proposal_form_step = 4
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # Step 4: Select BR Page Template
    elif st.session_state.proposal_form_step == 4:
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 3))

        # Initialize selected_br if not set

        br_templates_dir = folder_paths.get("br_templates")
        print(f"br temp _dir{br_templates_dir}")

        br_options = {}
        print(f"br_temp path: {os.path.exists(br_templates_dir)}")

        if br_templates_dir and os.path.exists(br_templates_dir):
            files = [f for f in os.listdir(br_templates_dir) if f.endswith(".pdf")]
            if files:
                for f in files:
                    br_options[os.path.splitext(f)[0]] = os.path.join(br_templates_dir, f)
            else:
                st.warning("No br templates found in br_templates folder.")
        else:
            st.warning("br templates folder not available.")

        st.subheader("Select Business Requirements Page Template")

        if 'selected_br' not in st.session_state:
            st.session_state.selected_br = None

        br_options_list = list(br_options.keys())

        if (
                st.session_state.selected_br is not None
                and st.session_state.selected_br in br_options_list
        ):
            initial_br = br_options_list.index(st.session_state.selected_br)
        else:
            initial_br = 0

        # Create layout columns
        col1, col2 = st.columns([1, 2])

        with col1:
            # Select box outside the form for dynamic updates
            selected_br = st.selectbox(
                "Choose a Business Requirements page style:",
                options=br_options_list,
                index=initial_br
            )
            # Save current selection in session state
            st.session_state.selected_br = selected_br

        with col2:
            # Show preview of selected BR
            try:
                import pdfplumber
                with pdfplumber.open(br_options[selected_br]) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(
                        preview_page.to_image(resolution=150).original,
                        caption=f"Preview: {selected_br}",
                        use_column_width=True
                    )
            except Exception as e:
                st.warning(f"Preview not available: {str(e)}")
                st.info("Will use selected template for final generation")

        # Now wrap the submission button in the form
        with st.form("proposal_form_step4"):
            # Just the submit button
            if st.form_submit_button("Next: Select Content Sections"):
                st.info("Adding Pages 7 to 13")
                st.session_state.proposal_data["br_template"] = br_options[selected_br]
                st.session_state.proposal_form_step = 5
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # Step 5: Select Content Page Template
    elif st.session_state.proposal_form_step == 5:
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 4))

        content_templates_dir = folder_paths.get("content_templates")
        print(f"content temp _dir{content_templates_dir}")

        content_options = {}
        print(f"content_temp path: {os.path.exists(content_templates_dir)}")

        if content_templates_dir and os.path.exists(content_templates_dir):
            files = [f for f in os.listdir(content_templates_dir) if f.endswith(".pdf")]
            if files:
                for f in files:
                    content_options[os.path.splitext(f)[0]] = os.path.join(content_templates_dir, f)
            else:
                st.warning("No Content templates found in content_templates folder.")
        else:
            st.warning("Content templates folder not available.")

        # # Define content options
        # content_options = {
        #     "Page 14 to 20": "p_14p20_template.pdf",
        #     "Page 15 to 21": "p_15p21_template.pdf",
        #     "Page 15 to 22": "p_15p22_template.pdf"
        # }

        st.subheader("Select Content Page Template")

        if 'selected_content' not in st.session_state:
            st.session_state.selected_content = None

        content_options_list = list(content_options.keys())

        if (
                st.session_state.selected_content is not None
                and st.session_state.selected_content in content_options_list
        ):
            initial_content = content_options_list.index(st.session_state.selected_content)
        else:
            initial_content = 0

        # Create layout columns
        col1, col2 = st.columns([1, 2])

        with col1:
            # Select box outside the form for dynamic updates
            selected_content = st.selectbox(
                "Choose a Content page style:",
                options=content_options_list,
                index=initial_content
            )
            # Save current selection in session state
            st.session_state.selected_content = selected_content

        with col2:
            # Show preview of selected Content
            try:
                import pdfplumber
                with pdfplumber.open(content_options[selected_content]) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(
                        preview_page.to_image(resolution=150).original,
                        caption=f"Preview: {selected_content}",
                        use_column_width=True
                    )
            except Exception as e:
                st.warning(f"Preview not available: {str(e)}")
                st.info("Will use selected template for final generation")

        # Now wrap the submission button in the form
        with st.form("proposal_form_step5"):
            # Just the submit button
            if st.form_submit_button("Next: Preview"):
                st.session_state.proposal_data["content_template"] = content_options[selected_content]
                st.session_state.proposal_form_step = 6
                # Optional: Add file existence checks


                merger_files = [
                    st.session_state.proposal_data["cover_template"],
                    st.session_state.proposal_data["index_template"],
                    st.session_state.proposal_data["p3_p6_template"],  # Now using the correct key
                    st.session_state.proposal_data["br_template"],
                    st.session_state.proposal_data["content_template"]
                ]

                import os
                for file_path in merger_files:
                    if not os.path.exists(file_path):
                        st.error(f"File not found: {file_path}")
                        return

                merger = Merger(merger_files)
                merger.merge_pdf_files("merged_output.pdf")
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.proposal_form_step == 6:
        from PyPDF2 import PdfReader

        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 5))
        st.title("📄 Preview and Finalize Proposal")

        merged_path = "merged_output.pdf"
        try:
            reader = PdfReader(merged_path)
            num_pages = len(reader.pages)

            if 'included_pages' not in st.session_state:
                # By default include all pages
                st.session_state.included_pages = [True] * num_pages

            st.write("Use the toggles below to include or exclude each page in the final proposal:")

            for i in range(num_pages):
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.session_state.included_pages[i] = st.radio(
                        f"Page {i + 1}",
                        options=["Include", "Exclude"],
                        index=0 if st.session_state.included_pages[i] else 1,
                        key=f"page_select_{i}"
                    ) == "Include"

                with col2:
                    try:
                        import pdfplumber
                        with pdfplumber.open(merged_path) as pdf:
                            preview_image = pdf.pages[i].to_image(resolution=100)
                            st.image(
                                preview_image.original,
                                caption=f"Page {i + 1}",
                                use_column_width=True
                            )
                    except Exception as e:
                        st.warning(f"Could not preview Page {i + 1}: {str(e)}")

            if st.button("Finalize and Generate Final Proposal"):
                from PyPDF2 import PdfWriter

                final_output_path = "final_output.pdf"
                writer = PdfWriter()

                for i in range(num_pages):
                    if st.session_state.included_pages[i]:
                        writer.add_page(reader.pages[i])

                with open(final_output_path, "wb") as f_out:
                    writer.write(f_out)

                st.success("✅ Final proposal generated!")
                with open(final_output_path, "rb") as f:
                    st.download_button("Download Final Proposal", f, file_name="final_proposal.pdf")

        except FileNotFoundError:
            st.error("Merged PDF file not found. Please go back and complete the previous steps.")




