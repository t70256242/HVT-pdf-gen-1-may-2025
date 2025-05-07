from docxtpl import DocxTemplate


def nda_edit(input_path, output_path, context):
    # Load the template
    doc = DocxTemplate(input_path)
    # Render the template
    doc.render(context)

    # Save the filled document
    doc.save(output_path)

    print(f"{output_path} has been created!")


# context = {
#     "date": "April 29, 2025",
#     "name": "Ojo Alaba",
#     "client_company_name": "Yoruba Ltd",
#     "client_phone": "+1 234 56000",
#     "client_address": "Lead Developer Street, Anthony, Riyah Turkey",
#     "client_email": "unfresh@email.com",
#     "project_name": "Tolu Scrapper",
#     "invoice_no": "#45678",
#     # "contract_end": "April 29, 2026",
# }
#
# nda_edit("invoice_1.docx", "wowo_3.docx", context)

