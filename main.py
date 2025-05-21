import time
import os
from datetime import datetime, timedelta
import streamlit as st
from dotenv import load_dotenv
from firebase_conf import auth, rt_db, bucket, firestore_db
from document_handlers import handle_internship_offer, handle_nda, handle_invoice, handle_contract, handle_proposal
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
import tempfile
import pdfplumber
from apscheduler.schedulers.background import BackgroundScheduler
from manage_internship_roles_tab import manage_internship_roles_tab
from docx_pdf_converter import main_converter

load_dotenv()

LOAD_LOCALLY = True

# import os
# import json
# from google.cloud import storage
# from firebase_admin import firestore
# from pathlib import Path
#
#
# def download_all_generated_files(temp_dir, firestore_db, bucket):
#     try:
#         docs = firestore_db.collection("generated_files").stream()
#         for doc in docs:
#             data = doc.to_dict()
#
#             filename = data.get("name")
#             storage_path = data.get("storage_path")
#             doc_type = data.get("doc_type", "Unknown")
#             template_part = data.get("template_part")
#             proposal_section_type = data.get("proposal_section_type")
#
#             # Construct local subfolder path
#             subfolder_parts = [doc_type]
#             if proposal_section_type:
#                 subfolder_parts.append(proposal_section_type)
#             elif template_part:
#                 subfolder_parts.append(template_part)
#
#             local_subdir = os.path.join(temp_dir, *subfolder_parts)
#             Path(local_subdir).mkdir(parents=True, exist_ok=True)
#
#             # Define full local file path
#             local_file_path = os.path.join(local_subdir, filename)
#             metadata_file_path = os.path.join(local_subdir, f"{filename}.json")
#
#             # Download file from Firebase Storage
#             blob = bucket.blob(storage_path)
#             blob.download_to_filename(local_file_path)
#
#             # Save metadata to JSON file
#             with open(metadata_file_path, "w") as f:
#                 json.dump(data, f, indent=2)
#
#         print(f"✅ All files downloaded to: {temp_dir}")
#
#     except Exception as e:
#         print(f"❌ Failed to download files: {e}")
#
#
# def pdf_view(file_input):
#     try:
#
#         with pdfplumber.open(file_input) as pdf:
#             st.subheader("Preview")
#             for i, page in enumerate(pdf.pages):
#                 st.image(
#                     page.to_image(resolution=150).original,
#                     caption=f"Page {i + 1}",
#                     use_column_width=True
#                 )
#     except Exception as e:
#         st.warning(f"Couldn't generate PDF preview: {str(e)}")

def cleanup_broken_metadata():
    """Check for and remove Firestore documents that reference non-existent storage blobs"""
    try:
        # Get all document types (e.g., Proposal, NDA, etc.)
        doc_types = firestore_db.collection("hvt_generator").stream()

        for doc_type in doc_types:
            # Get all templates for this document type
            templates_ref = firestore_db.collection("hvt_generator").document(doc_type.id).collection("templates")
            docs = templates_ref.stream()

            for doc in docs:
                data = doc.to_dict()
                if 'storage_path' in data:
                    blob = bucket.blob(data['storage_path'])
                    if not blob.exists():
                        st.warning(f"Deleting broken Firestore doc: {data.get('original_name', doc.id)}")
                        templates_ref.document(doc.id).delete()

    except Exception as e:
        st.error(f"Error during metadata cleanup: {str(e)}")


# Set up scheduled cleanup (runs daily at 2 AM)
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_broken_metadata, 'cron', hour=2)
scheduler.start()

# Initialize session state
if 'user' not in st.session_state:
    st.session_state.user = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False


def logout():
    st.session_state.user = None
    st.session_state.is_admin = False
    st.sidebar.success("Logged out successfully!")
    st.experimental_rerun() if LOAD_LOCALLY else st.rerun()


def admin_login(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        user_info = auth.get_account_info(user['idToken'])

        if user_info['users'][0]['email'] in st.secrets["custom"]["ADMIN_EMAILS"]:
            st.session_state.user = user
            st.session_state.is_admin = True
            st.success("Admin login successful!")
            return True
        else:
            st.error("Access denied. Not an admin account.")
            return False
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False


# Document types
DOCUMENT_TYPES = [
    "Internship Offer",
    "NDA",
    "Invoice",
    "Contract",
    "Proposal",
    "Admin Panel"
]

# Sidebar - Navigation and logout
# Add "History" to the list if admin is logged in
if st.session_state.get('is_admin', False):
    DOCUMENT_TYPES.insert(-1, "History")

# st.sidebar.title("📑 Navigation")
st.sidebar.title("📑 Menu")

selected_option = st.sidebar.radio("Choose a document type or Admin Panel", DOCUMENT_TYPES)

# Show logout button if logged in
if st.session_state.user:
    if st.sidebar.button("🚪 Logout"):
        logout()

# Admin panel
if selected_option == "Admin Panel":
    st.title("🔐 Admin Panel")

    if not st.session_state.is_admin:
        # Login form
        with st.form("admin_login_form"):
            admin_user = st.text_input("Admin Email")
            admin_pass = st.text_input("Password", type="password")
            login = st.form_submit_button("Login")

            if login:
                if admin_login(admin_user, admin_pass):
                    st.experimental_rerun() if LOAD_LOCALLY else st.rerun()
    else:
        # Admin dashboard
        st.success(f"Welcome Admin! ({st.session_state.user['email']})")

        # Admin panel content
        st.header("📁 Template Management")
        st.subheader("Upload New Templates")

        # Template upload section
        with st.expander("➕ Upload Template", expanded=True):
            doc_type = st.selectbox(
                "Select Document Type",
                ["Internship Offer", "NDA", "Invoice", "Contract", "Proposal"],
                key="doc_type_select"
            )

            uploaded_file = st.file_uploader(
                f"Upload {doc_type} Template",
                type=["docx", "pdf"],
                key=f"upload_{doc_type}"
            )

            if uploaded_file:
                # Additional fields for all templates
                with st.form("template_details_form"):
                    visibility = st.radio(
                        "Visibility",
                        ["Public", "Private"],
                        help="Public templates can be accessed by all users"
                    )

                    description = st.text_area("Template Description")

                    # Additional fields for Proposal
                    if doc_type == "Proposal":
                        proposal_subdir = st.selectbox(
                            "Proposal Template Category",
                            ["Cover Page", "Table of Contents", "Business Requirement", "Page 3 to 6", "Testimonials"],
                            help="Choose which part of the proposal this template belongs to"
                        )

                        subdir_map = {
                            "Cover Page": "cover_page",
                            "Table of Contents": "table_of_contents",
                            "Business Requirement": "business_requirement",
                            "Page 3 to 6": "page_3_6",
                            "Testimonials": "testimonials"
                        }
                        normalized_subdir = subdir_map[proposal_subdir]

                        # Additional fields for Proposal templates
                        # is_pdf = st.checkbox("Is this a PDF template?")
                        pdf_name = st.text_input("Name of PDF (if applicable)")
                        num_pages = st.number_input("BR Pages Number", min_value=1, value=1)

                    if st.form_submit_button("Save Template"):
                        try:
                            # Generate standardized filename
                            template_ref = firestore_db.collection("hvt_generator").document(doc_type)

                            # count = len([doc.id for doc in template_ref.collection("templates").get()])
                            count = len([doc.id for doc in template_ref.collection(
                                normalized_subdir if doc_type == "Proposal" else "templates").get()])

                            order_number = count + 1
                            file_extension = uploaded_file.name.split('.')[-1]
                            new_filename = f"template{order_number}.{file_extension}"

                            # Define storage paths
                            if doc_type == "Proposal":
                                storage_path = f"hvt_generator/Proposal/{normalized_subdir}/{new_filename}"
                            else:
                                storage_path = f"hvt_generator/{doc_type.lower().replace(' ', '_')}/templates/{new_filename}"

                            # Upload to Firebase Storage
                            blob = bucket.blob(storage_path)
                            blob.upload_from_string(
                                uploaded_file.getvalue(),
                                content_type=uploaded_file.type
                            )

                            # Generate download URL
                            download_url = blob.generate_signed_url(
                                expiration=datetime.timedelta(days=365 * 10),  # 10 year expiration
                                version="v4"
                            ) if visibility == "Private" else blob.public_url

                            # Prepare metadata
                            file_details = {
                                "name": new_filename,
                                "original_name": uploaded_file.name,
                                "doc_type": doc_type,
                                "file_type": uploaded_file.type,
                                "size_kb": f"{len(uploaded_file.getvalue()) / 1024:.1f}",
                                "size_bytes": len(uploaded_file.getvalue()),
                                "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "upload_timestamp": firestore.SERVER_TIMESTAMP,
                                "download_url": download_url,
                                "storage_path": storage_path,
                                "visibility": visibility,
                                "description": description,
                                "order_number": order_number,
                                "is_active": True
                            }

                            # Add proposal-specific fields if needed
                            if doc_type == "Proposal":
                                file_details.update({
                                    "template_part": proposal_subdir,
                                    "proposal_section_type": normalized_subdir,
                                    # "is_pdf": is_pdf,
                                    "pdf_name": pdf_name,
                                    "num_pages": num_pages
                                })

                            # Save to Firestore
                            # template_ref.collection("templates").add(file_details)
                            if doc_type == "Proposal":
                                template_ref.collection(normalized_subdir).add(file_details)
                            else:
                                template_ref.collection("templates").add(file_details)

                            # Update the document count
                            template_ref.set({
                                "template_count": order_number,
                                "last_updated": firestore.SERVER_TIMESTAMP
                            }, merge=True)

                            st.success(f"Template saved successfully as {new_filename}!")
                            st.markdown(f"**Download Link:** [Click here]({download_url})")

                        except Exception as e:
                            st.error(f"Error saving template: {str(e)}")
                            st.exception(e)

        # Template management in tabs
        st.subheader("Manage Templates")
        from streamlit_sortables import sort_items
        import streamlit as st
        import pdfplumber


        def preview_pdf_all_pages(pdf_path: str):

            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        preview_image = page.to_image(resolution=100)
                        st.image(
                            preview_image.original,
                            caption=f"Page {i + 1}",
                            use_column_width=True
                        )
            except Exception as e:
                st.warning(f"Could not preview PDF: {str(e)}")


        def show_templates_tab(doc_type):
            st.subheader(f"{doc_type} Templates")
            template_ref = firestore_db.collection("hvt_generator").document(doc_type)

            if doc_type == "Proposal":
                # Use section names as Firestore subcollections
                section_map = {
                    "Cover Page": "cover_page",
                    "Table of Contents": "table_of_contents",
                    "Business Requirement": "business_requirement",
                    "Page 3 to 6": "page_3_6",
                    "Testimonials": "testimonials"
                }

                for section_label, section_key in section_map.items():
                    st.markdown(f"### 📂 {section_label}")
                    templates = template_ref.collection(section_key).order_by("order_number").get()

                    if not templates:
                        st.info(f"No templates in {section_label}")
                        continue

                    for template_doc in templates:
                        template_data = template_doc.to_dict()
                        doc_id = template_doc.id

                        # Initialize session state for edit mode and preview
                        if f"edit_mode_{doc_id}" not in st.session_state:
                            st.session_state[f"edit_mode_{doc_id}"] = False
                        if f"show_preview_{doc_id}" not in st.session_state:
                            st.session_state[f"show_preview_{doc_id}"] = False

                        with st.expander(
                                f"📄 {template_data.get('original_name', 'Unnamed')} (Order: {template_data['order_number']})"):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                # Disabled fields by default, enabled when edit mode is on
                                new_name = st.text_area(
                                    "PDF Name",
                                    value=template_data.get("pdf_name", ""),
                                    key=f"pdf_name_{doc_id}",
                                    disabled=not st.session_state[f"edit_mode_{doc_id}"]
                                )
                                new_num_pages = st.number_input(
                                    "BR pages number",
                                    min_value=1,
                                    value=int(template_data.get("num_pages", 1)),
                                    key=f"num_pages_{doc_id}",
                                    disabled=not st.session_state[f"edit_mode_{doc_id}"]
                                )
                                new_desc = st.text_area(
                                    "Description",
                                    value=template_data.get("description", ""),
                                    key=f"desc_{doc_id}",
                                    disabled=not st.session_state[f"edit_mode_{doc_id}"]
                                )
                                new_vis = st.selectbox(
                                    "Visibility",
                                    ["Public", "Private"],
                                    index=["Public", "Private"].index(template_data.get("visibility", "Public")),
                                    key=f"vis_{doc_id}",
                                    disabled=not st.session_state[f"edit_mode_{doc_id}"]
                                )

                            with col2:
                                # Delete button
                                if st.button("🗑️ Delete Template", key=f"delete_{doc_id}"):
                                    try:
                                        blob = bucket.blob(template_data['storage_path'])
                                        blob.delete()
                                        template_ref.collection(section_key).document(doc_id).delete()
                                        st.success("Template deleted successfully")
                                        st.experimental_rerun()
                                    except Exception as e:
                                        st.error(f"Error deleting: {e}")

                                # Edit toggle button
                                edit_button_label = "✏️ Edit" if not st.session_state[
                                    f"edit_mode_{doc_id}"] else "✏️ Editing"
                                if st.button(edit_button_label, key=f"edit_toggle_{doc_id}"):
                                    st.session_state[f"edit_mode_{doc_id}"] = not st.session_state[
                                        f"edit_mode_{doc_id}"]
                                    st.experimental_rerun()

                                # Save button (only shown in edit mode)
                                if st.session_state[f"edit_mode_{doc_id}"]:
                                    if st.button("💾 Save Changes", key=f"save_{doc_id}"):
                                        template_ref.collection(section_key).document(doc_id).update({
                                            "description": new_desc,
                                            "visibility": new_vis,
                                            "pdf_name": new_name,
                                            "num_pages": new_num_pages
                                        })
                                        st.session_state[f"edit_mode_{doc_id}"] = False
                                        st.success("Metadata updated successfully")
                                        st.experimental_rerun()

                                # Preview toggle button
                                preview_button_label = "👁️ Show Preview" if not st.session_state[
                                    f"show_preview_{doc_id}"] else "👁️ Hide Preview"
                                if st.button(preview_button_label, key=f"preview_toggle_{doc_id}"):
                                    st.session_state[f"show_preview_{doc_id}"] = not st.session_state[
                                        f"show_preview_{doc_id}"]
                                    st.experimental_rerun()

                            # Preview section (conditionally shown)
                            if st.session_state[f"show_preview_{doc_id}"] and template_data[
                                'file_type'] == 'application/pdf' and template_data['visibility'] == 'Public':
                                try:
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                                        blob = bucket.blob(template_data['storage_path'])
                                        blob.download_to_filename(tmp_file.name)
                                        preview_pdf_all_pages(tmp_file.name)
                                except Exception as e:
                                    st.warning(f"❌ Skipping missing or broken preview: {str(e)}")

                            st.markdown(
                                f"**Download:** [{template_data['original_name']}]({template_data['download_url']})")

            else:
                # Rest of your code for non-Proposal templates remains the same
                templates = template_ref.collection("templates").order_by("order_number").get()
                if not templates:
                    st.info("No templates found.")
                    return

                for template_doc in templates:
                    template_data = template_doc.to_dict()
                    doc_id = template_doc.id

                    with st.expander(
                            f"📄 {template_data.get('original_name', 'Unnamed')} (Order: {template_data['order_number']})"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            new_desc = st.text_area("Edit Description", value=template_data.get("description", ""),
                                                    key=f"desc_{doc_id}")
                            new_vis = st.selectbox("Visibility", ["Public", "Private"],
                                                   index=["Public", "Private"].index(
                                                       template_data.get("visibility", "Public")), key=f"vis_{doc_id}")
                            if st.button("💾 Save Changes", key=f"save_{doc_id}"):
                                template_ref.collection("templates").document(doc_id).update({
                                    "description": new_desc,
                                    "visibility": new_vis
                                })
                                st.success("Metadata updated successfully")
                                st.experimental_rerun()

                        with col2:
                            if st.button("🗑️ Delete Template", key=f"delete_{doc_id}"):
                                try:
                                    blob = bucket.blob(template_data['storage_path'])
                                    blob.delete()
                                    template_ref.collection("templates").document(doc_id).delete()
                                    st.success("Template deleted successfully")
                                    st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"Error deleting: {e}")

                        if template_data['file_type'] == 'application/pdf' and template_data['visibility'] == 'Public':
                            try:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                                    blob = bucket.blob(template_data['storage_path'])
                                    blob.download_to_filename(tmp_file.name)
                                    preview_pdf_all_pages(tmp_file.name)
                            except Exception as e:
                                st.warning(f"❌ Skipping missing or broken preview: {str(e)}")

                        st.markdown(
                            f"**Download:** [{template_data['original_name']}]({template_data['download_url']})")

        #  History session
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Internship Offer", "NDA", "Invoice", "Contract", "Proposal", "Internship Positions"])

        with tab1:
            show_templates_tab("Internship Offer")

        with tab2:
            show_templates_tab("NDA")

        with tab3:
            show_templates_tab("Invoice")

        with tab4:
            show_templates_tab("Contract")

        with tab5:
            show_templates_tab("Proposal")

        with tab6:
            manage_internship_roles_tab()

        # import os
        # import tempfile
        # import mimetypes
        # import base64
        #
        # st.markdown("---")
        # st.subheader("🗂️ Manage Generated Documents")
        #
        # selected_generated_type = st.selectbox(
        #     "Select Document Type",
        #     ["Internship Offer", "NDA", "Invoice", "Contract", "Proposal"],
        #     key="generated_type_select"
        # )
        #
        # generated_folder = f"hvt_generator/generated/{selected_generated_type}"
        #
        # try:
        #     st.info(f"Loading generated files from: `{generated_folder}`")
        #     blobs = list(bucket.list_blobs(prefix=generated_folder))
        #
        #     if blobs:
        #         for blob in blobs:
        #             file_name = os.path.basename(blob.name)
        #             file_type, _ = mimetypes.guess_type(file_name)
        #
        #             # Save to a temporary file
        #             with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[-1]) as temp_file:
        #                 blob.download_to_filename(temp_file.name)
        #                 local_path = temp_file.name
        #
        #             col1, col2 = st.columns([6, 1])
        #             with col1:
        #                 st.markdown(f"📄 **{file_name}**")
        #
        #                 # Preview PDF
        #                 if file_type == "application/pdf":
        #                     st.markdown("Preview:")
        #                     with open(local_path, "rb") as pdf_file:
        #                         base64_pdf = base64.b64encode(pdf_file.read()).decode("utf-8")
        #                         pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="400" type="application/pdf"></iframe>'
        #                         st.markdown(pdf_display, unsafe_allow_html=True)
        #
        #                 # Preview DOCX
        #                 elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        #                     st.markdown("Preview:")
        #                     try:
        #                         from docx import Document
        #
        #                         doc = Document(local_path)
        #                         preview_text = "\n".join(
        #                             para.text for para in doc.paragraphs if para.text.strip()
        #                         )
        #                         st.text_area("📄 DOCX Preview", preview_text, height=250)
        #                     except Exception as e:
        #                         st.warning(f"Couldn't preview DOCX: {e}")
        #
        #             with col2:
        #                 if st.button("🗑 Delete", key=f"delete_{blob.name}"):
        #                     try:
        #                         blob.delete()
        #                         st.success(f"Deleted {blob.name}")
        #                         st.experimental_rerun()
        #                     except Exception as e:
        #                         st.error(f"Failed to delete: {str(e)}")
        #
        # except Exception as e:
        #     st.error(f"Error listing files: {str(e)}")


elif selected_option == "History" and st.session_state.get('is_admin', False):
    st.title("📜 Generated Documents History")

    # Create tabs for each document type
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Internship Offer",
        "NDA",
        "Invoice",
        "Contract",
        "Proposal"
    ])


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


    def display_documents_by_type(doc_type):
        try:
            # Query all documents and filter locally
            all_docs = firestore_db.collection("generated_files").stream()
            filtered_docs = []

            for doc in all_docs:
                data = doc.to_dict()
                if data.get('doc_type') == doc_type:
                    filtered_docs.append((doc.id, data))

            # Sort by upload_timestamp if available
            try:
                filtered_docs.sort(key=lambda x: x[1].get('upload_timestamp'), reverse=True)
            except:
                pass

            if not filtered_docs:
                st.info(f"No generated {doc_type} documents found.")
                return

            for doc_id, data in filtered_docs:
                with st.expander(
                        f"📄 {data.get('name', data.get('client_name', 'Unnamed Document'))} - {data.get('upload_date', '')}"):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        # Display metadata
                        st.subheader("Metadata")
                        st.json(data)

                        # Display preview if available in storage
                        if 'storage_path' in data and data.get('file_type') == 'application/pdf':
                            try:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                                    blob = bucket.blob(data['storage_path'])
                                    blob.download_to_filename(tmp_file.name)
                                    pdf_view(tmp_file.name)
                            except Exception as e:
                                st.warning(f"Couldn't preview document: {str(e)}")

                    with col2:
                        # Download button if storage_path exists
                        if 'storage_path' in data:
                            try:
                                blob = bucket.blob(data['storage_path'])
                                file_bytes = blob.download_as_bytes()

                                st.download_button(
                                    label="⬇️ Download",
                                    data=file_bytes,
                                    file_name=data.get('name', 'document'),
                                    mime=data.get('file_type', 'application/octet-stream'),
                                    key=f"download_{doc_id}"
                                )
                            except Exception as e:
                                st.error(f"Download failed: {str(e)}")

                        # Delete button
                        if st.button("🗑️ Delete", key=f"delete_{doc_id}"):
                            try:
                                # Delete from storage if path exists
                                if 'storage_path' in data:
                                    blob = bucket.blob(data['storage_path'])
                                    blob.delete()

                                # Delete from Firestore
                                firestore_db.collection("generated_files").document(doc_id).delete()

                                st.success("Document deleted successfully")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Error deleting document: {str(e)}")

                        # Show additional info if available
                        if 'client_name' in data:
                            st.caption(f"Client: {data['client_name']}")

        except Exception as e:
            st.error(f"Error loading documents: {str(e)}")


    with tab1:
        display_documents_by_type("Internship Offer")

    with tab2:
        display_documents_by_type("NDA")

    with tab3:
        display_documents_by_type("Invoice")

    with tab4:
        display_documents_by_type("Contract")

    with tab5:
        display_documents_by_type("Proposal")

# Handle document types
elif selected_option == "Internship Offer":
    handle_internship_offer()

elif selected_option == "NDA":
    handle_nda()

elif selected_option == "Invoice":
    handle_invoice()

elif selected_option == "Contract":
    handle_contract()

elif selected_option == "Proposal":
    handle_proposal()
