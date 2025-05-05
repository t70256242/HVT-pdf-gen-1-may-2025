import time
import os
from datetime import datetime, timedelta
import streamlit as st
from dotenv import load_dotenv
from firebase_conf import auth, rt_db, bucket, firestore_db
from document_handlers import handle_internship_offer, handle_nda, handle_contract, handle_proposal
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

load_dotenv()

LOAD_LOCALLY = False

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
st.sidebar.title("📑 Navigation")
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

                    # Additional field for Proposal
                    if doc_type == "Proposal":
                        proposal_subdir = st.selectbox(
                            "Proposal Template Category",
                            ["Cover Templates", "Index Templates", "Rest of Proposal Templates"],
                            help="Choose which part of the proposal this template belongs to"
                        )

                        subdir_map = {
                            "Cover Templates": "cover_templates",
                            "Index Templates": "index_templates",
                            "Rest of Proposal Templates": "rest_of_proposal_templates"
                        }
                        normalized_subdir = subdir_map[proposal_subdir]

                    if st.form_submit_button("Save Template"):
                        try:
                            # Generate standardized filename
                            template_ref = firestore_db.collection("hvt_generator").document(doc_type)
                            count = len([doc.id for doc in template_ref.collection("templates").get()])
                            order_number = count + 1
                            file_extension = uploaded_file.name.split('.')[-1]
                            new_filename = f"template{order_number}.{file_extension}"

                            # Define storage paths
                            if doc_type == "Proposal":
                                storage_path = f"hvt_generator/proposal/{normalized_subdir}/{new_filename}"
                            else:
                                storage_path = f"hvt_generator/{doc_type.lower().replace(' ', '_')}/{new_filename}"

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
                                file_details["template_part"] = proposal_subdir
                                file_details["proposal_section_type"] = normalized_subdir.split('_')[0].capitalize()

                            # Save to Firestore
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
        from streamlit_sortables import sort_items


        # --- Fetch templates from Firestore ---
        def fetch_templates(doc_type):
            templates_ref = firestore_db.collection("hvt_generator").document(doc_type).collection("templates")
            docs = templates_ref.order_by("order_number").get()
            templates = [doc.to_dict() | {"id": doc.id} for doc in docs]
            return templates


        # --- Render a template card ---
        def render_template_card(template):
            st.markdown(f"**{template['original_name']}**")
            st.write(f"""
            **Type:** {template['file_type']}  
            **Size:** {template['size_kb']} KB  
            **Visibility:** {template['visibility']}  
            **Uploaded:** {template['upload_date']}
            """)

            with st.expander("🔍 Preview"):
                if template['file_type'] == "application/pdf":
                    st.pdf(template['download_url'])
                else:
                    st.info("DOCX preview not supported in-browser")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Delete", key=f"delete_{template['id']}"):
                    firestore_db.collection("hvt_generator").document(template["doc_type"]) \
                        .collection("templates").document(template["id"]).delete()
                    st.success("Deleted successfully")
                    st.experimental_rerun()
            with col2:
                if st.button("⭐ Set as Default", key=f"default_{template['id']}"):
                    # Optional logic to manage 'is_default' field
                    st.success("Set as default")


        # --- Render templates per tab ---
        def show_templates_tab(doc_type):
            templates = fetch_templates(doc_type)

            if not templates:
                st.info(f"No templates found for {doc_type}")
                return

            if doc_type == "Proposal":
                # Group by section (template_part)
                grouped = {}
                for tpl in templates:
                    part = tpl.get("template_part", "Section Template")
                    grouped.setdefault(part, []).append(tpl)

                for section, tpl_list in grouped.items():
                    st.subheader(f"📄 {section}")
                    names = [tpl['name'] for tpl in tpl_list]
                    sorted_names = sort_items(names, direction="vertical")
                    sorted_tpls = sorted(tpl_list, key=lambda t: sorted_names.index(t["name"]))

                    for tpl in sorted_tpls:
                        render_template_card(tpl)

                    for idx, tpl in enumerate(sorted_tpls, start=1):
                        firestore_db.collection("hvt_generator").document(doc_type) \
                            .collection("templates").document(tpl["id"]).update({"order_number": idx})
            else:
                names = [tpl['name'] for tpl in templates]
                sorted_names = sort_items(names, direction="vertical")
                sorted_tpls = sorted(templates, key=lambda t: sorted_names.index(t["name"]))

                for tpl in sorted_tpls:
                    render_template_card(tpl)

                for idx, tpl in enumerate(sorted_tpls, start=1):
                    firestore_db.collection("hvt_generator").document(doc_type) \
                        .collection("templates").document(tpl["id"]).update({"order_number": idx})


        # --- Tabs for each template type ---
        tab1, tab2, tab3, tab4 = st.tabs(["Internship Offer", "NDA", "Contract", "Proposal"])
        with tab1:
            show_templates_tab("Internship Offer")
        with tab2:
            show_templates_tab("NDA")
        with tab3:
            show_templates_tab("Contract")
        with tab4:
            show_templates_tab("Proposal")

        # Template statistics
        st.subheader("📊 Template Statistics")

        col1, col2, col3 = st.columns(3)
        # Optional: Fetch total template count across all types
        doc_types = ["Internship Offer", "NDA", "Contract", "Proposal"]
        all_templates = []
        for dt in doc_types:
            all_templates.extend(fetch_templates(dt))

        col1.metric("Total Templates", len(all_templates))
        col2.metric("Most Recent", max(
            [tpl['upload_date'] for tpl in all_templates],
            default="N/A"
        ))
        col3.metric("Largest Template", max(
            [tpl['size_kb'] for tpl in all_templates],
            default="N/A"
        ))

# Handle document types
elif selected_option == "Internship Offer":
    handle_internship_offer()

elif selected_option == "NDA":
    handle_nda()

elif selected_option == "Contract":
    handle_contract()

elif selected_option == "Proposal":
    handle_proposal()
