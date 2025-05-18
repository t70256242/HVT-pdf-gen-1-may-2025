# import os
# import subprocess
# from docx import Document
# import fitz
#
#
# class EditTextFile:
#     def __init__(self, file_path):
#         self.file_path = file_path
#
#     def modify_pdf_fields(self, output_pdf, modifications, y_offset=0):
#         input_pdf = self.file_path
#
#         try:
#             if not os.path.exists(input_pdf):
#                 raise FileNotFoundError(f"Input PDF not found: {self.file_path}")
#
#             doc = fitz.open(self.file_path)
#             print(f"Processing {len(doc)} pages...")
#
#             for page_num, page in enumerate(doc):
#                 # print(f"\nAnalyzing page {page_num + 1}...")
#                 text_instances = page.get_text("words")
#
#                 if not text_instances:
#                     print("Warning: No text found on this page (may be scanned)")
#                     continue
#
#                 # print("Text elements found on page:")
#                 for inst in text_instances:
#                     print(".")
#
#                 for field, new_value in modifications.items():
#                     found = False
#                     variations = [
#                         field,
#                         field.replace(":", ""),
#                         field.replace(":", " :"),
#                         field.lower(),
#                         field.upper(),
#                         field.replace(" ", ""),
#                         field.replace(" ", "  ")
#                     ]
#
#                     for variation in variations:
#                         instances = page.search_for(variation)
#                         if instances:
#                             # print(f"Found potential match for '{variation}' on page {page_num + 1}")
#                             for inst in instances:
#                                 try:
#                                     if field == "Date":
#                                         # Search for "Date:" label on page
#                                         label_instances = page.search_for("Date")
#                                         if label_instances:
#                                             for label_rect in label_instances:
#                                                 # Define area BELOW "Date:" to redact and replace
#                                                 value_y_start = label_rect.y1 + 8  # Slight offset down
#                                                 value_rect = fitz.Rect(
#                                                     label_rect.x0 - 2,
#                                                     value_y_start,
#                                                     label_rect.x1 + 150,  # adjust width
#                                                     value_y_start + 28  # adjust height
#                                                 )
#
#                                                 # Redact the old date
#                                                 page.add_redact_annot(value_rect, fill=(1, 1, 1))
#                                                 page.apply_redactions()
#
#                                                 # Insert new date below the "Date:" label
#                                                 page.insert_text(
#                                                     (label_rect.x0, value_y_start + 14),
#                                                     new_value,
#                                                     fontsize=20,
#                                                     fontname="helv",
#                                                     color=(0, 0, 0)
#                                                 )
#
#                                                 found = True
#                                                 break
#
#                                     # if field == "14 April 2025":
#                                     #     # Redact and replace date field directly using rectangle
#                                     #     # Custom X position — adjust this as needed
#                                     #     custom_x = 45
#                                     #     custom_y = inst.y0 + (inst.y1 - inst.y0) / 2 + y_offset
#                                     #
#                                     #     # Redact original date region
#                                     #     date_area = fitz.Rect(
#                                     #         inst.x0 - 2,
#                                     #         inst.y0 - 2,
#                                     #         inst.x1 + 100,
#                                     #         inst.y1 + 2
#                                     #     )
#                                     #     page.add_redact_annot(date_area, fill=(1, 1, 1))
#                                     #     page.apply_redactions()
#                                     #
#                                     #     # Custom-positioned new date
#                                     #     page.insert_text(
#                                     #         (custom_x, custom_y),
#                                     #         new_value,
#                                     #         fontsize=23,
#                                     #         color=(0, 0, 0),
#                                     #         fontname="helv"
#                                     #     )
#
#                                     else:
#                                         value_area = fitz.Rect(
#                                             inst.x1,
#                                             inst.y0 - 2,
#                                             inst.x1 + 250,
#                                             inst.y1 + 2
#                                         )
#                                         page.add_redact_annot(value_area, fill=(1, 1, 1))
#                                         page.apply_redactions()
#
#                                         y_pos = inst.y0 + (inst.height / 2) + y_offset
#                                         page.insert_text(
#                                             (inst.x1 + 2, y_pos),
#                                             new_value,
#                                             fontsize=18,
#                                             color=(0, 0, 0),
#                                             fontname="helv"
#                                         )
#
#                                     found = True
#                                     # print(f"✅ Modified field: {field}")
#                                     break
#
#                                 except Exception as e:
#                                     print(f"❌ Error processing {field}: {str(e)}")
#                                     continue
#
#                             if found:
#                                 break
#
#                     if not found:
#                         print(f"⚠️ Warning: Field '{field}' not found on page {page_num + 1}")
#
#             if len(doc) > 0:
#                 doc.save(output_pdf)
#                 print(f"\n✅ Successfully saved modified PDF to {output_pdf}")
#             else:
#                 print("❌ Error: No pages processed - output not saved")
#
#         except Exception as e:
#             print(f"❌ Critical error: {str(e)}")
#         finally:
#             if 'doc' in locals():
#                 doc.close()
#
#
# modifications = {
#     "{ date }": "May 12, 2025",
#     "{ client_name }": ": Jane Doe",
#     "{ client_email }": ": jane@example.com",
#     "{ client_phone }": f": 22334433",
#     "{ country }": f": Nigeria",
# }
# editor = EditTextFile("cover.pdf")
# editor.modify_pdf_fields("cico_4.pdf", modifications, 8)


import os
import fitz  # PyMuPDF


# class EditTextFile:
#     def __init__(self, file_path):
#         self.file_path = file_path
#
#     def modify_pdf_fields(self, output_pdf, modifications, y_offset=0):
#         input_pdf = self.file_path
#
#         try:
#             if not os.path.exists(input_pdf):
#                 raise FileNotFoundError(f"Input PDF not found: {self.file_path}")
#
#             doc = fitz.open(self.file_path)
#             print(f"Processing {len(doc)} pages...")
#
#             for page_num, page in enumerate(doc):
#                 # First pass: Search for label-value pairs
#                 text_blocks = page.get_text("blocks")
#
#                 # Build a mapping of labels to their positions
#                 label_positions = {}
#                 for block in text_blocks:
#                     text = block[4].strip()
#                     if ":" in text:  # This is a label
#                         label = text.split(":")[0].strip()
#                         label_positions[label] = (block[0], block[1], block[2], block[3])
#
#                 for field, new_value in modifications.items():
#                     found = False
#                     clean_field = field.strip("{}").strip()
#
#                     # Try to find the label position
#                     if clean_field in label_positions:
#                         x0, y0, x1, y1 = label_positions[clean_field]
#
#                         try:
#                             # Calculate position to right of label
#                             insert_x = x1 + 10
#                             insert_y = y0 + (y1 - y0) / 2 + y_offset
#
#                             # Create redaction area (to right of label)
#                             redact_rect = fitz.Rect(
#                                 x1 + 5,
#                                 y0 - 2,
#                                 x1 + 150,  # Wide enough for most values
#                                 y1 + 2
#                             )
#
#                             page.add_redact_annot(redact_rect, fill=(1, 1, 1))
#                             page.apply_redactions()
#
#                             page.insert_text(
#                                 (insert_x, insert_y),
#                                 new_value,
#                                 fontsize=11,
#                                 fontname="helv",
#                                 color=(0, 0, 0)
#                             )
#
#                             found = True
#                             print(f"✅ Modified field: {clean_field}")
#
#                         except Exception as e:
#                             print(f"❌ Error processing {clean_field}: {str(e)}")
#                             continue
#
#                     if not found:
#                         print(f"⚠️ Warning: Field '{clean_field}' not found on page {page_num + 1}")
#
#             # Save with garbage collection to fix xref issues
#             doc.save(output_pdf, garbage=4, deflate=True)
#             print(f"\n✅ Successfully saved modified PDF to {output_pdf}")
#
#         except Exception as e:
#             print(f"❌ Critical error: {str(e)}")
#         finally:
#             if 'doc' in locals():
#                 doc.close()
#
#
# # Example usage with all fields from your PDF
# modifications = {
#     "{ date }": "May 12, 2025",
#     "{ client_name }": "Jane Doe",
#     "{ client_email }": "jane@example.com",
#     "{ client_phone }": "22334433",
#     "{ country }": "Nigeria",
# }
#
# editor = EditTextFile("cover.pdf")
# editor.modify_pdf_fields("cico_6.pdf", modifications, y_offset=0)
# Example usage
# modifications = {
#     "{ date }": "May 12, 2025",
#     "{client_name}": "Jane Doe",
#     "{client_email}": "jane@example.com",
#     "{client_phone}": "22334433",
#     "{country}": "Nigeria",
# }
#
# editor = EditTextFile("cover.pdf")
# editor.modify_pdf_fields("cico_5.pdf", modifications, y_offset=0)

import fitz  # PyMuPDF


def replace_pdf_placeholders(input_path, output_path, replacements, y_offset=0):

    doc = fitz.open(input_path)

    for page in doc:
        for placeholder, replacement in replacements.items():
            text_instances = page.search_for(placeholder)
            for inst in text_instances:
                # Draw a white rectangle over the old text
                page.draw_rect(inst, color=(1, 1, 1), fill=(1, 1, 1))
                # Insert new text with vertical offset
                new_position = fitz.Point(inst.x0, inst.y0 + y_offset)
                page.insert_text(new_position, replacement, fontsize=18, color=(0, 0, 0))

    doc.save(output_path)
    doc.close()
    print(f"Updated PDF saved to: {output_path}")


# replace_pdf_placeholders(
#     input_path="Cover_Page.pdf",
#     output_path="Cover_Page_Edited++++_5.pdf",
#     replacements={
#         "{ client_name }": "John Doe",
#         "{ client_email }": "john@example.com",
#         "{ client_phone }": "+1234567890",
#         "{ client_country }": "USA",
#         "{ date }": "2025-05-18"
#     },
#     y_offset=19
# )





