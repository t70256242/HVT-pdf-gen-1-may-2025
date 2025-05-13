import time
import os
from datetime import datetime, timedelta
import streamlit as st
from dotenv import load_dotenv
from firebase_conf import auth, rt_db, bucket, firestore_db
from document_handlers import handle_internship_offer, handle_nda, handle_contract, handle_proposal
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
import tempfile
import pdfplumber
from apscheduler.schedulers.background import BackgroundScheduler
from manage_internship_roles_tab import manage_internship_roles_tab

load_dotenv()

LOAD_LOCALLY = True


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
    "Contract",
    "Proposal",
    "Admin Panel"
]

# Sidebar - Navigation and logout
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
        # Template upload section
        with st.expander("➕ Upload Template", expanded=True):
            doc_type = st.selectbox(
                "Select Document Type",
                ["Internship Offer", "NDA", "Contract", "Proposal"],
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
                        num_pages = st.number_input("Number of pages", min_value=1, value=1)

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

        # # Template upload section
        # with st.expander("➕ Upload Template", expanded=True):
        #     doc_type = st.selectbox(
        #         "Select Document Type",
        #         ["Internship Offer", "NDA", "Contract", "Proposal"],
        #         key="doc_type_select"
        #     )
        #
        #     uploaded_file = st.file_uploader(
        #         f"Upload {doc_type} Template",
        #         type=["docx", "pdf"],
        #         key=f"upload_{doc_type}"
        #     )
        #
        #     if uploaded_file:
        #         # Additional fields for all templates
        #         with st.form("template_details_form"):
        #             visibility = st.radio(
        #                 "Visibility",
        #                 ["Public", "Private"],
        #                 help="Public templates can be accessed by all users"
        #             )
        #
        #             description = st.text_area("Template Description")
        #
        #             # Additional field for Proposal
        #             if doc_type == "Proposal":
        #                 proposal_subdir = st.selectbox(
        #                     "Proposal Template Category",
        #                     ["Cover Templates", "Index Templates", "Page 3 to Page 6", "Business Requirements Templates",
        #                      "Page 14 optional", "Content Templates"],
        #                     help="Choose which part of the proposal this template belongs to"
        #                 )
        #
        #                 subdir_map = {
        #                     "Cover Templates": "cover_templates",
        #                     "Index Templates": "index_templates",
        #                     "Page 3 to Page 6": "p3_to_p6_templates",
        #                     "Business Requirements Templates": "br_templates",
        #                     "Page 14 optional": "p_14_templates",
        #                     "Content Templates": "content_templates"
        #                 }
        #                 normalized_subdir = subdir_map[proposal_subdir]
        #
        #             if st.form_submit_button("Save Template"):
        #                 try:
        #                     # Generate standardized filename
        #                     template_ref = firestore_db.collection("hvt_generator").document(doc_type)
        #                     count = len([doc.id for doc in template_ref.collection("templates").get()])
        #                     order_number = count + 1
        #                     file_extension = uploaded_file.name.split('.')[-1]
        #                     new_filename = f"template{order_number}.{file_extension}"
        #
        #                     # Define storage paths
        #                     if doc_type == "Proposal":
        #                         storage_path = f"hvt_generator/proposal/{normalized_subdir}/{new_filename}"
        #                     else:
        #                         storage_path = f"hvt_generator/{doc_type.lower().replace(' ', '_')}/{new_filename}"
        #
        #                     # Upload to Firebase Storage
        #                     blob = bucket.blob(storage_path)
        #                     blob.upload_from_string(
        #                         uploaded_file.getvalue(),
        #                         content_type=uploaded_file.type
        #                     )
        #
        #                     # Generate download URL
        #                     download_url = blob.generate_signed_url(
        #                         expiration=datetime.timedelta(days=365 * 10),  # 10 year expiration
        #                         version="v4"
        #                     ) if visibility == "Private" else blob.public_url
        #
        #                     # Prepare metadata
        #                     file_details = {
        #                         "name": new_filename,
        #                         "original_name": uploaded_file.name,
        #                         "doc_type": doc_type,
        #                         "file_type": uploaded_file.type,
        #                         "size_kb": f"{len(uploaded_file.getvalue()) / 1024:.1f}",
        #                         "size_bytes": len(uploaded_file.getvalue()),
        #                         "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #                         "upload_timestamp": firestore.SERVER_TIMESTAMP,
        #                         "download_url": download_url,
        #                         "storage_path": storage_path,
        #                         "visibility": visibility,
        #                         "description": description,
        #                         "order_number": order_number,
        #                         "is_active": True
        #                     }
        #
        #                     # Add proposal-specific fields if needed
        #                     if doc_type == "Proposal":
        #                         file_details["template_part"] = proposal_subdir
        #                         file_details["proposal_section_type"] = normalized_subdir.split('_')[0].capitalize()
        #
        #                     # Save to Firestore
        #                     template_ref.collection("templates").add(file_details)
        #
        #                     # Update the document count
        #                     template_ref.set({
        #                         "template_count": order_number,
        #                         "last_updated": firestore.SERVER_TIMESTAMP
        #                     }, merge=True)
        #
        #                     st.success(f"Template saved successfully as {new_filename}!")
        #                     st.markdown(f"**Download Link:** [Click here]({download_url})")
        #
        #                 except Exception as e:
        #                     st.error(f"Error saving template: {str(e)}")
        #                     st.exception(e)

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
                                    "Number of Pages",
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



        # def show_templates_tab(doc_type):
        #     st.subheader(f"{doc_type} Templates")
        #
        #     template_ref = firestore_db.collection("hvt_generator").document(doc_type)
        #
        #     if doc_type == "Proposal":
        #         # Use section names as Firestore subcollections
        #         section_map = {
        #             "Cover Page": "cover_page",
        #             "Table of Contents": "table_of_contents",
        #             "Business Requirement": "business_requirement",
        #             "Page 3 to 6": "page_3_6",
        #             "Testimonials": "testimonials"
        #         }
        #
        #         edit_states = st.session_state.setdefault("edit_states", {})
        #
        #         for section_label, section_key in section_map.items():
        #             st.markdown(f"### 📂 {section_label}")
        #             templates = template_ref.collection(section_key).order_by("order_number").get()
        #
        #             if not templates:
        #                 st.info(f"No templates in {section_label}")
        #                 continue
        #
        #             for template_doc in templates:
        #                 template_data = template_doc.to_dict()
        #                 doc_id = template_doc.id
        #
        #                 # Track edit and preview state
        #                 edit_key = f"edit_enabled_{doc_id}"
        #                 preview_key = f"preview_visible_{doc_id}"
        #                 st.session_state.setdefault(edit_key, False)
        #                 st.session_state.setdefault(preview_key, False)
        #
        #                 with st.expander(
        #                         f"📄 {template_data.get('original_name', 'Unnamed')} (Order: {template_data['order_number']})"):
        #                     col1, col2 = st.columns([3, 1])
        #                     with col1:
        #                         disabled = not st.session_state[edit_key]
        #
        #                         new_name = st.text_input("Edit PDF Name", value=template_data.get("pdf_name", ""),
        #                                                  key=f"pdf_name_{doc_id}", disabled=disabled)
        #                         new_num_pages = st.number_input("Edit Number of Pages",
        #                                                         min_value=1,
        #                                                         value=int(template_data.get("num_pages", 1)),
        #                                                         key=f"num_pages_{doc_id}",
        #                                                         disabled=disabled)
        #                         new_desc = st.text_area("Edit Description", value=template_data.get("description", ""),
        #                                                 key=f"desc_{doc_id}", disabled=disabled)
        #                         new_vis = st.selectbox("Visibility", ["Public", "Private"],
        #                                                index=["Public", "Private"].index(
        #                                                    template_data.get("visibility", "Public")),
        #                                                key=f"vis_{doc_id}", disabled=disabled)
        #
        #                         if st.session_state[edit_key]:
        #                             save_col, preview_col = st.columns([1, 1])
        #                             with save_col:
        #                                 if st.button("💾 Save Changes", key=f"save_{doc_id}"):
        #                                     template_ref.collection(section_key).document(doc_id).update({
        #                                         "description": new_desc,
        #                                         "visibility": new_vis,
        #                                         "pdf_name": new_name,
        #                                         "num_pages": new_num_pages
        #                                     })
        #                                     st.success("Metadata updated successfully")
        #                                     st.session_state[edit_key] = False
        #                                     st.experimental_rerun()
        #                             with preview_col:
        #                                 st.toggle("📄 Show Preview", key=preview_key)
        #
        #                     with col2:
        #                         if st.button("🗑️ Delete Template", key=f"delete_{doc_id}"):
        #                             try:
        #                                 blob = bucket.blob(template_data['storage_path'])
        #                                 blob.delete()
        #                                 template_ref.collection(section_key).document(doc_id).delete()
        #                                 st.success("Template deleted successfully")
        #                                 st.experimental_rerun()
        #                             except Exception as e:
        #                                 st.error(f"Error deleting: {e}")
        #                         if st.button("✏️ Edit", key=f"edit_btn_{doc_id}"):
        #                             st.session_state[edit_key] = not st.session_state[edit_key]
        #                             st.experimental_rerun()
        #
        #                     if st.session_state[preview_key] and template_data['file_type'] == 'application/pdf' and \
        #                             template_data['visibility'] == 'Public':
        #                         try:
        #                             with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        #                                 blob = bucket.blob(template_data['storage_path'])
        #                                 blob.download_to_filename(tmp_file.name)
        #                                 preview_pdf_all_pages(tmp_file.name)
        #                         except Exception as e:
        #                             st.warning(f"❌ Skipping missing or broken preview: {str(e)}")
        #
        #                     st.markdown(
        #                         f"**Download:** [{template_data['original_name']}]({template_data['download_url']})")
        #
        #         # for section_label, section_key in section_map.items():
        #         #     st.markdown(f"### 📂 {section_label}")
        #         #     templates = template_ref.collection(section_key).order_by("order_number").get()
        #         #
        #         #     if not templates:
        #         #         st.info(f"No templates in {section_label}")
        #         #         continue
        #         #
        #         #     for template_doc in templates:
        #         #         template_data = template_doc.to_dict()
        #         #         doc_id = template_doc.id
        #         #         with st.expander(
        #         #                 f"📄 {template_data.get('original_name', 'Unnamed')} (Order: {template_data['order_number']})"):
        #         #             col1, col2 = st.columns([3, 1])
        #         #             with col1:
        #         #                 # "pdf_name": pdf_name
        #         #                 # "num_pages": num_pages
        #         #                 new_name = st.text_area("Edit Pdf name", value=template_data.get("pdf_name", ""),
        #         #                                         key=f"pdf_name_{doc_id}")
        #         #                 new_num_pages = st.number_input(
        #         #                     "Edit Number of Pages",
        #         #                     min_value=1,
        #         #                     value=int(template_data.get("num_pages", 1)),
        #         #                     key=f"num_pages_{doc_id}"
        #         #                 )
        #         #                 new_desc = st.text_area("Edit Description", value=template_data.get("description", ""),
        #         #                                         key=f"desc_{doc_id}")
        #         #                 new_vis = st.selectbox("Visibility", ["Public", "Private"],
        #         #                                        index=["Public", "Private"].index(
        #         #                                            template_data.get("visibility", "Public")),
        #         #                                        key=f"vis_{doc_id}")
        #         #                 if st.button("💾 Save Changes", key=f"save_{doc_id}"):
        #         #                     template_ref.collection(section_key).document(doc_id).update({
        #         #                         "description": new_desc,
        #         #                         "visibility": new_vis,
        #         #                         "pdf_name": new_name,
        #         #                         "num_pages": new_num_pages
        #         #                     })
        #         #                     st.success("Metadata updated successfully")
        #         #                     st.experimental_rerun()
        #         #
        #         #             with col2:
        #         #                 if st.button("🗑️ Delete Template", key=f"delete_{doc_id}"):
        #         #                     try:
        #         #                         blob = bucket.blob(template_data['storage_path'])
        #         #                         blob.delete()
        #         #                         template_ref.collection(section_key).document(doc_id).delete()
        #         #                         st.success("Template deleted successfully")
        #         #                         st.experimental_rerun()
        #         #                     except Exception as e:
        #         #                         st.error(f"Error deleting: {e}")
        #         #
        #         #             # Preview if PDF and public
        #         #             if template_data['file_type'] == 'application/pdf' and template_data[
        #         #                 'visibility'] == 'Public':
        #         #                 try:
        #         #                     with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        #         #                         blob = bucket.blob(template_data['storage_path'])
        #         #                         blob.download_to_filename(tmp_file.name)
        #         #                         preview_pdf_all_pages(tmp_file.name)
        #         #                 except Exception as e:
        #         #                     st.warning(f"❌ Skipping missing or broken preview: {str(e)}")
        #         #
        #         #             st.markdown(
        #         #                 f"**Download:** [{template_data['original_name']}]({template_data['download_url']})")
        #
        #     else:
        #         templates = template_ref.collection("templates").order_by("order_number").get()
        #         if not templates:
        #             st.info("No templates found.")
        #             return
        #
        #         for template_doc in templates:
        #             template_data = template_doc.to_dict()
        #             doc_id = template_doc.id
        #
        #             with st.expander(
        #                     f"📄 {template_data.get('original_name', 'Unnamed')} (Order: {template_data['order_number']})"):
        #                 col1, col2 = st.columns([3, 1])
        #                 with col1:
        #                     new_desc = st.text_area("Edit Description", value=template_data.get("description", ""),
        #                                             key=f"desc_{doc_id}")
        #                     new_vis = st.selectbox("Visibility", ["Public", "Private"],
        #                                            index=["Public", "Private"].index(
        #                                                template_data.get("visibility", "Public")), key=f"vis_{doc_id}")
        #                     if st.button("💾 Save Changes", key=f"save_{doc_id}"):
        #                         template_ref.collection("templates").document(doc_id).update({
        #                             "description": new_desc,
        #                             "visibility": new_vis
        #                         })
        #                         st.success("Metadata updated successfully")
        #                         st.experimental_rerun()
        #
        #                 with col2:
        #                     if st.button("🗑️ Delete Template", key=f"delete_{doc_id}"):
        #                         try:
        #                             blob = bucket.blob(template_data['storage_path'])
        #                             blob.delete()
        #                             template_ref.collection("templates").document(doc_id).delete()
        #                             st.success("Template deleted successfully")
        #                             st.experimental_rerun()
        #                         except Exception as e:
        #                             st.error(f"Error deleting: {e}")
        #
        #                 if template_data['file_type'] == 'application/pdf' and template_data['visibility'] == 'Public':
        #                     try:
        #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        #                             blob = bucket.blob(template_data['storage_path'])
        #                             blob.download_to_filename(tmp_file.name)
        #                             preview_pdf_all_pages(tmp_file.name)
        #                     except Exception as e:
        #                         st.warning(f"❌ Skipping missing or broken preview: {str(e)}")
        #
        #                 st.markdown(
        #                     f"**Download:** [{template_data['original_name']}]({template_data['download_url']})")
        #

        # def show_templates_tab(doc_type):
        #     st.subheader(f"{doc_type} Templates")
        #
        #     # Reference to Firestore collection
        #     template_ref = firestore_db.collection("hvt_generator").document(doc_type)
        #     templates = template_ref.collection("templates").order_by("order_number").get()
        #
        #     if not templates:
        #         st.info(f"No templates found for {doc_type}")
        #         return
        #
        #     if doc_type == "Proposal":
        #         # Group proposal templates by template_part
        #         grouped_templates = {}
        #         for template_doc in templates:
        #             template_data = template_doc.to_dict()
        #             section = template_data.get("template_part", "Uncategorized")
        #             grouped_templates.setdefault(section, []).append((template_doc.id, template_data))
        #
        #         for section, templates_in_section in grouped_templates.items():
        #             st.markdown(f"### {section}")
        #
        #             for doc_id, template_data in templates_in_section:
        #                 with st.expander(
        #                         f"📝 {template_data['original_name']} (Order: {template_data['order_number']})"):
        #                     st.write(f"**Description:** {template_data.get('description', '-')}")
        #                     st.write(f"**Visibility:** {template_data.get('visibility', '-')}")
        #                     st.write(f"**Upload Date:** {template_data.get('upload_date', '-')}")
        #                     st.write(f"**File Type:** {template_data.get('file_type', '-')}")
        #                     st.write(f"**Size:** {template_data.get('size_kb', '-')} KB")
        #                     st.markdown(f"[Download Template]({template_data['download_url']})")
        #
        #                     # Preview using your function if PDF + Public
        #                     if template_data['file_type'] == 'application/pdf' and template_data[
        #                         'visibility'] == 'Public':
        #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        #                             blob = bucket.blob(template_data['storage_path'])
        #                             if not blob.exists():
        #                                 st.warning(f"❌ Skipping missing file: {template_data['storage_path']}")
        #                                 return
        #                             blob.download_to_filename(tmp_file.name)
        #                             preview_pdf_all_pages(tmp_file.name)
        #                             # preview_pdf_all_pages_grid(tmp_file.name, columns=3, width=220)
        #                             # preview_pdf_all_pages_grid_with_zoom_overlay(tmp_file.name, columns=3)
        #
        #                     col1, col2, col3, col4 = st.columns(4)
        #
        #                     with col1:
        #                         if st.button(f"🔼 Move Up", key=f"move_up_{doc_id}"):
        #                             current_order = template_data['order_number']
        #                             higher_templates = [t for t in templates_in_section if
        #                                                 t[1]['order_number'] < current_order]
        #                             if higher_templates:
        #                                 nearest = max(higher_templates, key=lambda t: t[1]['order_number'])
        #                                 template_ref.collection("templates").document(doc_id).update(
        #                                     {"order_number": nearest[1]['order_number']})
        #                                 template_ref.collection("templates").document(nearest[0]).update(
        #                                     {"order_number": current_order})
        #                                 st.experimental_rerun()
        #
        #                     with col2:
        #                         if st.button(f"🔽 Move Down", key=f"move_down_{doc_id}"):
        #                             current_order = template_data['order_number']
        #                             lower_templates = [t for t in templates_in_section if
        #                                                t[1]['order_number'] > current_order]
        #                             if lower_templates:
        #                                 nearest = min(lower_templates, key=lambda t: t[1]['order_number'])
        #                                 template_ref.collection("templates").document(doc_id).update(
        #                                     {"order_number": nearest[1]['order_number']})
        #                                 template_ref.collection("templates").document(nearest[0]).update(
        #                                     {"order_number": current_order})
        #                                 st.experimental_rerun()
        #
        #                     with col3:
        #                         new_visibility = "Private" if template_data['visibility'] == "Public" else "Public"
        #                         if st.button(f"👁️ Toggle to {new_visibility}", key=f"toggle_vis_{doc_id}"):
        #                             # Update the visibility in Firestore
        #                             template_ref.collection("templates").document(doc_id).update(
        #                                 {"visibility": new_visibility})
        #                             st.success(f"Visibility changed to {new_visibility}.")
        #                             st.experimental_rerun()
        #
        #                     with col4:
        #                         if st.button(f"🗑️ Delete", key=f"delete_{doc_id}"):
        #                             try:
        #                                 blob = bucket.blob(template_data['storage_path'])
        #                                 if not blob.exists():
        #                                     st.warning(f"❌ Skipping missing file: {template_data['storage_path']}")
        #                                     return
        #                                 blob.delete()
        #                                 template_ref.collection("templates").document(doc_id).delete()
        #                                 st.success(f"Template {template_data['original_name']} deleted successfully.")
        #                                 st.experimental_rerun()
        #                             except Exception as e:
        #                                 st.error(f"Error deleting template: {str(e)}")
        #
        #     else:
        #         for template_doc in templates:
        #             template_data = template_doc.to_dict()
        #             doc_id = template_doc.id
        #
        #             with st.expander(f"📝 {template_data['original_name']} (Order: {template_data['order_number']})"):
        #                 st.write(f"**Description:** {template_data.get('description', '-')}")
        #                 st.write(f"**Visibility:** {template_data.get('visibility', '-')}")
        #                 st.write(f"**Upload Date:** {template_data.get('upload_date', '-')}")
        #                 st.write(f"**File Type:** {template_data.get('file_type', '-')}")
        #                 st.write(f"**Size:** {template_data.get('size_kb', '-')} KB")
        #                 st.markdown(f"[Download Template]({template_data['download_url']})")
        #
        #                 if template_data['file_type'] == 'application/pdf' and template_data['visibility'] == 'Public':
        #                     with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        #                         blob = bucket.blob(template_data['storage_path'])
        #                         if not blob.exists():
        #                             st.warning(f"❌ Skipping missing file: {template_data['storage_path']}")
        #                             return
        #                         blob.download_to_filename(tmp_file.name)
        #                         preview_pdf_all_pages(tmp_file.name)
        #
        #                 col1, col2, col3, col4 = st.columns(4)
        #
        #                 with col1:
        #                     if st.button(f"🔼 Move Up", key=f"move_up_{doc_id}"):
        #                         current_order = template_data['order_number']
        #                         higher_templates = [t for t in templates if t.to_dict()['order_number'] < current_order]
        #                         if higher_templates:
        #                             nearest = max(higher_templates, key=lambda t: t.to_dict()['order_number'])
        #                             template_ref.collection("templates").document(doc_id).update(
        #                                 {"order_number": nearest.to_dict()['order_number']})
        #                             template_ref.collection("templates").document(nearest.id).update(
        #                                 {"order_number": current_order})
        #                             st.experimental_rerun()
        #
        #                 with col2:
        #                     if st.button(f"🔽 Move Down", key=f"move_down_{doc_id}"):
        #                         current_order = template_data['order_number']
        #                         lower_templates = [t for t in templates if t.to_dict()['order_number'] > current_order]
        #                         if lower_templates:
        #                             nearest = min(lower_templates, key=lambda t: t.to_dict()['order_number'])
        #                             template_ref.collection("templates").document(doc_id).update(
        #                                 {"order_number": nearest.to_dict()['order_number']})
        #                             template_ref.collection("templates").document(nearest.id).update(
        #                                 {"order_number": current_order})
        #                             st.experimental_rerun()
        #
        #                 with col3:
        #                     new_visibility = "Private" if template_data['visibility'] == "Public" else "Public"
        #                     if st.button(f"👁️ Toggle to {new_visibility}", key=f"toggle_vis_{doc_id}"):
        #                         template_ref.collection("templates").document(doc_id).update(
        #                             {"visibility": new_visibility})
        #                         st.success(f"Visibility changed to {new_visibility}.")
        #                         st.experimental_rerun()
        #
        #                 with col4:
        #                     if st.button(f"🗑️ Delete", key=f"delete_{doc_id}"):
        #                         try:
        #                             blob = bucket.blob(template_data['storage_path'])
        #                             if not blob.exists():
        #                                 st.warning(f"❌ Skipping missing file: {template_data['storage_path']}")
        #                                 return
        #                             blob.delete()
        #                             template_ref.collection("templates").document(doc_id).delete()
        #                             st.success(f"Template {template_data['original_name']} deleted successfully.")
        #                             st.experimental_rerun()
        #                         except Exception as e:
        #                             st.error(f"Error deleting template: {str(e)}")


        # Create the tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Internship Offer", "NDA", "Contract", "Proposal", "Internship Positions"])

        with tab1:
            show_templates_tab("Internship Offer")

        with tab2:
            show_templates_tab("NDA")

        with tab3:
            show_templates_tab("Contract")

        with tab4:
            show_templates_tab("Proposal")

        with tab5:
            manage_internship_roles_tab()

# Handle document types
elif selected_option == "Internship Offer":
    handle_internship_offer()

elif selected_option == "NDA":
    handle_nda()

elif selected_option == "Contract":
    handle_contract()

elif selected_option == "Proposal":
    handle_proposal()
