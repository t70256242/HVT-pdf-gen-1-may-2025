import time
import os
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from internship_template_edit import fill_pdf_template
from internship_docx_edit import replace_docx_placeholders
from firebase_conf import auth, rt_db, bucket, firestore_db

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
        #
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
                # Save to database/storage
                file_details = {
                    "name": uploaded_file.name,
                    "type": doc_type,
                    "size": f"{len(uploaded_file.getvalue()) / 1024:.1f} KB",
                    "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M")
                }

                if st.button("Save Template"):
                    # Add your save logic here (Firebase/DB)
                    st.session_state.templates[doc_type] = file_details
                    st.success(f"{doc_type} template saved successfully!")

        st.subheader("📋 Current Templates")

        # Template management in tabs
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Internship Offer", "NDA", "Contract", "Proposal"]
        )


        def show_template_tab(doc_type):
            """Reusable function for template tabs"""
            if doc_type in st.session_state.templates:
                template = st.session_state.templates[doc_type]

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"""
                    **File Name**: {template['name']}  
                    **Type**: {template['type']}  
                    **Size**: {template['size']}  
                    **Uploaded**: {template['upload_date']}
                    """)

                    # Preview section
                    with st.expander("🔍 Preview"):
                        if template['name'].endswith('.pdf'):
                            st.pdf(uploaded_file)
                        else:
                            st.warning("DOCX preview requires conversion to PDF")

                with col2:
                    st.button(
                        "🗑️ Delete",
                        key=f"delete_{doc_type}",
                        on_click=lambda: st.session_state.templates.pop(doc_type)
                    )
                    st.button(
                        "⬆️ Set as Default",
                        key=f"default_{doc_type}"
                    )
            else:
                st.warning(f"No {doc_type} template uploaded yet")


        # Initialize session state for templates if not exists
        if 'templates' not in st.session_state:
            st.session_state.templates = {}

        # Show all tabs
        with tab1:
            show_template_tab("Internship Offer")

        with tab2:
            show_template_tab("NDA")

        with tab3:
            show_template_tab("Contract")

        with tab4:
            show_template_tab("Proposal")

        # Template statistics
        st.subheader("📊 Template Statistics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Templates", len(st.session_state.templates))
        col2.metric("Most Recent", max(
            [t['upload_date'] for t in st.session_state.templates.values()],
            default="N/A"
        ))
        col3.metric("Largest Template", max(
            [t['size'] for t in st.session_state.templates.values()],
            default="N/A"
        ))

        # Bulk actions
        with st.expander("⚙️ Bulk Actions"):
            st.download_button(
                "📥 Export All Templates",
                data=str(st.session_state.templates),
                file_name="templates_backup.json"
            )
            st.button(
                "🔄 Refresh All Templates",
                help="Reload templates from database"
            )

# Internship Offer form
elif selected_option == "Internship Offer":
    st.title("📄 Internship Offer Form")

    # Initialize session state for multi-page form
    if 'form_step' not in st.session_state:
        st.session_state.form_step = 1
        st.session_state.offer_data = {}

    if st.session_state.form_step == 1:
        # Step 1: Collect information
        with st.form("internship_offer_form"):
            name = st.text_input("Candidate Name")
            position = st.selectbox(
                "Internship Position",
                ["UI UX Designer", "AI Automations Developer", "Sales and Marketing"],
                index=0
            )
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
            stipend_input = st.text_input("Stipend (write out digits, no commas or dot)")
            # stipend = "{:,.2f}".format(int(stipend))
            if stipend_input.strip().isdigit():
                stipend = "{:,.2f}".format(int(stipend_input))
            else:
                stipend = "0.00"
            hours = st.text_input("Work Hours per week")
            duration = st.number_input("Internship Duration (In Months)", min_value=1, max_value=24, step=1)
            first_paycheck = st.date_input("First Paycheck Date")

            if st.form_submit_button("Generate Offer"):
                st.session_state.offer_data = {
                    "name": name,
                    "position": position,
                    "start_date": start_date,
                    "end_date": end_date,
                    "stipend": stipend,
                    "hours": hours,
                    "duration": duration,
                    "first_paycheck": first_paycheck
                }
                st.session_state.form_step = 2
                st.experimental_rerun()

    elif st.session_state.form_step == 2:
        # Step 2: Preview and download
        st.success("Offer generated successfully!")
        st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'form_step', 1))

        # Generate documents
        replacements_pdf = {
            "an _Position_": st.session_state.offer_data["position"],
            "_Date_": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
            "_Name_,": st.session_state.offer_data["name"] + ",",
            "_Stipend_/": st.session_state.offer_data["stipend"],
            "_Hrs_": st.session_state.offer_data["hours"],
            "_Internship_Duration_ months,": f"{st.session_state.offer_data['duration']} months,",
            "_First_Pay_Cheque_Date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y")
        }

        replacements_docx = {
            "_Date_": replacements_pdf["_Date_"],
            "_Name_": st.session_state.offer_data["name"],
            "_Position_": st.session_state.offer_data["position"],
            "_Stipend_": str(st.session_state.offer_data["stipend"]),
            "_Hrs_": str(st.session_state.offer_data["hours"]),
            "_Internship_Duration_": str(st.session_state.offer_data["duration"]),
            "_First_Pay_Cheque_Date": replacements_pdf["_First_Pay_Cheque_Date"]
        }

        # Generate temporary files
        pdf_output = "temp_offer.pdf"
        docx_output = "temp_offer.docx"

        fill_pdf_template("Internship Offer Letter Template.pdf", pdf_output, replacements_pdf, 11)
        replace_docx_placeholders("Internship Offer Letter Template.docx", docx_output, replacements_docx)

        # Preview section
        st.subheader("Preview")
        st.write(f"**Candidate Name:** {st.session_state.offer_data['name']}")
        st.write(f"**Position:** {st.session_state.offer_data['position']}")
        st.write(f"**Duration:** {st.session_state.offer_data['duration']} months")
        st.write(f"**Stipend:** ₹{st.session_state.offer_data['stipend']}/month")

        # PDF preview (requires pdfplumber)
        try:
            import pdfplumber

            with pdfplumber.open(pdf_output) as pdf:
                preview_page = pdf.pages[0]
                st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
        except:
            st.warning("Couldn't generate PDF preview. Install pdfplumber for previews.")

        # Download buttons
        st.subheader("Download Documents")
        col1, col2 = st.columns(2)
        with open(pdf_output, "rb") as f_pdf, open(docx_output, "rb") as f_docx:
            with col1:
                st.download_button(
                    "⬇️ Download PDF",
                    f_pdf,
                    file_name=f"Offer_{st.session_state.offer_data['name']}.pdf",
                    mime="application/pdf"
                )
            with col2:
                st.download_button(
                    "⬇️ Download DOCX",
                    f_docx,
                    file_name=f"Offer_{st.session_state.offer_data['name']}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

        # Clean up temp files
        try:
            os.remove(pdf_output)
            os.remove(docx_output)
        except:
            pass