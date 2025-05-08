from docxtpl import DocxTemplate


def nda_edit(input_path, output_path, context):
    # Load the template
    doc = DocxTemplate(input_path)
    # Render the template
    doc.render(context)

    # Save the filled document
    doc.save(output_path)

    print(f"{output_path} has been created!")


