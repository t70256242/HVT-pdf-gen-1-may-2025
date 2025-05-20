import os
from datetime import datetime, timedelta
import pycountry
import streamlit as st
from nda_edit import nda_edit
from docx_pdf_converter import main_converter
from edit_proposal_cover_1 import replace_pdf_placeholders
from merge_pdf import Merger
import tempfile
from firebase_conf import auth, rt_db, bucket, firestore_db
import pdfplumber
from firebase_admin import storage
import json
import base64
import random
# import os
# from datetime import datetime
from google.cloud import storage, firestore
from invoice_editor import invoice_edit
from testimonial_page_edit import EditTextFile
import re

LOAD_LOCALLY = True


def format_currency_amount(raw_price: str) -> str:
    # Extract digits (optionally include decimal point)
    match = re.search(r"\d+(?:\.\d+)?", raw_price)
    if not match:
        return "0"

    number = float(match.group())
    return f"{number:,.2f}" if '.' in match.group() else f"{int(number):,}"


# def generate_download_link(file_path, filename):
#     with open(file_path, "rb") as f:
#         file_bytes = f.read()
#         b64 = base64.b64encode(file_bytes).decode()
#         href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">📥 Download Proposal PDF</a>'
#         st.markdown(href, unsafe_allow_html=True)


# def generate_download_link(file_path, filename, file_type, doc_type):
#     with open(file_path, "rb") as f:
#         file_bytes = f.read()
#         b64 = base64.b64encode(file_bytes).decode()
#         href = f'''
#         <a href="data:application/pdf;base64,{b64}" download="{filename}"
#            style="display: inline-block;
#                   padding: 12px 24px;
#                   background: linear-gradient(45deg, #2196F3, #00BCD4);
#                   color: white;
#                   text-decoration: none;
#                   border-radius: 6px;
#                   font-weight: bold;
#                   font-family: sans-serif;
#                   box-shadow: 0 4px 6px rgba(0,0,0,0.1);
#                   transition: all 0.3s ease;
#                   border: none;
#                   cursor: pointer;">
#            📥 Download {doc_type} {file_type}
#         </a>
#         '''
#         st.markdown(href, unsafe_allow_html=True)


def save_generated_file_to_firebase(local_file_path, doc_type, bucket):
    try:
        from datetime import datetime
        import os

        # Get filename from local path
        filename = os.path.basename(local_file_path)

        # Define storage path
        storage_path = f"hvt_generator/generated/{doc_type}/{filename}"

        # Upload to Firebase Storage
        blob = bucket.blob(storage_path)
        blob.upload_from_filename(local_file_path)

        # Make it public or generate signed URL
        public_url = blob.public_url

        st.success(f"✅ File uploaded to Firebase")
        # st.markdown(f"[📁 View File]({public_url})")

        return storage_path, public_url

    except Exception as e:
        st.error(f"❌ Failed to upload file: {e}")
        return None, None


# def generate_download_link(file_path, filename, file_type, doc_type):
#     with open(file_path, "rb") as f:
#         file_bytes = f.read()
#         b64 = base64.b64encode(file_bytes).decode()
#         href = f'''
#         <a href="data:application/pdf;base64,{b64}" download="{filename}"
#            style="display: inline-block;
#                   padding: 12px 24px;
#                   background: linear-gradient(45deg, #2196F3, #00BCD4);
#                   color: white;
#                   text-decoration: none;
#                   border-radius: 6px;
#                   font-weight: bold;
#                   font-family: sans-serif;
#                   box-shadow: 0 4px 6px rgba(0,0,0,0.1);
#                   transition: all 0.3s ease;
#                   border: none;
#                   cursor: pointer;">
#            📥 Download {doc_type} {file_type}
#         </a>
#         '''
#         st.markdown(href, unsafe_allow_html=True)


def generate_download_link(file_path, filename, file_type, doc_type):
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        b64 = base64.b64encode(file_bytes).decode()

    href = f'''
    <a href="data:application/pdf;base64,{b64}" download="{filename}"
       style="display: inline-block;
              padding: 12px 24px;
              background: linear-gradient(45deg, #2196F3, #00BCD4);
              color: white;
              text-decoration: none;
              border-radius: 6px;
              font-weight: bold;
              font-family: sans-serif;
              box-shadow: 0 4px 6px rgba(0,0,0,0.1);
              transition: all 0.3s ease;
              border: none;
              cursor: pointer;">
       📥 Download {doc_type} {file_type}
    </a>
    '''
    st.markdown(href, unsafe_allow_html=True)


def pdf_view(file_input):
    try:

        with pdfplumber.open(file_input) as pdf:
            st.subheader("Preview")
            for i, page in enumerate(pdf.pages):
                st.image(
                    page.to_image(resolution=150).original,
                    caption=f"Page {i + 1}",
                    use_column_width=True
                )
    except Exception as e:
        st.warning(f"Couldn't generate PDF preview: {str(e)}")


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
            json_path = "roles.json"
            try:
                with open(json_path, "r") as f:
                    data = json.load(f)
                    data_ = data.get("internship_position", [])
            except Exception as e:
                st.error(f"Error loading roles from JSON: {str(e)}")
            positions = data_
            position = st.selectbox("Internship Position", positions, index=0 if positions else None)

            # position = st.selectbox(
            #     "Internship Position",
            #     ["UI UX Designer", "AI Automations Developer", "Sales and Marketing"],
            #     index=0
            # )

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
        with st.spinner("Loading template and generating offer..."):
            st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'form_step', 1))

            context = {
                "date": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
                "name": st.session_state.offer_data["name"],
                "position": st.session_state.offer_data["position"],
                "stipend": str(st.session_state.offer_data["stipend"]),
                "hours": str(st.session_state.offer_data["hours"]),
                "internship_duration": str(st.session_state.offer_data["duration"]),
                "first_paycheque_date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y"),
            }

            template_path = None
            docx_output = None
            pdf_output = None

            try:
                # Create temp directory
                temp_dir = os.path.join(tempfile.gettempdir(), "hvt_offer")
                os.makedirs(temp_dir, exist_ok=True)

                # Fetch the template with order_number == 1
                doc_type = "Internship Offer"
                template_ref = firestore_db.collection("hvt_generator").document(doc_type)
                # Get all templates ordered by order_number
                templates = template_ref.collection("templates").order_by("order_number").get()

                template_doc = None
                for t in templates:
                    t_data = t.to_dict()
                    if (
                            t_data.get("visibility") == "Public" and
                            t_data.get(
                                "file_type") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" and
                            t_data.get("storage_path")
                    ):
                        blob = bucket.blob(t_data["storage_path"])
                        if blob.exists():
                            template_doc = t
                            break
                        else:
                            print(f"❌ Skipping missing file: {t_data['storage_path']}")

                if not template_doc:
                    st.error("No valid public templates found in storage")
                    return

                template_data = template_doc.to_dict()

                # templates = template_ref.collection("templates").where("order_number", "==", 1).get()
                #
                # if not templates:
                #     st.error("No templates found with order number 1 for Internship Offer")
                #     return
                #
                # template_doc = templates[0]
                # template_data = template_doc.to_dict()

                if template_data.get("visibility") != "Public":
                    st.error("This template is not publicly available")
                    return

                if template_data.get(
                        "file_type") != "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    st.error("Template must be a Word document (.docx)")
                    return

                storage_path = template_data.get("storage_path")
                if not storage_path:
                    st.error("Missing storage path in template metadata")
                    return

                blob = bucket.blob(storage_path)
                if not blob.exists():
                    # st.warning(f"❌ Skipping missing file: {storage_path}")
                    return

                template_path = os.path.join(temp_dir, "template.docx")
                blob.download_to_filename(template_path)

                docx_output = os.path.join(temp_dir, "offer.docx")
                pdf_output = os.path.join(temp_dir, "offer.pdf")

                nda_edit(template_path, docx_output, context)
                main_converter(docx_output, pdf_output)

                # Preview section
                st.subheader("Preview")
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Candidate Name:** {context['name']}")
                    st.write(f"**Position:** {context['position']}")
                    st.write(f"**Start Date:** {context['date']}")

                with col2:
                    st.write(f"**Duration:** {st.session_state.offer_data['duration']} months")
                    st.write(f"**Stipend:** ₹{context['stipend']}/month")
                    st.write(f"**First Paycheck:** {context['first_paycheque_date']}")

                pdf_view(pdf_output)

                st.subheader("Download Documents")
                col1, col2 = st.columns(2)
                file_prefix = f"{context['name'].replace(' ', ' ')} {context['position'].replace(' ', ' ')}"

                with col1:
                    if os.path.exists(pdf_output):
                        # generate_download_link(pdf_output,
                        #                        f"{file_prefix} Offer Letter.pdf", "PDF", "Internship")
                        #
                        if st.button("✅ Confirm and Upload Contract PDF", key="upload_pdf"):
                            storage_path, public_url = save_generated_file_to_firebase(pdf_output, doc_type="Internship",
                                                                                       bucket=bucket)

                            st.success("Now you can download the file:")
                            # Step 2: Show download link only after upload
                            generate_download_link(pdf_output,
                                                   f"{file_prefix} Offer Letter.pdf",
                                                   "PDF", "Internship")

                        # with open(pdf_output, "rb") as f_pdf:
                        #     st.download_button(
                        #         "⬇️ Download PDF",
                        #         f_pdf,
                        #         file_name=f"{file_prefix} Offer Letter.pdf",
                        #         mime="application/pdf"
                        #     )
                    else:
                        st.warning("PDF file not available")

                with col2:
                    if os.path.exists(docx_output):
                        # generate_download_link(docx_output,
                        #                        f"{file_prefix} Offer Letter.docx", "DOCX", "Internship")

                        if st.button("✅ Confirm and Upload Contract DOCX", key="upload_docx"):
                            storage_path, public_url = save_generated_file_to_firebase(docx_output, doc_type="Internship",
                                                                                       bucket=bucket)

                            st.success("Now you can download the file:")
                            # Step 2: Show download link only after upload
                            generate_download_link(docx_output,
                                                   f"{file_prefix} Offer Letter.docx",
                                                   "DOCX", "Internship")

                        # with open(docx_output, "rb") as f_docx:
                        #     st.download_button(
                        #         "⬇️ Download DOCX",
                        #         f_docx,
                        #         file_name=f"{file_prefix} Offer Letter.docx",
                        #         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        #     )
                    else:
                        st.warning("DOCX file not available")

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.error("Please try again or contact support if the problem persists.")

            finally:
                try:
                    for file_path in [template_path, docx_output, pdf_output]:
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
            client_name = st.text_input("Client Name")
            client_company_name = st.text_input("Client Company Name")
            client_company_address = st.text_area("Client Company Address")

            if st.form_submit_button("Generate NDA"):
                st.session_state.nda_data = {
                    "date": date.strftime("%B %d, %Y"),
                    "client_name": client_name,
                    "client_company_name": client_company_name,
                    "client_company_address": client_company_address
                }
                st.session_state.nda_form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.nda_form_step == 2:
        # Step 2: Preview and download
        # st.success("NDA generated successfully!")
        with st.spinner("Loading template and generating offer..."):
            st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'nda_form_step', 1))

            # Generate documents
            replacements_docx = {
                "date": st.session_state.nda_data["date"],
                "client_name": f"                 {st.session_state.nda_data['client_name']}",
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
                # bucket = storage.bucket()
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
            st.write(f"**Client Name:** {st.session_state.nda_data['client_name']}")
            st.write(f"**Client Company Name:** {st.session_state.nda_data['client_company_name']}")
            st.write(f"**Client Address:** {st.session_state.nda_data['client_company_address']}")

            # PDF preview (requires pdfplumber)
            pdf_view(pdf_output)

            # Download buttons
            st.subheader("Download Documents")
            col1, col2 = st.columns(2)

            with col1:
                # generate_download_link(pdf_output,
                #                        f"{st.session_state.nda_data['client_company_name']} NDA.pdf", "PDF", "NDA")
                #
                if st.button("✅ Confirm and Upload Contract PDF", key="upload_pdf"):
                    storage_path, public_url = save_generated_file_to_firebase(pdf_output, doc_type="NDA",
                                                                               bucket=bucket)

                    st.success("Now you can download the file:")
                    # Step 2: Show download link only after upload
                    generate_download_link(pdf_output,
                                           f"{st.session_state.nda_data['client_company_name']} NDA.pdf",
                                           "PDF", "NDA")


                # with open(pdf_output, "rb") as f_pdf:
                #     st.download_button(
                #         "⬇️ Download PDF",
                #         f_pdf,
                #         file_name=f"{st.session_state.nda_data['client_company_name']} NDA.pdf",
                #         mime="application/pdf"
                #     )

            with col2:
                # generate_download_link(docx_output,
                #                        f"{st.session_state.nda_data['client_company_name']} NDA.docx", "DOCX", "NDA")
                #
                if st.button("✅ Confirm and Upload Contract DOCX", key="upload_docx"):
                    storage_path, public_url = save_generated_file_to_firebase(docx_output, doc_type="NDA",
                                                                               bucket=bucket)

                    st.success("Now you can download the file:")
                    # Step 2: Show download link only after upload
                    generate_download_link(docx_output,
                                           f"{st.session_state.nda_data['client_company_name']} NDA.docx",
                                           "DOCX", "NDA")


                # with open(docx_output, "rb") as f_docx:
                #     st.download_button(
                #         "⬇️ Download DOCX",
                #         f_docx,
                #         file_name=f"{st.session_state.nda_data['client_company_name']} NDA.docx",
                #         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                #     )

        # Clean up temp files
        try:
            import os
            os.unlink(template_path)
            os.unlink(pdf_output)
            os.unlink(docx_output)
        except:
            pass


def handle_invoice():
    st.title("📄 Invoice Generator")

    # Initialize session state for multi-page form
    if 'invoice_form_step' not in st.session_state:
        st.session_state.invoice_form_step = 1
        st.session_state.invoice_data = {}

        st.session_state.payment_items = []
        st.session_state.show_description = False

    # Currency options
    currency_options = {
        "USD": {"label": "USD – US Dollar", "sign": "$", "name": "US Dollar"},
        "EUR": {"label": "EUR – Euro", "sign": "€", "name": "Euro"},
        "GBP": {"label": "GBP – British Pound", "sign": "£", "name": "British Pound"},
        "INR": {"label": "INR – Indian Rupee", "sign": "₹", "name": "Indian Rupee"},
        "NGN": {"label": "NGN – Nigerian Naira", "sign": "₦", "name": "Nigerian Naira"},
        "CAD": {"label": "CAD – Canadian Dollar", "sign": "CA$", "name": "Canadian Dollar"},
        "AUD": {"label": "AUD – Australian Dollar", "sign": "A$", "name": "Australian Dollar"},
        "JPY": {"label": "JPY – Japanese Yen", "sign": "¥", "name": "Japanese Yen"},
    }
    if "invoice_currency" not in st.session_state:
        st.session_state.invoice_currency = {}

    # Step 1: Client and Company Information
    if st.session_state.invoice_form_step == 1:
        with st.form("invoice_form_step1"):
            st.subheader("Client & Company Information")

            col1, col2 = st.columns(2)
            with col1:
                invoice_no = st.text_input("Invoice Number", placeholder="12234")
                date = st.date_input("Invoice Date", value=datetime.now().date())
                client_name = st.text_input("Client Name", placeholder="Ojo Alaba")
                client_company_name = st.text_input("Client Company Name", placeholder="Yoruba Ltd")
                client_phone = st.text_input("Client Phone", placeholder="+1 234 56000")
                client_email = st.text_input("Client Email", placeholder="unfresh@email.com")

            with col2:
                company_number = st.text_input("Your Company Phone", placeholder="+1 234 56000")
                company_gst = st.text_input("Your Company GST", placeholder="9000")
                client_address = st.text_area("Client Address",
                                              placeholder="Lead Developer Street, Anthony, Riyah Turkey")
                project_name = st.text_input("Project Name", placeholder="Tolu Scrapper")

            currency_shortcode = st.selectbox(
                "Currency Code",
                options=list(currency_options.keys()),
                format_func=lambda code: currency_options[code]["label"],  # Show full name
                index=0
            )

            currency_sign = currency_options[currency_shortcode]["sign"]
            currency_name = currency_options[currency_shortcode]["name"]
            currency_data = {
                "currency_code": currency_shortcode,
                "currency_sign": currency_sign,
                "currency_name": currency_name
            }
            print("here")
            print(f"currency data {currency_data}")
            print(f"currency data {currency_data}")
            print(f"currency data {currency_data}")
            st.session_state.invoice_currency = currency_data

            if st.form_submit_button("Continue to Items"):

                print(f"Invoice currency session state: {st.session_state.invoice_currency}")
                if not client_name.strip():
                    st.error("Please enter client name")
                    st.stop()

                st.session_state.invoice_data = {
                    "date": date.strftime("%B %d, %Y"),
                    "client_name": client_name.strip(),
                    "client_company_name": client_company_name.strip(),
                    "client_phone": client_phone.strip(),
                    "company_number": company_number.strip(),
                    "company_gst": company_gst.strip(),
                    "client_address": client_address.strip(),
                    "client_email": client_email.strip(),
                    "project_name": project_name.strip(),
                    "invoice_no": invoice_no,
                    "payment_currency": f""
                                        f"{st.session_state.invoice_currency['currency_code']} "
                                        f"{st.session_state.invoice_currency['currency_sign']}"

                }
                st.session_state.invoice_form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # Step 2
    elif st.session_state.invoice_form_step == 2:

        st.button("← Back", on_click=lambda: setattr(st.session_state, 'invoice_form_step', 1))

        if 'show_schedule' not in st.session_state:
            st.session_state.show_schedule = False

        # Display payment items
        if st.session_state.payment_items:
            st.markdown("### 💰 Current Payment Items")
            for idx, item in enumerate(st.session_state.payment_items):
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
                    with col1:
                        st.markdown(f"**{item['s_no']}.**")

                    with col2:
                        st.markdown(f"**{item['description']}.**")

                    with col3:
                        st.markdown(f"**{item['hns_code']}.**")

                    with col4:
                        st.markdown(f"**{item['price']}.**")

                    with col5:
                        if st.button("❌", key=f"remove_{idx}"):
                            st.session_state.payment_items.pop(idx)
                            st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

        # Add new item form
        with st.form("invoice_form_step2"):
            st.subheader("➕ Add New Payment Description")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                s_no = st.number_input("S.No", min_value=1, value=len(st.session_state.payment_items) + 1)
            with col2:
                description = st.text_input("Description", placeholder="Project Setup Fee")
            with col3:
                price = st.text_input("Amount", placeholder="10000")

            hns_code = st.text_input("HSN Code", placeholder="2345666")

            col1, col2 = st.columns(2)
            with col1:
                add_btn = st.form_submit_button("➕ Add")
            with col2:
                schedule_toggle = st.form_submit_button(
                    "📅 Add Payment Schedule" if not st.session_state.show_schedule else "❌ Cancel Payment Schedule")

            if add_btn:
                if not description.strip():
                    st.error("Please enter item description.")
                    st.stop()
                if not price.strip():
                    st.error("Please enter item price.")
                    st.stop()
                new_item = {
                    "s_no": str(s_no),
                    "description": description.strip(),
                    "hns_code": hns_code.strip(),
                    "price": f"{st.session_state.invoice_currency['currency_sign']}{format_currency_amount(price.strip())}",
                    "additional_desc": ""
                }
                st.session_state.payment_items.append(new_item)
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

            if schedule_toggle:
                st.session_state.show_schedule = not st.session_state.show_schedule
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

        # Payment Schedule Section
        if st.session_state.show_schedule:
            st.subheader("📅 Payment Schedule")

            if 'payment_schedule' not in st.session_state:
                st.session_state.payment_schedule = []

            if st.session_state.payment_schedule:
                st.markdown("#### Current Schedule")
                for idx, item in enumerate(st.session_state.payment_schedule):
                    with st.container():
                        col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
                        with col1:
                            st.markdown(f"**{item['s_no']}.**")
                        with col2:
                            st.markdown(f"**{item['schedule']}**")
                        with col3:
                            st.markdown(f"**{item['price']}**")
                        with col4:
                            if st.button("❌", key=f"remove_schedule_{idx}"):
                                st.session_state.payment_schedule.pop(idx)
                                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

            with st.form("payment_schedule_form"):
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    schedule_s_no = st.number_input("S.No.", min_value=1,
                                                    value=len(st.session_state.payment_schedule) + 1, key="schedule_no")
                with col2:
                    schedule_desc = st.text_input("Schedule Description", placeholder="Upon signing",
                                                  key="schedule_desc")
                with col3:
                    schedule_price = st.text_input("Amount", placeholder="10000", key="schedule_price")

                col1, col2 = st.columns(2)
                with col1:
                    add_schedule_btn = st.form_submit_button("➕ Add")
                with col2:
                    done_btn = st.form_submit_button("✅ Done with Schedule")

                if add_schedule_btn:
                    if not schedule_desc.strip():
                        st.error("Please enter schedule description.")
                        st.stop()
                    if not schedule_price.strip():
                        st.error("Please enter schedule amount.")
                        st.stop()
                    new_schedule = {
                        "s_no": str(schedule_s_no),
                        "schedule": schedule_desc.strip(),
                        "price": f"{st.session_state.invoice_currency['currency_sign']}{format_currency_amount(schedule_price.strip())}"
                    }
                    st.session_state.payment_schedule.append(new_schedule)
                    st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

                if done_btn:
                    st.session_state.show_schedule = False
                    st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

        # Proceed to Preview
        if st.session_state.payment_items:
            if st.button("➡ Continue to Preview"):
                st.session_state.invoice_data["payment_description"] = st.session_state.payment_items
                if hasattr(st.session_state, 'payment_schedule') and st.session_state.payment_schedule:
                    st.session_state.invoice_data["payment_schedule"] = st.session_state.payment_schedule
                st.session_state.invoice_form_step = 3
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()
        else:
            st.warning("⚠️ Add at least one Payment Description before continuing.")

    # Step 3: Preview and Download
    elif st.session_state.invoice_form_step == 3:
        st.button("← Back to Items", on_click=lambda: setattr(st.session_state, 'invoice_form_step', 2))

        with st.spinner("Generating invoice..."):
            # Prepare context for template
            import re
            total = sum(
                float(re.sub(r"[^\d.]", "", item["price"]))
                for item in st.session_state.payment_items
                if re.search(r"\d", item["price"])
            )
            context = {
                **st.session_state.invoice_data,
                "payment_description": st.session_state.payment_items,
                "sum": f"{st.session_state.invoice_currency['currency_sign']}{total}"
            }

            # Add amount in words
            from num2words import num2words
            def extract_numeric(price_str):
                match = re.search(r"[\d,]+(?:\.\d+)?", price_str)
                if not match:
                    return 0.0
                number_str = match.group().replace(",", "")
                return float(number_str)

            total_amount = sum(extract_numeric(item['price']) for item in st.session_state.payment_items)

            # total_amount = sum(float(item['price'].replace(',', '')) for item in st.session_state.payment_items)
            context["sum_to_word"] = f"{num2words(abs(total_amount), to='currency').title()} {st.session_state.invoice_currency['currency_name']} only."

            # Get template from Firestore
            doc_type = "Invoice"
            try:
                template_ref = firestore_db.collection("hvt_generator").document(doc_type)
                templates = template_ref.collection("templates").order_by("order_number").limit(1).get()

                if not templates:
                    st.error("No invoice templates found in the database")
                    return

                template_doc = templates[0]
                template_data = template_doc.to_dict()

                if template_data.get('visibility', 'Private') != 'Public':
                    st.error("This invoice template is not currently available")
                    return

                if template_data.get(
                        'file_type') != 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                    st.error("Template is not a valid Word document (.docx)")
                    return

                if 'storage_path' not in template_data:
                    st.error("Template storage path not found in the database")
                    return

                # Download the template
                blob = bucket.blob(template_data['storage_path'])

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
                invoice_edit(template_path, docx_output, context)
                main_converter(docx_output, pdf_output)

            # Preview section
            st.subheader("Invoice Preview")

            # Client info
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Client Name:** {context['client_name']}")
                st.write(f"**Company:** {context['client_company_name']}")
                st.write(f"**Address:** {context['client_address']}")
                st.write(f"**Phone:** {context['client_phone']}")
                st.write(f"**Email:** {context['client_email']}")

            with col2:
                st.write(f"**Invoice #:** {context['invoice_no']}")
                st.write(f"**Date:** {context['date']}")
                st.write(f"**Project:** {context['project_name']}")
                st.write(f"**GST:** {context['company_gst']}")
                st.write(f"**Currency:** {context['payment_currency']} ")

            with col3:
                with st.expander("View Invoice Data (JSON)", expanded=True):
                    st.json(st.session_state.invoice_data)

            # Total
            # st.write(f"**Total Amount:** {context['payment_currency']['sign']}{context['sum']:,.2f}")
            st.write(f"**Amount in Words:** {context['sum_to_word']}")

            # PDF preview
            pdf_view(pdf_output)

            # Download buttons
            st.subheader("Download Invoice")
            col1, col2 = st.columns(2)
            file_prefix = f"Invoice {context['client_name']} {context['invoice_no']}"

            with col1:
                # generate_download_link(
                #     pdf_output,
                #     f"{file_prefix}.pdf",
                #     "PDF", "Invoice"
                # )

                if st.button("✅ Confirm and Upload Contract PDF",  key="upload_pdf"):
                    storage_path, public_url = save_generated_file_to_firebase(pdf_output, doc_type="Invoice",
                                                                               bucket=bucket)

                    st.success("Now you can download the file:")
                    # Step 2: Show download link only after upload
                    generate_download_link(pdf_output,
                                           f"{file_prefix}.pdf",
                                           "PDF", "Invoice")

            with col2:
                # generate_download_link(
                #     docx_output,
                #     f"{file_prefix}.docx",
                #     "DOCX", "Invoice"
                # )
                if st.button("✅ Confirm and Upload Contract DOCX",  key="upload_docx"):
                    storage_path, public_url = save_generated_file_to_firebase(docx_output, doc_type="Invoice",
                                                                               bucket=bucket)

                    st.success("Now you can download the file:")
                    # Step 2: Show download link only after upload
                    generate_download_link(docx_output,
                                           f"{file_prefix}.docx",
                                           "DOCX", "Invoice")

        # Clean up temp files
        try:
            os.unlink(template_path)
            os.unlink(pdf_output)
            os.unlink(docx_output)
        except:
            pass


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
            client_name = st.text_input("Client Name")
            client_company_address = st.text_area("Client Company Address")
            contract_end = st.date_input("Contract End Date")

            if st.form_submit_button("Generate Contract"):
                st.session_state.contract_data = {
                    "date": date.strftime("%B %d, %Y"),
                    "client_company_name": client_company_name,
                    "client_name": client_name,
                    "client_company_address": client_company_address,
                    "contract_end": contract_end.strftime("%B %d, %Y")
                }
                st.session_state.contract_form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.contract_form_step == 2:
        # Step 2: Preview and download
        # st.success("Contract generated successfully!")
        with st.spinner("Loading template and generating offer..."):
            st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'contract_form_step', 1))

            # Prepare context data
            context = {
                "date": st.session_state.contract_data["date"],
                "client_company_name": st.session_state.contract_data["client_company_name"],
                "client_name": f"        {st.session_state.contract_data['client_name']}",
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
                # bucket = storage.bucket()
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
            st.write(f"**Client Name:** {st.session_state.contract_data['client_name']}")
            st.write(f"**Client Company Name:** {st.session_state.contract_data['client_company_name']}")
            st.write(f"**Client Address:** {st.session_state.contract_data['client_company_address']}")
            st.write(f"**Contract End Date:** {st.session_state.contract_data['contract_end']}")

            # PDF preview (requires pdfplumber)
            pdf_view(pdf_output)

            # Download buttons
            st.subheader("Download Documents")
            col1, col2 = st.columns(2)

            with col1:
                # generate_download_link(pdf_output,
                #                        f"{st.session_state.contract_data['client_company_name']} "
                #                        f"Contract.pdf",
                #                        "PDF", "Contract")
                if st.button("✅ Confirm and Upload Contract PDF", key="upload_pdf"):
                    storage_path, public_url = save_generated_file_to_firebase(pdf_output, doc_type="Contract",
                                                                               bucket=bucket)

                    st.success("Now you can download the file:")
                    # Step 2: Show download link only after upload
                    generate_download_link(pdf_output,
                                           f"{st.session_state.contract_data['client_company_name']} Contract.pdf",
                                           "PDF", "Contract")

                # with open(pdf_output, "rb") as f_pdf:
                #     st.download_button(
                #         "⬇️ Download PDF",
                #         f_pdf,
                #         file_name=f"{st.session_state.contract_data['client_company_name']} Contract.pdf",
                #         mime="application/pdf"
                #     )

            with col2:
                # generate_download_link(docx_output,
                #                        f"{st.session_state.contract_data['client_company_name']} Contract.docx",
                #                        "DOCX", "Contract")
                # Step 1: Confirm and upload
                if st.button("✅ Confirm and Upload Contract DOCX", key="upload_docx"):
                    storage_path, public_url = save_generated_file_to_firebase(docx_output, doc_type="Contract",
                                                                               bucket=bucket)

                    st.success("Now you can download the file:")
                    # Step 2: Show download link only after upload
                    generate_download_link(docx_output,
                                           f"{st.session_state.contract_data['client_company_name']} Contract.docx",
                                           "DOCX", "Contract")

                # with open(docx_output, "rb") as f_docx:
                #     st.download_button(
                #         "⬇️ Download DOCX",
                #         f_docx,
                #         file_name=f"{st.session_state.contract_data['client_company_name']} Contract.docx",
                #         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                #     )

        # Clean up temp files
        try:
            import os
            os.unlink(template_path)
            os.unlink(pdf_output)
            os.unlink(docx_output)
        except Exception as e:
            st.warning(f"Error cleaning up temporary files: {str(e)}")


def fetch_proposal_templates_to_temp_dir(firestore_db, bucket):
    base_temp_dir = tempfile.mkdtemp(prefix="proposal_templates_")

    # Mapping section labels to their Firestore subcollection names
    section_map = {
        "cover_page": "Cover Page",
        "table_of_contents": "Table of Contents",
        "business_requirement": "Business Requirement",
        "page_3_6": "Page 3 to 6",
        "testimonials": "Testimonials"
    }

    folder_paths = {}

    for section_key, section_label in section_map.items():
        target_dir = os.path.join(base_temp_dir, section_key)
        os.makedirs(target_dir, exist_ok=True)
        folder_paths[section_key] = target_dir

        try:
            templates_ref = firestore_db.collection("hvt_generator").document("Proposal").collection(section_key)
            templates = templates_ref.stream()

            for doc in templates:
                data = doc.to_dict()

                if not data.get("storage_path"):
                    continue

                filename = data.get("original_name", doc.id)
                if not filename.lower().endswith(".pdf"):
                    filename += ".pdf"

                target_path = os.path.join(target_dir, filename)

                try:
                    blob = bucket.blob(data["storage_path"])
                    blob.download_to_filename(target_path)
                except Exception as e:
                    print(f"❌ Failed to download {data['storage_path']}: {e}")

        except Exception as e:
            print(f"⚠️ Failed to fetch templates from section {section_key}: {e}")

    return folder_paths


def fetch_path_from_temp_dir(sub_folder, selected_template, folder_paths):
    try:
        # Ensure required input
        if not selected_template or "original_name" not in selected_template:
            st.error("Invalid template data provided.")
            return None

        the_temp_dir = folder_paths.get(sub_folder)
        if not the_temp_dir:
            st.error(f"❌ Templates folder for '{sub_folder}' not found in folder_paths.")
            return None

        # Construct expected file name
        expected_filename = selected_template["original_name"]
        if not expected_filename.lower().endswith(".pdf"):
            expected_filename += ".pdf"

        template_path = os.path.join(the_temp_dir, expected_filename)

        # Check if file exists
        if not os.path.isfile(template_path):
            st.error(f"❌ Template file not found: `{template_path}`")
            return None

        return template_path

    except Exception as e:
        st.error(f"❌ An error occurred while fetching the template path: {str(e)}")
        return None


def get_proposal_template_details(firestore_db):

    doc_type = "Proposal"
    proposal_doc_ref = firestore_db.collection("hvt_generator").document(doc_type)

    # Subcollections map
    section_keys = [
        "cover_page",
        "table_of_contents",
        "business_requirement",
        "page_3_6",
        "testimonials"
    ]

    all_templates = []

    for section_key in section_keys:
        templates = proposal_doc_ref.collection(section_key).stream()

        for doc in templates:
            data = doc.to_dict()
            if not data:
                continue

            file_details = {
                "name": data.get("name"),
                "original_name": data.get("original_name"),
                "doc_type": data.get("doc_type", "Proposal"),
                "file_type": data.get("file_type"),
                "size_kb": data.get("size_kb"),
                "size_bytes": data.get("size_bytes"),
                "upload_date": data.get("upload_date"),
                "upload_timestamp": data.get("upload_timestamp"),
                "download_url": data.get("download_url"),
                "storage_path": data.get("storage_path"),
                "visibility": data.get("visibility"),
                "description": data.get("description"),
                "order_number": data.get("order_number"),
                "is_active": data.get("is_active", True),
                "template_part": data.get("template_part"),
                "proposal_section_type": data.get("proposal_section_type"),
                "pdf_name": data.get("pdf_name"),
                "num_pages": data.get("num_pages"),
                "section_key": section_key,
                "document_id": doc.id  # Include Firestore document ID for edit/delete
            }

            all_templates.append(file_details)

    return all_templates


def get_specific_templates(all_templates, number_of_pages):
    # Filter for table_of_contents and testimonials with exactly 8 pages
    filtered_templates = [
        tpl for tpl in all_templates
        if tpl["section_key"] in ["table_of_contents", "testimonials"]
           and tpl.get("num_pages") == number_of_pages
    ]

    # Group by section and get first match from each
    result = {}
    for tpl in filtered_templates:
        if tpl["section_key"] not in result:  # Only take first match per section
            result[tpl["section_key"]] = tpl

    return result


def handle_proposal():
    st.title("📄 Proposal Form")
    st.session_state.setdefault("proposal_data", {})
    st.session_state.setdefault("proposal_form_step", 1)

    # if 'proposal_data' not in st.session_state:
    #     st.session_state.proposal_data = {}
    #
    # # Initialize session state for multi-page form
    # if 'proposal_form_step' not in st.session_state:
    #     st.session_state.proposal_form_step = 1
        # st.session_state.proposal_data = {}

    all_templates = get_proposal_template_details(firestore_db)
    folder_paths = fetch_proposal_templates_to_temp_dir(firestore_db, bucket)

    # Step 1: Basic Information
    if st.session_state.proposal_form_step == 1:
        with st.form("proposal_form_step1"):
            st.subheader("Client Information")
            name = st.text_input("Client Name")
            company = st.text_input("Company Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            countries = sorted([country.name for country in pycountry.countries])
            country = st.selectbox("Select Country", countries)
            proposal_date = st.date_input("Proposal Date")

            if st.form_submit_button("Next: Select Cover Page"):
                print("Client data",{
                        "client_name": name,
                        "company_name": company,
                        "email": email,
                        "phone": phone,
                        "country": country,
                        "proposal_date": proposal_date.strftime("%B %d, %Y")
                    })
                if not st.session_state.proposal_data:
                    st.warning("Proposal data not available")
                else:

                    st.session_state.proposal_data = {
                        "client_name": name,
                        "company_name": company,
                        "email": email,
                        "phone": phone,
                        "country": country,
                        "proposal_date": proposal_date.strftime("%B %d, %Y")
                    }
                    st.session_state.proposal_form_step = 2
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.proposal_form_step == 2:
        st.subheader("Select Cover page")
        print(f"st.session_state.proposal_data: {st.session_state.proposal_data}")
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 1))

        cover_templates = [tpl for tpl in all_templates if tpl["proposal_section_type"] == "cover_page"]

        # Build options with pdf_name as label
        cover_options = {
            tpl["pdf_name"] or tpl["original_name"]: tpl for tpl in cover_templates
        }

        if not cover_options:
            st.error("No valid cover templates available. Cannot proceed.")
            st.stop()

        col1, col2 = st.columns([1, 2])

        with col1:

            selected_cover_name = st.selectbox(
                "Choose a cover page style:",
                options=list(cover_options.keys()),
                index=0,
                key="cover_template_select"
            )

            selected_template = cover_options[selected_cover_name]
            template_path = fetch_path_from_temp_dir("cover_page", selected_template, folder_paths)

            if not template_path:
                st.warning("Cover page template file not found.")
                return

            # Ensure output path is valid in Streamlit Cloud
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                temp_img_path = temp_img.name
            # temp_dir = tempfile.gettempdir()
            # output_pdf = os.path.join(temp_dir, "modified_cover.pdf")

            # pdf_editor = EditTextFile(template_path)
            #
            # modifications = {
            #     "Name :": f": {st.session_state.proposal_data['client_name']}",
            #     "Email :": f": {st.session_state.proposal_data['email']}",
            #     "Phone :": f": {st.session_state.proposal_data['phone']}",
            #     "Country: ": f": {st.session_state.proposal_data['country']}",
            #     "Date": f"{st.session_state.proposal_data['proposal_date']}"
            # }

            replace_pdf_placeholders(
                input_path=template_path,
                output_path=temp_img_path,
                replacements={
                    "{ client_name }": f"{st.session_state.proposal_data['client_name']}",
                    "{ client_email }": f"{st.session_state.proposal_data['email']}",
                    "{ client_phone }": f"{st.session_state.proposal_data['phone']}",
                    "{ client_country }": f"{st.session_state.proposal_data['country']}",
                    "{ date }": f"{st.session_state.proposal_data['proposal_date']}"
                },
                y_offset=19
            )

            # print(f"modifications: {modifications}")
            #
            # pdf_editor.modify_pdf_fields(temp_img_path, modifications, 8)

            # Preview
            if os.path.exists(temp_img_path):
                pdf_view(temp_img_path)
            else:
                st.warning("Preview not available")

        with st.form("proposal_form_step2"):
            if st.form_submit_button("Next: Select Business Requirement Page"):
                st.session_state.proposal_data["cover_template"] = temp_img_path
                st.session_state.proposal_form_step = 3
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.proposal_form_step == 3:
        st.subheader("Select Business Requirement page")
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 2))

        br_templates = [tpl for tpl in all_templates if tpl["proposal_section_type"] == "business_requirement"]

        # Build options with pdf_name as label
        br_options = {
            tpl["pdf_name"] or tpl["original_name"]: tpl for tpl in br_templates
        }

        if not br_options:
            st.error("No valid BR templates available. Cannot proceed.")
            st.stop()

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

        col1, col2 = st.columns([1, 2])

        with col1:


            selected_br_name = st.selectbox(
                "Choose a business requirements page style:",
                options=list(br_options.keys()),
                index=0,
                key="br_template_select"
            )

            selected_br_template = br_options[selected_br_name]
            # st.session_state.selected_br = selected_br_name
        br_temp_dir = folder_paths.get("business_requirement")
        if br_temp_dir:
            # Find the matching file in the temp directory
            expected_filename = selected_br_template["original_name"]
            if not expected_filename.lower().endswith(".pdf"):
                expected_filename += ".pdf"

            template_path = os.path.join(br_temp_dir, expected_filename)

            if os.path.exists(template_path):
                modifications = {
                    "{ client_name }": (f"    {st.session_state.proposal_data['client_name']}", 0, 7),
                    "{ date }": (f"{st.session_state.proposal_data['proposal_date']}", -30, 0)
                }
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_br:
                    temp_br_path = temp_br.name
                # temp_dir = tempfile.gettempdir()
                # output_pdf = os.path.join(temp_dir, "modified_testimonials.pdf")
                editor = EditTextFile(template_path)
                editor.modify_pdf_fields(temp_br_path, modifications)

                st.session_state.selected_br = temp_br_path
                st.session_state.proposal_data["br_template"] = st.session_state.selected_br
                try:
                    br_num_pages = selected_br_template.get("num_pages")
                    st.write(f"This BR template has {br_num_pages} page(s)")
                except Exception as e:
                    st.warning(f"⚠️ Could not read number of pages of Template: {str(e)}")
                    st.stop()

                specific_templates = get_specific_templates(all_templates, br_num_pages)

                pdf_view(temp_br_path)
            else:
                st.error(f"Template file not found: {template_path}")
        else:
            st.error("Business requirement templates directory not found")
        # pdf_view(br_options[selected_br_name])

        # with col2:
        #     # Get the path to the downloaded template in temp directory
        #     br_temp_dir = folder_paths.get("business_requirement")
        #     if br_temp_dir:
        #         # Find the matching file in the temp directory
        #         expected_filename = selected_br_template["original_name"]
        #         if not expected_filename.lower().endswith(".pdf"):
        #             expected_filename += ".pdf"
        #
        #         template_path = os.path.join(br_temp_dir, expected_filename)
        #
        #         if os.path.exists(template_path):
        #             modifications = {
        #                 "{ client_name }": (f"    {st.session_state.proposal_data['client_name']}", 0, 7),
        #                 "{ date }": (f"{st.session_state.proposal_data['proposal_date']}", -30, 0)
        #             }
        #             with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_br:
        #                 temp_br_path = temp_br.name
        #             # temp_dir = tempfile.gettempdir()
        #             # output_pdf = os.path.join(temp_dir, "modified_testimonials.pdf")
        #             editor = EditTextFile(template_path)
        #             editor.modify_pdf_fields(temp_br_path, modifications)
        #
        #             st.session_state.selected_br = temp_br_path
        #             st.session_state.proposal_data["br_template"] = st.session_state.selected_br
        #             try:
        #                 br_num_pages = selected_br_template.get("num_pages")
        #                 st.write(f"This BR template has {br_num_pages} page(s)")
        #             except Exception as e:
        #                 st.warning(f"⚠️ Could not read number of pages of Template: {str(e)}")
        #                 st.stop()
        #
        #             specific_templates = get_specific_templates(all_templates, br_num_pages)
        #
        #             pdf_view(temp_br_path)
        #         else:
        #             st.error(f"Template file not found: {template_path}")
        #     else:
        #         st.error("Business requirement templates directory not found")
        #     # pdf_view(br_options[selected_br_name])

        with st.form("proposal_form_step4"):
            if st.form_submit_button("Next: Preview Proposal"):

                section_dir = folder_paths.get("page_3_6")
                p3_p6_templates = [
                    os.path.join(section_dir, f)
                    for f in os.listdir(section_dir)
                    if f.lower().endswith(".pdf")
                ]
                st.session_state.proposal_data["p3_p6_template"] = p3_p6_templates
                st.session_state.proposal_data["br_template"] = st.session_state.selected_br
                table_of_contents = specific_templates.get("table_of_contents")
                testimonial = specific_templates.get("testimonials")

                selected_table_of_content = fetch_path_from_temp_dir("table_of_contents", table_of_contents,
                                                                     folder_paths)
                selected_testimonial = fetch_path_from_temp_dir("testimonials", testimonial, folder_paths)
                st.session_state.proposal_data["table_of_contents"] = selected_table_of_content
                st.session_state.proposal_data["testimonials"] = selected_testimonial

                merger_files = []

                # Cover page
                cover = st.session_state.proposal_data.get("cover_template")
                if cover and os.path.exists(cover):
                    merger_files.append(cover)
                else:
                    st.info("Cover Template not available.")

                # Table of Contents
                toc = st.session_state.proposal_data.get("table_of_contents")
                if toc and os.path.exists(toc):
                    merger_files.append(toc)
                else:
                    st.info("Table of Contents Template for the selected BR page count is unavailable.")

                # Page 3 to 6
                p3_p6_list = st.session_state.proposal_data.get("p3_p6_template", [])
                if p3_p6_list:
                    available_p3_p6 = [p for p in p3_p6_list if os.path.exists(p)]
                    if available_p3_p6:
                        merger_files.extend(available_p3_p6)
                    else:
                        st.info("Page 3 to 6 Templates are missing.")
                else:
                    st.info("No Page 3 to 6 Templates found.")

                # Business Requirement
                br = st.session_state.proposal_data.get("br_template")
                if br and os.path.exists(br):
                    merger_files.append(br)
                else:
                    st.info("Business Requirement Template unavailable.")

                # Testimonials
                testimonials = st.session_state.proposal_data.get("testimonials")
                if testimonials and os.path.exists(testimonials):

                    merger_files.append(testimonials)
                else:
                    st.info("Testimonial Template for the selected BR page count is unavailable.")

                for file_path in merger_files:
                    print(file_path)
                    if file_path is None:
                        continue
                    if not os.path.exists(file_path):
                        st.error(f"File not found: {file_path}")
                        return

                merger = Merger(merger_files)
                merger.merge_pdf_files("merged_output.pdf")

                st.session_state.proposal_form_step = 4
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()
    # Page 4: Final Preview and Download
    elif st.session_state.proposal_form_step == 4:
        st.subheader("📄 Final Proposal Preview")
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 3))

        st.markdown("""
            <style>
                .download-col > div {
                    text-align: center;
                }
            </style>
        """, unsafe_allow_html=True)

        # Proposal metadata summary
        st.markdown("#### 🧾 Proposal Details")
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Client Name:** {st.session_state.proposal_data['client_name']}")
            st.write(f"**Company:** {st.session_state.proposal_data['company_name']}")
            st.write(f"**Email:** {st.session_state.proposal_data['email']}")
            st.write(f"**Phone:** {st.session_state.proposal_data['phone']}")

        with col2:
            st.write(f"**Country:** {st.session_state.proposal_data['country']}")
            st.write(f"**Proposal Date:** {st.session_state.proposal_data['proposal_date']}")

        # st.divider()
        st.markdown("---")

        # PDF Preview
        if os.path.exists("merged_output.pdf"):
            st.markdown("#### 📑 Preview of Merged Proposal")
            pdf_view("merged_output.pdf")
        else:
            st.error("Merged proposal file not found.")
            st.stop()

        # st.divider()
        st.markdown("---")

        # Download section
        st.markdown("#### ⬇️ Download Final Proposal")
        download_col1, download_col2 = st.columns([2, 1], gap="medium")

        # query_params = st.experimental_get_query_params()
        # upload_trigger = query_params.get("upload_trigger", ["0"])[0] == "1"
        #
        # with download_col1:
        #     default_filename = f"{st.session_state.proposal_data['client_name'].replace(' ', ' ')} Proposal.pdf"
        #
        #     # generate_download_link("merged_output.pdf", default_filename, "PDF", "Proposal")
        #     generate_download_link("merged_output.pdf", default_filename,
        #                            "PDF", "Proposal")
        #     if upload_trigger:
        #         save_generated_file_to_firebase("merged_output.pdf", doc_type="Proposal", bucket=bucket)
        #         # Reset trigger to prevent multiple uploads
        #         st.experimental_set_query_params(upload_trigger="0")
        with download_col1:
            default_filename = f"{st.session_state.proposal_data['client_name'].replace(' ', '_')} Proposal.pdf"

            # Step 1: Confirm and upload
            if st.button("✅ Confirm and Upload Proposal"):
                storage_path, public_url = save_generated_file_to_firebase("merged_output.pdf", doc_type="Proposal",
                                                                           bucket=bucket)
                st.success("Now you can download the file:")
                # Step 2: Show download link only after upload
                generate_download_link("merged_output.pdf", default_filename, "PDF", "Proposal")

            # default_filename = f"{st.session_state.proposal_data['client_name'].replace(' ', ' ')} Proposal.pdf"
            # generate_download_link("merged_output.pdf", default_filename,
            #                        "PDF", "Proposal")
            # save_generated_file_to_firebase("merged_output.pdf", doc_type="Proposal", bucket=bucket)


        with download_col2:
            if st.button("🔁 Start Over"):
                for key in [
                    'proposal_form_step', 'proposal_data', 'selected_br'
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()


