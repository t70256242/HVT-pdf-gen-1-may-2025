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

LOAD_LOCALLY = False


def handle_internship_offer():
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
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    elif st.session_state.form_step == 2:
        # Step 2: Preview and download
        st.success("Offer generated successfully!")
        st.button("← Back to Form", on_click=lambda: setattr(st.session_state, 'form_step', 1))

        # replacements_docx = {
        #     "_Date_": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
        #     "_Name_": st.session_state.offer_data["name"],
        #     "_Position_": st.session_state.offer_data["position"],
        #     "_Stipend_": str(st.session_state.offer_data["stipend"]),
        #     "_Hrs_": str(st.session_state.offer_data["hours"]),
        #     "_Internship_Duration_": str(st.session_state.offer_data["duration"]),
        #     "_First_Pay_Cheque_Date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y")
        # }
        context = {
            "date": st.session_state.offer_data["start_date"].strftime("%B %d, %Y"),
            "name": st.session_state.offer_data["name"],
            "position": st.session_state.offer_data["position"],
            "stipend": str(st.session_state.offer_data["stipend"]),
            "hours": str(st.session_state.offer_data["hours"]),
            "internship_duration": str(st.session_state.offer_data["duration"]),
            "first_paycheck_date": st.session_state.offer_data["first_paycheck"].strftime("%B %d, %Y"),
        }

        # nda_edit("internship_template.docx", "wowo.docx", context)

        # Generate temporary files
        pdf_output = "temp_offer.pdf"
        docx_output = "temp_offer.docx"

        # replace_docx_placeholders("Internship Offer Letter Template.docx", docx_output, replacements_docx)
        nda_edit("internship_template.docx", docx_output, context)
        main_converter(docx_output, pdf_output)

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
            st.warning("Couldn't generate PDF preview. PDF file not available now.")

        # Download buttons
        st.subheader("Download Documents")
        col1, col2 = st.columns(2)
        # Check if files exist before trying to open them
        pdf_exists = os.path.exists(pdf_output) if pdf_output else False
        docx_exists = os.path.exists(docx_output) if docx_output else False

        with col1:
            if pdf_exists:
                with open(pdf_output, "rb") as f_pdf:
                    st.download_button(
                        "⬇️ Download PDF",
                        f_pdf,
                        file_name=f"Offer_{st.session_state.offer_data['name']}.pdf",
                        mime="application/pdf"
                    )
            else:
                st.warning("PDF file not available for download")

        with col2:
            if docx_exists:
                with open(docx_output, "rb") as f_docx:
                    st.download_button(
                        "⬇️ Download DOCX",
                        f_docx,
                        file_name=f"Offer_{st.session_state.offer_data['name']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            else:
                st.warning("DOCX file not available for download")

        # Clean up temp files
        try:
            os.remove(pdf_output)
            os.remove(docx_output)
        except:
            pass


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

        # Generate temporary files
        pdf_output = "temp_nda.pdf"
        docx_output = "temp_nda.docx"

        nda_edit("nda_template.docx", docx_output, replacements_docx)
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

        # Check if files exist before trying to open them
        pdf_exists = os.path.exists(pdf_output) if pdf_output else False
        docx_exists = os.path.exists(docx_output) if docx_output else False

        with col1:
            if pdf_exists:
                with open(pdf_output, "rb") as f_pdf:
                    st.download_button(
                        "⬇️ Download PDF",
                        f_pdf,
                        file_name=f"{st.session_state.offer_data['name']}_NDA.pdf",
                        mime="application/pdf"
                    )
            else:
                st.warning("PDF file not available for download")

        with col2:
            if docx_exists:
                with open(docx_output, "rb") as f_docx:
                    st.download_button(
                        "⬇️ Download DOCX",
                        f_docx,
                        file_name=f"{st.session_state.offer_data['name']}_NDA.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            else:
                st.warning("DOCX file not available for download")

        # Clean up temp files
        try:
            os.remove(pdf_output)
            os.remove(docx_output)
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

        # Generate documents

        # replacements_docx = {
        #     "_Date_": st.session_state.contract_data["date"],
        #     "_Client Company Name_": st.session_state.contract_data["client_company_name"],
        #     "_Client Company Address_": st.session_state.contract_data["client_company_address"],
        #     "_Contract End_": st.session_state.contract_data["contract_end"]
        # }
        context = {
            "date": st.session_state.contract_data["date"],
            "client_company_name": st.session_state.contract_data["client_company_name"],
            "client_address": st.session_state.contract_data["client_company_address"],
            "contract_end": st.session_state.contract_data["contract_end"],
        }

        # Generate temporary files
        pdf_output = "temp_contract.pdf"
        docx_output = "temp_contract.docx"

        # Call function
        # replace_docx_placeholders(
        #     input_path="Contract Template_Format_.docx",
        #     output_path=docx_output,
        #     replacements=replacements_docx
        # )
        nda_edit("contract_template.docx", docx_output, context)
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
        pdf_exists = os.path.exists(pdf_output) if pdf_output else False
        docx_exists = os.path.exists(docx_output) if docx_output else False

        with col1:
            if pdf_exists:
                with open(pdf_output, "rb") as f_pdf:
                    st.download_button(
                        "⬇️ Download PDF",
                        f_pdf,
                        file_name=f"{st.session_state.contract_data['client_company_name']}_Contract.pdf",
                        mime="application/pdf"
                    )
            else:
                st.warning("PDF file not available for download")

        with col2:
            if docx_exists:
                with open(docx_output, "rb") as f_docx:
                    st.download_button(
                        "⬇️ Download DOCX",
                        f_docx,
                        file_name=f"{st.session_state.contract_data['client_company_name']}_Contract.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            else:
                st.warning("DOCX file not available for download")


        # Clean up temp files
        try:
            os.remove(pdf_output)
            os.remove(docx_output)
        except:
            pass


def handle_proposal():
    st.title("📄 Proposal Form")

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

            cover_options = {
                "Modern": "proposal_index_template.pdf",
                # "Professional": "professional_cover.pdf",
                # "Creative": "creative_cover.pdf",
                # "Minimal": "minimal_cover.pdf"
            }

            selected_cover = st.radio(
                "Choose a cover page style:",
                list(cover_options.keys()),
                horizontal=True
            )

            output_pdf = "temp_cover.pdf"
            pdf_editor = EditTextFile("proposal_index_template.pdf")

            modifications = {
                "Name:": f": {st.session_state.proposal_data['client_name']}",
                "Email:": f": {st.session_state.proposal_data['email']}",
                "Phone": f": {st.session_state.proposal_data['phone']}",
                "Country": f": {st.session_state.proposal_data['country']}",
                "14 April 2025": f"{st.session_state.proposal_data['proposal_date']}"
            }

            pdf_editor.modify_pdf_fields(output_pdf, modifications, 8)
            # st.session_state.filled_page1 = output_pdf

            try:
                import pdfplumber
                with pdfplumber.open(output_pdf) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
            except:
                st.warning("PDF preview not available - will use selected template for generation")

            if st.form_submit_button("Next: Select Index Page"):
                st.session_state.proposal_data["cover_template"] = output_pdf
                st.session_state.proposal_form_step = 3
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # Step 3: Select Index Page Template
    elif st.session_state.proposal_form_step == 3:
        st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 2))

        with st.form("proposal_form_step3"):
            st.subheader("Select Index Page Template")

            index_options = {
                "Detailed": "index_type_1.pdf",
                "Simple": "index_type_1.pdf",
                "Tabular": "index_type_1.pdf"
            }

            selected_index = st.radio(
                "Choose an index page style:",
                list(index_options.keys()),
                horizontal=True
            )

            # Show preview of selected index with error handling
            try:
                import pdfplumber
                with pdfplumber.open(index_options[selected_index]) as pdf:
                    preview_page = pdf.pages[0]
                    st.image(preview_page.to_image(resolution=150).original, caption="PDF Preview")
            except:
                st.warning("PDF preview not available - will use selected template for generation")

            # Form submit button
            if st.form_submit_button("Next: Select Content Sections"):
                st.session_state.proposal_data["index_template"] = index_options[selected_index]
                st.session_state.proposal_form_step = 4
                st.experimental_rerun() if LOAD_LOCALLY else st.rerun()

    # # Step 4: Select Content Sections
    # elif st.session_state.proposal_form_step == 4:
    #     st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 3))
    #
    #     with st.form("proposal_form_step4"):
    #         st.subheader("Select Proposal Sections")
    #
    #         section_options = {
    #             "Executive Summary": True,
    #             "Project Scope": True,
    #             "Methodology": True,
    #             "Timeline": True,
    #             "Deliverables": True,
    #             "Pricing": True,
    #             "Terms & Conditions": True,
    #             "About Us": False,
    #             "Case Studies": False,
    #             "Testimonials": False
    #         }
    #
    #         st.write("Select which sections to include in your proposal:")
    #         selected_sections = {}
    #
    #         for section, default in section_options.items():
    #             selected_sections[section] = st.checkbox(section, value=default)
    #
    #         # Special handling for pricing section
    #         if selected_sections["Pricing"]:
    #             pricing_type = st.radio("Pricing Format:", ["Itemized", "Package", "Hourly Rate"])
    #             st.session_state.proposal_data["pricing_type"] = pricing_type
    #
    #         st.session_state.proposal_data["sections"] = selected_sections
    #
    #         if st.form_submit_button("Next: Preview & Generate"):
    #             st.session_state.proposal_form_step = 5
    #             st.experimental_rerun()
    #
    # # Step 5: Preview and Generate
    # elif st.session_state.proposal_form_step == 5:
    #     st.button("← Back", on_click=lambda: setattr(st.session_state, 'proposal_form_step', 4))
    #     st.success("Proposal generated successfully!")
    #
    #     # Display preview information
    #     st.subheader("Proposal Preview")
    #     col1, col2 = st.columns(2)
    #
    #     with col1:
    #         st.write("**Client Information**")
    #         st.write(f"Name: {st.session_state.proposal_data['client_name']}")
    #         st.write(f"Company: {st.session_state.proposal_data['company_name']}")
    #         st.write(f"Email: {st.session_state.proposal_data['email']}")
    #         st.write(f"Phone: {st.session_state.proposal_data['phone']}")
    #
    #     with col2:
    #         st.write("**Project Details**")
    #         st.write(f"Project: {st.session_state.proposal_data['project_name']}")
    #         st.write(f"Date: {st.session_state.proposal_data['proposal_date']}")
    #         st.write(f"Valid Until: {st.session_state.proposal_data['valid_until']}")
    #
    #     st.write("\n**Selected Sections:**")
    #     for section, included in st.session_state.proposal_data["sections"].items():
    #         if included:
    #             st.write(f"- {section}")
    #
    #     # Generate documents
    #     replacements = {
    #         "_ClientName_": st.session_state.proposal_data["client_name"],
    #         "_CompanyName_": st.session_state.proposal_data["company_name"],
    #         "_ProjectName_": st.session_state.proposal_data["project_name"],
    #         "_Date_": st.session_state.proposal_data["proposal_date"],
    #         "_ValidUntil_": st.session_state.proposal_data["valid_until"],
    #         "_Email_": st.session_state.proposal_data["email"],
    #         "_Phone_": st.session_state.proposal_data["phone"]
    #     }
    #
    #     # Generate temporary files
    #     pdf_output = "temp_proposal.pdf"
    #     docx_output = "temp_proposal.docx"
    #
    #     # In a real implementation, you would combine all selected templates here
    #     # This is a simplified version
    #     fill_pdf_template("Proposal_Template.pdf", pdf_output, replacements, 11)
    #     replace_docx_placeholders("Proposal_Template.docx", docx_output, replacements)
    #
    #     # Download buttons
    #     st.subheader("Download Documents")
    #     col1, col2 = st.columns(2)
    #
    #     # Check if files exist before trying to open them
    #     pdf_exists = os.path.exists(pdf_output) if pdf_output else False
    #     docx_exists = os.path.exists(docx_output) if docx_output else False
    #
    #     with col1:
    #         if pdf_exists:
    #             with open(pdf_output, "rb") as f_pdf:
    #                 st.download_button(
    #                     "⬇️ Download PDF",
    #                     f_pdf,
    #                     file_name=f"Proposal_{st.session_state.proposal_data['project_name']}.pdf",
    #                     mime="application/pdf"
    #                 )
    #         else:
    #             st.warning("PDF file not available for download")
    #
    #     with col2:
    #         if docx_exists:
    #             with open(docx_output, "rb") as f_docx:
    #                 st.download_button(
    #                     "⬇️ Download DOCX",
    #                     f_docx,
    #                     file_name=f"Proposal_{st.session_state.proposal_data['project_name']}.docx",
    #                     mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    #                 )
    #         else:
    #             st.warning("DOCX file not available for download")
    #
    #     # Clean up temp files
    #     try:
    #         os.remove(pdf_output)
    #         os.remove(docx_output)
    #     except:
    #         pass
