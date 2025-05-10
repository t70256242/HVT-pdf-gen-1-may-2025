from docxtpl import DocxTemplate


def nda_edit(input_path, output_path, context):
    # Load the template
    doc = DocxTemplate(input_path)
    # Render the template
    doc.render(context)

    # Save the filled document
    doc.save(output_path)

    print(f"{output_path} has been created!")



# replacements_docx = {
#                 "date": "22-3-1290",
#                 "client_name": "       Diddy",
#                 "client_company_name": "DAVE",
#                 "client_company_address": "Ajalejo Street"
#             }
# nda_edit("penny_pig_2.docx", "wowo_8.docx", replacements_docx)

