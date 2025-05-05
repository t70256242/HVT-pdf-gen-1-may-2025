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
#     "client_company_name": "Ojo Alaba",
#     "client_address": "Lead Developer Street",
#     "contract_end": "April 29, 2026",
# }
#
# nda_edit("contract_template.docx", "wowo_2.docx", context)

