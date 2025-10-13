from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.lib.pagesizes import letter
from django.conf import settings
from reportlab.lib.colors import HexColor
from bs4 import BeautifulSoup
import os
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from datetime import datetime
import matplotlib
matplotlib.use("Agg")  # Use a non-GUI backend
from reportlab.lib.utils import simpleSplit, ImageReader
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # This removes the limit entirely
from .models import saved_data_cargo_and_tank
import base64
from reportlab.lib import colors
from reportlab.lib.units import inch
import re
from scipy.interpolate import make_interp_spline
import matplotlib.pyplot as plt
import numpy as np
import json
from Intact_Stability.lifting_report import summary_html_from_json, tank_html_from_json, cargo_html_from_json, draw_tank_table, draw_empty_table

# Constants for layout
left_margin = 110
top_margin = 70
right_margin = 110
bottom_margin = 60
cell_height = 20
page_width, page_height = letter
header_height = 20
footer_height = 20


# Function to draw a table from HTML content
def draw_table(
    soup,
    y_position,
    canvas,
    doc_number,
    project_name,
    first_column_width,
    second_column_width=None,
    third_column_width=None,
    fourth_column_width=None,
    fifth_column_width=None,
    sixth_column_width=None,
    seventh_column_width=None,
    eighth_column_width=None,
    use_special_header_color=True,
    cell_height=20,
    left_align_first_column=False,
):

    global page_width, page_height, top_margin, bottom_margin, left_margin, footer_height, header_height
    header_color = (
        HexColor("#8BE1FF") if use_special_header_color else HexColor("#FFFFFF")
    )
    delete_column_index = None

    for index, row in enumerate(soup.find_all("tr")):
        if y_position < bottom_margin + footer_height + cell_height:
            canvas.showPage()
            add_header_footer(canvas, doc_number, project_name=project_name)
            y_position = page_height - top_margin - header_height - cell_height

        x_position = left_margin
        columns = row.find_all(["td", "th"])
        if index == 0:
            delete_column_index = next(
                (
                    i
                    for i, x in enumerate(columns)
                    if x.get_text(strip=True).upper() == "DELETE"
                ),
                None,
            )
        if delete_column_index is not None and len(columns) > delete_column_index:
            columns.pop(delete_column_index)

        if delete_column_index is not None and len(columns) > delete_column_index:
            columns.pop(delete_column_index)
        if columns and columns[-1].get_text(strip=True).upper() == "DELETE":
            columns.pop()

        for cell_index, cell in enumerate(columns):
            text = cell.get_text(strip=True)

            # Updated cell width calculation with fourth_column_width
            if cell_index == 0:
                cell_width = first_column_width
            elif cell_index == 1 and second_column_width is not None:
                cell_width = second_column_width
            elif cell_index == 2 and third_column_width is not None:
                cell_width = third_column_width
            elif cell_index == 3 and fourth_column_width is not None:
                cell_width = fourth_column_width
            elif cell_index == 4 and fifth_column_width is not None:
                cell_width = fifth_column_width
            elif cell_index == 5 and sixth_column_width is not None:
                cell_width = sixth_column_width
            elif cell_index == 6 and seventh_column_width is not None:
                cell_width = seventh_column_width
            elif cell_index == 7 and eighth_column_width is not None:
                cell_width = eighth_column_width
            else:
                remaining_columns = len(columns) - 1
                total_fixed_width = first_column_width
                if second_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += second_column_width
                if third_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += third_column_width
                if fourth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += fourth_column_width
                if fifth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += fifth_column_width
                if sixth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += sixth_column_width
                if seventh_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += seventh_column_width
                if eighth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += eighth_column_width

                cell_width = (
                    page_width - left_margin - right_margin - total_fixed_width
                ) / remaining_columns

            if index == 0:
                canvas.setFont("Helvetica-Bold", 9)
                canvas.setFillColor(header_color)
                canvas.rect(
                    x_position, y_position, cell_width, cell_height, stroke=1, fill=1
                )
                canvas.setFillColor(HexColor("#000000"))
            else:
                canvas.setFont("Helvetica", 9)
                canvas.setFillColor(HexColor("#000000"))
                canvas.rect(
                    x_position, y_position, cell_width, cell_height, stroke=1, fill=0
                )

            lines = simpleSplit(text, "Helvetica", 9, cell_width)
            text_y_position = y_position + (cell_height - 10 * len(lines)) / 2

            for line_index, line in enumerate(lines):
                line_x_position = x_position + 10  # Left-align text with padding
                canvas.drawString(
                    line_x_position,
                    text_y_position + (10 * (len(lines) - line_index - 1)),
                    line,
                )

            x_position += cell_width

        y_position -= cell_height

    return y_position


# def draw_tank_table(
#     soup,
#     y_position,
#     canvas,
#     doc_number,
#     project_name,
#     first_column_width,
#     second_column_width=None,
#     third_column_width=None,
#     fourth_column_width=None,
#     fifth_column_width=None,
#     sixth_column_width=None,
#     seventh_column_width=None,
#     eighth_column_width=None,
#     cell_height=20,
#     header_cell_height=30,
# ):

#     global page_width, page_height, top_margin, bottom_margin, left_margin, footer_height, header_height
#     header_color = HexColor("#8BE1FF")

#     for index, row in enumerate(soup.find_all("tr")):
#         current_cell_height = header_cell_height if index == 0 else cell_height

#         if y_position < bottom_margin + footer_height + current_cell_height:
#             canvas.showPage()
#             add_header_footer(canvas, doc_number, project_name=project_name)
#             y_position = page_height - top_margin - header_height - current_cell_height

#         x_position = left_margin
#         columns = row.find_all(["td", "th"])

#         for cell_index, cell in enumerate(columns):
#             text = cell.get_text(strip=True)

#             if cell_index == 0:
#                 cell_width = first_column_width
#             elif cell_index == 1 and second_column_width is not None:
#                 cell_width = second_column_width
#             elif cell_index == 2 and third_column_width is not None:
#                 cell_width = third_column_width
#             elif cell_index == 3 and fourth_column_width is not None:
#                 cell_width = fourth_column_width
#             elif cell_index == 4 and fifth_column_width is not None:
#                 cell_width = fifth_column_width
#             elif cell_index == 5 and sixth_column_width is not None:
#                 cell_width = sixth_column_width
#             elif cell_index == 6 and seventh_column_width is not None:
#                 cell_width = seventh_column_width
#             elif cell_index == 7 and eighth_column_width is not None:
#                 cell_width = eighth_column_width
#             else:
#                 remaining_columns = len(columns) - 1
#                 total_fixed_width = sum(
#                     filter(
#                         None,
#                         [
#                             first_column_width,
#                             second_column_width,
#                             third_column_width,
#                             fourth_column_width,
#                             fifth_column_width,
#                             sixth_column_width,
#                             seventh_column_width,
#                             eighth_column_width,
#                         ],
#                     )
#                 )
#                 cell_width = (
#                     page_width - left_margin - right_margin - total_fixed_width
#                 ) / remaining_columns

#             if index == 0:
#                 canvas.setFont("Helvetica-Bold", 9)
#                 canvas.setFillColor(header_color)
#                 canvas.rect(
#                     x_position,
#                     y_position,
#                     cell_width,
#                     header_cell_height,
#                     stroke=1,
#                     fill=1,
#                 )
#                 canvas.setFillColor(HexColor("#000000"))
#             else:
#                 canvas.setFont("Helvetica", 9)
#                 canvas.setFillColor(HexColor("#000000"))
#                 canvas.rect(
#                     x_position, y_position, cell_width, cell_height, stroke=1, fill=0
#                 )

#             lines = simpleSplit(text, "Helvetica", 9, cell_width)
#             text_y_position = y_position + (current_cell_height - 10 * len(lines)) / 2

#             for line_index, line in enumerate(lines):
#                 line_x_position = x_position + 10
#                 canvas.drawString(
#                     line_x_position,
#                     text_y_position + (10 * (len(lines) - line_index - 1)),
#                     line,
#                 )

#             x_position += cell_width

#         # Apply special fix **only for this function**
#         if index == 0:
#             y_position -= header_cell_height
#             y_position += cell_height / 2  # Corrects the extra space
#         else:
#             y_position -= cell_height

#     return y_position


# def draw_empty_table(
#     soup,
#     y_position,
#     canvas,
#     doc_number,
#     project_name,
#     first_column_width,
#     second_column_width=None,
#     third_column_width=None,
#     fourth_column_width=None,
#     fifth_column_width=None,
#     sixth_column_width=None,
#     seventh_column_width=None,
#     eighth_column_width=None,
#     cell_height=20,
#     header_cell_height=30,
# ):

#     global page_width, page_height, top_margin, bottom_margin, left_margin, footer_height, header_height
#     header_color = HexColor("#8BE1FF")

#     table_rows = soup.find_all("tr")

#     # Check if there's any data row (excluding header)
#     if len(table_rows) <= 1:  # Only header row exists or table is empty
#         empty_row_html = "<tr>" + "".join(["<td>-</td>" for _ in range(8)]) + "</tr>"
#         soup.table.append(BeautifulSoup(empty_row_html, "html.parser"))

#     for index, row in enumerate(soup.find_all("tr")):
#         current_cell_height = header_cell_height if index == 0 else cell_height

#         if y_position < bottom_margin + footer_height + current_cell_height:
#             canvas.showPage()
#             add_header_footer(canvas, doc_number, project_name=project_name)
#             y_position = page_height - top_margin - header_height - current_cell_height

#         x_position = left_margin
#         columns = row.find_all(["td", "th"])

#         for cell_index, cell in enumerate(columns):
#             text = cell.get_text(strip=True)

#             if cell_index == 0:
#                 cell_width = first_column_width
#             elif cell_index == 1 and second_column_width is not None:
#                 cell_width = second_column_width
#             elif cell_index == 2 and third_column_width is not None:
#                 cell_width = third_column_width
#             elif cell_index == 3 and fourth_column_width is not None:
#                 cell_width = fourth_column_width
#             elif cell_index == 4 and fifth_column_width is not None:
#                 cell_width = fifth_column_width
#             elif cell_index == 5 and sixth_column_width is not None:
#                 cell_width = sixth_column_width
#             elif cell_index == 6 and seventh_column_width is not None:
#                 cell_width = seventh_column_width
#             elif cell_index == 7 and eighth_column_width is not None:
#                 cell_width = eighth_column_width
#             else:
#                 remaining_columns = len(columns) - 1
#                 total_fixed_width = sum(
#                     filter(
#                         None,
#                         [
#                             first_column_width,
#                             second_column_width,
#                             third_column_width,
#                             fourth_column_width,
#                             fifth_column_width,
#                             sixth_column_width,
#                             seventh_column_width,
#                             eighth_column_width,
#                         ],
#                     )
#                 )
#                 cell_width = (
#                     page_width - left_margin - right_margin - total_fixed_width
#                 ) / remaining_columns

#             if index == 0:
#                 canvas.setFont("Helvetica-Bold", 9)
#                 canvas.setFillColor(header_color)
#                 canvas.rect(
#                     x_position,
#                     y_position,
#                     cell_width,
#                     header_cell_height,
#                     stroke=1,
#                     fill=1,
#                 )
#                 canvas.setFillColor(HexColor("#000000"))
#             else:
#                 canvas.setFont("Helvetica", 9)
#                 canvas.setFillColor(HexColor("#000000"))
#                 canvas.rect(
#                     x_position, y_position, cell_width, cell_height, stroke=1, fill=0
#                 )

#             lines = simpleSplit(text, "Helvetica", 9, cell_width)
#             text_y_position = y_position + (current_cell_height - 10 * len(lines)) / 2

#             for line_index, line in enumerate(lines):
#                 line_x_position = x_position + 10
#                 canvas.drawString(
#                     line_x_position,
#                     text_y_position + (10 * (len(lines) - line_index - 1)),
#                     line,
#                 )

#             x_position += cell_width

#         if index == 0:
#             y_position -= header_cell_height
#             y_position += cell_height / 2
#         else:
#             y_position -= cell_height

#     return y_position


def draw_table_with_subscripts(
    soup,
    y_position,
    canvas,
    doc_number,
    project_name,
    first_column_width,
    third_column_width=None,
    fifth_column_width=None,
    fourth_column_width=None,
    use_special_header_color=True,
    second_column_width=None,
    cell_height=20,
    left_align_first_column=False,
):
    global page_width, page_height, top_margin, bottom_margin, left_margin, right_margin, footer_height, header_height

    header_color = (
        HexColor("#8BE1FF") if use_special_header_color else HexColor("#FFFFFF")
    )
    delete_column_index = None

    for index, row in enumerate(soup.find_all("tr")):
        if y_position < bottom_margin + footer_height + cell_height:
            canvas.showPage()
            add_header_footer(canvas, doc_number, project_name=project_name)
            y_position = page_height - top_margin - header_height - cell_height

        x_position = left_margin
        columns = row.find_all(["td", "th"])
        if index == 0:
            delete_column_index = next(
                (
                    i
                    for i, x in enumerate(columns)
                    if x.get_text(strip=True).upper() == "DELETE"
                ),
                None,
            )

        if delete_column_index is not None and len(columns) > delete_column_index:
            columns.pop(delete_column_index)
        if columns and columns[-1].get_text(strip=True).upper() == "DELETE":
            columns.pop()

        for cell_index, cell in enumerate(columns):
            text = cell.get_text(strip=True)

            # Extract and separate main text and subscript
            cell_content = str(cell)
            main_text = "".join(
                BeautifulSoup(
                    cell_content.replace("<sub>", "§").replace("</sub>", "§"),
                    "html.parser",
                ).findAll(text=True)
            )
            parts = re.split("§", main_text)

            # Updated cell width calculation with fourth_column_width
            if cell_index == 0:
                cell_width = first_column_width
            elif cell_index == 1 and second_column_width is not None:
                cell_width = second_column_width
            elif cell_index == 2 and third_column_width is not None:
                cell_width = third_column_width
            elif cell_index == 3 and fifth_column_width is not None:
                cell_width = fifth_column_width
            elif cell_index == 4 and fourth_column_width is not None:
                cell_width = fourth_column_width
            else:
                remaining_columns = len(columns) - 1
                total_fixed_width = first_column_width
                if second_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += second_column_width
                if third_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += third_column_width
                if fifth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += fifth_column_width
                if fourth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += fourth_column_width

                cell_width = (
                    page_width - left_margin - right_margin - total_fixed_width
                ) / remaining_columns

            if index == 0:
                canvas.setFont("Helvetica-Bold", 9)
                canvas.setFillColor(header_color)
                canvas.rect(
                    x_position, y_position, cell_width, cell_height, stroke=1, fill=1
                )
                canvas.setFillColor(HexColor("#000000"))
            else:
                canvas.setFont("Helvetica", 9)
                canvas.setFillColor(HexColor("#000000"))
                canvas.rect(
                    x_position, y_position, cell_width, cell_height, stroke=1, fill=0
                )

            # Centering and drawing the text with subscripts
            full_text = "".join(parts)
            font_name = "Helvetica-Bold" if cell.name == "th" else "Helvetica"
            text_x_position = x_position + 10
            for part_index, part in enumerate(parts):
                if part_index % 2 != 0:  # This is a subscript part
                    canvas.setFont("Helvetica", 6)
                    text_y_position = y_position + (cell_height - 6) / 2 - 3
                else:
                    canvas.setFont(font_name, 9)
                    text_y_position = y_position + (cell_height - 10) / 2

                canvas.drawString(text_x_position, text_y_position, part)
                text_x_position += canvas.stringWidth(
                    part, font_name, 6 if part_index % 2 != 0 else 9
                )

            x_position += cell_width

        y_position -= cell_height

    return y_position


def draw_table_with_colors(
    soup,
    y_position,
    canvas,
    doc_number,
    project_name,
    first_column_width,
    third_column_width=None,
    fifth_column_width=None,
    fourth_column_width=None,
    use_special_header_color=True,
    second_column_width=None,
    cell_height=20,
    left_align_first_column=False,
):
    global page_width, page_height, top_margin, bottom_margin, left_margin, right_margin, footer_height, header_height

    # Define color mappings for named colors
    named_colors = {
        "rgb(246, 102, 92)": HexColor("#FF0000"),
        "rgb(102, 195, 123)": HexColor("#008000"),
        "blue": HexColor("#0000FF"),
        "black": HexColor("#000000"),
        # Add more named colors as needed
    }

    header_color = (
        HexColor("#8BE1FF") if use_special_header_color else HexColor("#FFFFFF")
    )
    delete_column_index = None

    for index, row in enumerate(soup.find_all("tr")):
        if y_position < bottom_margin + footer_height + cell_height:
            canvas.showPage()
            add_header_footer(canvas, doc_number, project_name=project_name)
            y_position = page_height - top_margin - header_height - cell_height

        x_position = left_margin
        columns = row.find_all(["td", "th"])
        if index == 0:
            delete_column_index = next(
                (
                    i
                    for i, x in enumerate(columns)
                    if x.get_text(strip=True).upper() == "DELETE"
                ),
                None,
            )
        if delete_column_index is not None and len(columns) > delete_column_index:
            columns.pop(delete_column_index)

        if delete_column_index is not None and len(columns) > delete_column_index:
            columns.pop(delete_column_index)
        if columns and columns[-1].get_text(strip=True).upper() == "DELETE":
            columns.pop()

        for cell_index, cell in enumerate(columns):
            text = cell.get_text(strip=True)

            # Extract and separate main text and subscript
            cell_content = str(cell)
            main_text = "".join(
                BeautifulSoup(
                    cell_content.replace("<sub>", "§").replace("</sub>", "§"),
                    "html.parser",
                ).findAll(text=True)
            )
            parts = re.split("§", main_text)

            # Extract color from style attribute if present
            cell_color = HexColor("#000000")  # Default color is black
            if "style" in cell.attrs:
                style = cell.attrs["style"]
                if "color:" in style:
                    color_code = style.split("color:")[-1].strip().split(";")[0]
                    if color_code.startswith("#"):
                        cell_color = HexColor(color_code.strip())
                    else:
                        # Use named color mapping
                        cell_color = named_colors.get(
                            color_code.strip(), HexColor("#000000")
                        )

            cell_text = ""
            cell_parts = []
            for element in cell.children:
                if element.name == "span" and "style" in element.attrs:
                    style = element.attrs["style"]
                    if "color:" in style:
                        color_code = style.split("color:")[-1].strip().split(";")[0]
                        if color_code.startswith("#"):
                            span_color = HexColor(color_code.strip())
                        else:
                            # Use named color mapping
                            span_color = named_colors.get(
                                color_code.strip(), HexColor("#000000")
                            )
                    span_text = element.get_text(strip=True)
                    cell_parts.append((span_text, span_color))
                else:
                    text = element.get_text(strip=True)
                    cell_parts.append((text, cell_color))

            if not cell_parts:  # Fallback to handle cases where no parts were added
                cell_parts.append((text, cell_color))

            # Updated cell width calculation with fourth_column_width
            if cell_index == 0:
                cell_width = first_column_width
            elif cell_index == 1 and second_column_width is not None:
                cell_width = second_column_width
            elif cell_index == 2 and third_column_width is not None:
                cell_width = third_column_width
            elif cell_index == 3 and fifth_column_width is not None:
                cell_width = fifth_column_width
            elif cell_index == 4 and fourth_column_width is not None:
                cell_width = fourth_column_width
            else:
                remaining_columns = len(columns) - 1
                total_fixed_width = first_column_width
                if second_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += second_column_width
                if third_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += third_column_width
                if fifth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += fifth_column_width
                if fourth_column_width is not None:
                    remaining_columns -= 1
                    total_fixed_width += fourth_column_width

                cell_width = (
                    page_width - left_margin - right_margin - total_fixed_width
                ) / remaining_columns

            if index == 0:
                canvas.setFont("Helvetica-Bold", 9)
                canvas.setFillColor(header_color)
                canvas.rect(
                    x_position, y_position, cell_width, cell_height, stroke=1, fill=1
                )
                canvas.setFillColor(HexColor("#000000"))
            else:
                canvas.setFont("Helvetica", 9)
                canvas.setFillColor(cell_color)
                canvas.rect(
                    x_position, y_position, cell_width, cell_height, stroke=1, fill=0
                )

            text_x_position = x_position + 10
            text_y_position = y_position + (cell_height - 10) / 2
            for part_index, (part_text, part_color) in enumerate(cell_parts):
                if part_index % 2 != 0 and cell_index == 0:
                    canvas.setFont("Helvetica", 6)
                    text_y_position = y_position + (cell_height - 6) / 2 - 3
                else:
                    font_style = "Helvetica-Bold" if index == 0 else "Helvetica"
                    canvas.setFont(font_style, 9)
                    text_y_position = y_position + (cell_height - 10) / 2
                canvas.setFillColor(part_color)
                canvas.drawString(text_x_position, text_y_position, part_text)
                text_x_position += canvas.stringWidth(
                    part_text,
                    font_style,
                    6 if (part_index % 2 != 0 and cell_index == 0) else 9,
                )

            x_position += cell_width

        y_position -= cell_height

    return y_position


def draw_abbreviations_table(p, y_position, left_margin, doc_number, project_name, abbreviations):
    black = HexColor("#000000")
    odd_bg = HexColor("#FAF9FA")
    even_bg = HexColor("#f4f2f3")

    font_size = 10
    first_column_width = 100
    second_column_width = page_width - 2 * left_margin - first_column_width
    row_height = 22

    p.setFont("Helvetica", font_size)

    subscripts = {
        "ECCX": ("ECC", "X"),
        "ECCY": ("ECC", "Y"),
    }

    # Loop with index for alternate coloring
    for index, (abbreviation, description) in enumerate(abbreviations.items()):
        y_position = check_space_and_add_new_page(y_position, row_height, p, doc_number, project_name=project_name)

        # Alternate background color
        bg_color = odd_bg if index % 2 == 0 else even_bg
        p.setFillColor(bg_color)
        p.rect(left_margin, y_position - row_height, first_column_width + second_column_width, row_height, fill=1, stroke=0)

        # Text color
        p.setFillColor(black)

        # Abbreviation (with subscript if applicable)
        if abbreviation in subscripts:
            main, sub = subscripts[abbreviation]
            p.setFont("Helvetica", font_size)
            p.drawString(left_margin + 10, y_position - row_height + 7, main)
            p.setFont("Helvetica", font_size - 2)
            p.drawString(
                left_margin + 10 + p.stringWidth(main, "Helvetica", font_size),
                y_position - row_height + 5,
                sub
            )
            p.setFont("Helvetica", font_size)
        else:
            p.setFont("Helvetica", font_size)
            p.drawString(left_margin + 10, y_position - row_height + 7, abbreviation)

        # Description
        p.drawString(left_margin + first_column_width + 10, y_position - row_height + 7, description)

        y_position -= row_height

    return y_position

def draw_text(
    p,
    text,
    x,
    y,
    font="Helvetica-Bold",
    font_size=12,
    color=colors.black,
    is_number=False,
    outside_margin=False,
):
    p.setFont(font, font_size)
    p.setFillColor(color)
    if outside_margin:
        p.drawString(x - 40, y, text)  # Position the number outside the margin
    else:
        p.drawString(x, y, text)


total_pages = 0

def add_header_footer(
    canvas,
    doc_number,
    title="",
    project_name="",
    include_title_and_number=True,
):
    global total_pages, page_width, page_height, top_margin, bottom_margin, left_margin, right_margin
    canvas.saveState()
    bg_image_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_dot_image.png")
    if os.path.exists(bg_image_path):
        canvas.drawImage(
            bg_image_path,
            0,
            0,
            width=page_width,
            height=page_height,
            preserveAspectRatio=False,  # Force full stretch
            mask='auto'
        )
    
    pg_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_number.png")
    if os.path.exists(pg_path):
        canvas.drawImage(
            pg_path,
            550,
            page_height - 35,
            width=23,
            height=50,
            mask="auto"
        )
        
    # Only draw page number
    if include_title_and_number:
        # Set font to Helvetica (regular)
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(HexColor("#000000"))
        
        # Adjust right margin based on page number
        page_num = canvas.getPageNumber()
        right_offset = 47.5 if page_num < 10 else 45

        canvas.drawRightString(
            page_width - right_offset,
            page_height - top_margin + 50,
            f"{page_num}"
        )

    # Draw the image on every page
    logo_path = os.path.join(settings.BASE_DIR, "static", "img", "fusie.png")
    if os.path.exists(logo_path):
        canvas.drawImage(
            logo_path,
            260,
            page_height - 40,
            width=90,
            height=30,
            mask="auto"
        )
    
    canvas.restoreState()

# Helper function to check space before adding content
def check_space_and_add_new_page(
    y_position,
    needed_space,
    canvas,
    doc_number,
    project_name="",
    table_height_estimate=0,
    header_height=30,
):
    global bottom_margin, footer_height, page_height, top_margin
    # Include header height in the total required space
    total_needed_space = needed_space + table_height_estimate + header_height
    if y_position - total_needed_space < bottom_margin + footer_height:
        add_new_page(canvas, doc_number, project_name=project_name)
        # Reset y_position to the start of a new page
        return page_height - top_margin - header_height
    return y_position


def draw_cover_page(p, post_data, project_name, doc_number, report_data):
    # Pass False to exclude title and page number on the cover page
    # add_header_footer(p, doc_number,include_title_and_number=False, project_name=project_name)
    p.setFont("Helvetica-Bold", 12)

    y_position = 480
    left_margin = 200

    if report_data:
        longest_label = max(len(label) for label in report_data.keys())

        # Iterate over report_data keys and values
        for key, value in report_data.items():
            y_position = check_space_and_add_new_page(
                y_position, 25, p, doc_number, project_name=project_name
            )
            padded_key = key.upper().ljust(longest_label)
            p.drawString(
                left_margin, y_position, f"{padded_key} : {str(value).upper()}"
            )
            y_position -= 25


# Function to add new page and footer
def add_new_page(canvas, doc_number, project_name="", first_page=False):
    global y_position, total_pages
    if not first_page:
        canvas.showPage()
    add_header_footer(canvas, doc_number, project_name=project_name)
    total_pages += 1  # Increment the total pages counter
    y_position = page_height - top_margin - header_height - cell_height


def draw_text1(c, text, font="Courier", font_size=18):
    text_width = c.stringWidth(text, font, font_size)
    x = (page_width - text_width) / 2  # Center the text horizontally
    y = (
        page_height - top_margin - header_height - font_size - 100
    )  # Position below the header line, adjusted further down

    c.setFont(font, font_size)
    c.drawString(x, y, text)


def draw_custom_table(c, labels, values, x, y, column_gap=10, box_width=250, box_height=80):
    c.saveState()

    # Layout: Two columns
    columns = 2
    row_height = box_height
    max_per_column = (len(labels) + 1) // columns

    for i, (label, value) in enumerate(zip(labels, values)):
        col = i % columns
        row = i // columns

        box_x = x + col * (box_width + column_gap)
        box_y = y - row * (row_height + 10)  # 10 points gap between rows

        # Draw box
        c.setFillColor(HexColor("#F9FEFF"))
        c.setStrokeColor(HexColor("#C1E6EA"))

        c.rect(box_x, box_y - row_height, box_width, row_height, fill=1, stroke=1)

        # Draw label (bold)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.black)
        c.drawString(box_x + 20, box_y - 35, label)

        # Draw value (regular)
        c.setFont("Helvetica", 12)
        c.drawString(box_x + 20, box_y - 55, str(value))

    c.restoreState()


def generate_cog_envelope_graph(squareX2, squareY2, leverCoordinates):
    from matplotlib import pyplot as plt
    from io import BytesIO
    from PIL import Image

    pointX = (
        leverCoordinates[0] if leverCoordinates and len(leverCoordinates) > 0 else 0
    )
    pointY = (
        leverCoordinates[1] if leverCoordinates and len(leverCoordinates) > 1 else 0
    )

    # Define the square bounds for COG envelope
    squareX = float(squareX2)
    squareY = float(squareY2)

    # Array of points to create a square-like shape based on squareX and squareY
    points = [
        {"x": squareX, "y": squareY},
        {"x": -squareX, "y": squareY},
        {"x": -squareX, "y": -squareY},
        {"x": squareX, "y": -squareY},
        {"x": squareX, "y": squareY},  # Closing the square
    ]

    square_x = [point["x"] for point in points]
    square_y = [point["y"] for point in points]

    # Create the figure
    fig, ax = plt.subplots(figsize=(6, 6))

    # Plot the square
    ax.plot(
        square_x,
        square_y,
        linestyle="--",
        marker="o",
        color="blue",
        label="COG Envelope",
    )

    # Plot the lever point (COG point)
    ax.plot(pointX, pointY, "ro", label="Lever Point")

    # Center axes in the middle of the graph
    ax.spines["left"].set_position("zero")
    ax.spines["left"].set_color("black")
    ax.spines["bottom"].set_position("zero")
    ax.spines["bottom"].set_color("black")

    # Hide top and right axes
    ax.spines["right"].set_color("none")
    ax.spines["top"].set_color("none")

    # Set the axis limits to ensure the square fits well
    maxAbsX = max(abs(squareX), abs(pointX)) + 5
    maxAbsY = max(abs(squareY), abs(pointY)) + 5
    ax.set_xlim([-maxAbsX, maxAbsX])
    ax.set_ylim([-maxAbsY, maxAbsY])

    # Show grid
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)

    # Reduce the font size of the axis tick labels
    ax.tick_params(axis="both", which="major", labelsize=6)

    # Save the plot to a buffer
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format="png", bbox_inches="tight")
    plt.close()

    # Rotate the image if needed and return the image data
    img_buffer.seek(0)
    img = Image.open(img_buffer)

    # Save the rotated image to buffer
    rotated_buffer = BytesIO()
    img.save(rotated_buffer, format="png")
    rotated_buffer.seek(0)

    return rotated_buffer.getvalue()


def add_image_to_pdf(canvas, img_data, x, y, max_width, max_height):
    img = Image.open(BytesIO(img_data))

    # Rotate the image 90 degrees clockwise
    img = img.rotate(-90, expand=True)  # Use -90 for clockwise rotation

    # Get new dimensions after rotation
    img_width, img_height = img.size
    aspect_ratio = img_width / img_height

    # Scale the image to fit within the max dimensions while maintaining aspect ratio
    if img_width > max_width:
        img_width = max_width
        img_height = max_width / aspect_ratio
    if img_height > max_height:
        img_height = max_height
        img_width = max_height * aspect_ratio

    # Draw the rotated and scaled image onto the PDF
    canvas.drawImage(
        ImageReader(img), x, y - img_height, width=img_width, height=img_height
    )


# Update headers with newline for text within parentheses to enhance readability
def format_headers(headers):
    formatted_headers = []
    for header in headers:
        if "(" in header and ")" in header:
            # Split the header at the parentheses and insert a newline
            main_text, parenthesis_text = header.split("(")
            formatted_header = f"{main_text.strip()} \n({parenthesis_text}"
            formatted_headers.append(formatted_header)
        else:
            formatted_headers.append(header)
    return formatted_headers

# Function to generate a graph from x and y values
def swl_graph(table_html, ra_value, swlreq_value):
    if not table_html:
        return None

    table = BeautifulSoup(table_html, "html.parser")
    x_values = []
    y_values = []

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            try:
                x = float(cells[0].get_text(strip=True))
                y = float(cells[1].get_text(strip=True))
                x_values.append(x)
                y_values.append(y)
            except ValueError:
                continue

    if not x_values or not y_values:
        return None

    # Sort for smooth interpolation
    sorted_indices = np.argsort(x_values)
    x_values = np.array([x_values[i] for i in sorted_indices])
    y_values = np.array([y_values[i] for i in sorted_indices])

    # Interpolation
    spline = make_interp_spline(x_values, y_values, k=3)
    x_smooth = np.linspace(x_values.min(), x_values.max(), 500)
    y_smooth = spline(x_smooth)

    # Plot
    img_buffer = BytesIO()
    plt.figure(figsize=(6, 4))
    plt.plot(x_smooth, y_smooth, label="SWL Curve", linewidth=1)

    # Plot the red point
    plt.scatter(ra_value, swlreq_value, color='red', s=50, zorder=5)

    # Labels
    plt.xlabel("Outreach (m)", fontsize=9)
    plt.ylabel("Safe Working Load (t)", fontsize=9)

    # Force axis to start at 0
    plt.xlim(left=0)
    plt.ylim(bottom=0)

    # Custom ticks
    x_max = max(x_values)
    y_max = max(y_values)
    plt.xticks(np.arange(0, x_max + 10, 10), fontsize=8)
    plt.yticks(np.arange(0, y_max + 20, 20), fontsize=8)

    # Grid and layout
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(img_buffer, format="png", bbox_inches="tight")
    plt.close()

    return img_buffer.getvalue()

def generate_pdf_jackup(request):
    global page_width, page_height, top_margin, bottom_margin, cell_height, new_y_position
    
    if request.method == "POST":
        name = request.POST.get("name")
        user_id = request.user.id
        pickle_name = request.POST.get("pickle_name")

        if not name or not user_id or not pickle_name:
            return JsonResponse(
                {"error": "Missing name or user ID or pickle name in request"}, status=400
            )
            
        buffer = BytesIO()
        toc_entries = []
        p = canvas.Canvas(buffer, pagesize=letter)
        page_width, page_height = letter  # Dimensions of the page
        margin = 1 * inch

        # Fetch the report data
        report_data = {}
        try:
            data_instance = saved_data_cargo_and_tank.objects.get(
                name=name, user_id=user_id, pickle_name=pickle_name
            )
            report_data = data_instance.report
        except saved_data_cargo_and_tank.DoesNotExist:
            report_data = {}

        # Load and position the logo image with adjustments
        logo_image_path = os.path.join(
            settings.BASE_DIR, "static", "img", "logo_pdf.png"
        )
        try:
            with open(logo_image_path, "rb") as image_file:
                logo_image = ImageReader(image_file)

                # Fixed dimensions for the logo
                fixed_logo_width = 113
                fixed_logo_height = 30

                # Adjust the logo position to be at the top-left corner
                logo_x = 40  # Place logo on the left edge
                logo_y = page_height - fixed_logo_height - 40  # Adjust vertical position above the text

                p.drawImage(
                    logo_image,
                    logo_x,
                    logo_y,
                    width=fixed_logo_width,
                    height=fixed_logo_height,
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")

        # Load and position the logo image with adjustments
        logo_image_path = os.path.join(
            settings.BASE_DIR, "static", "img", "marine_ops_pdf.webp"
        )
        try:
            with open(logo_image_path, "rb") as image_file:
                logo_image = ImageReader(image_file)

                # Fixed dimensions for the logo
                fixed_logo_width = 175
                fixed_logo_height = 35

                # Adjust the logo position to be at the top-left corner
                logo_x = 398  # Place logo on the left edge
                logo_y = page_height - fixed_logo_height - 40  # Adjust vertical position above the text

                p.drawImage(
                    logo_image,
                    logo_x,
                    logo_y,
                    width=fixed_logo_width,
                    height=fixed_logo_height,
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")
            
        # Extract project name
        project_name = report_data.get(
            "project_name", ""
        )  # Fallback if project name not found
        
        # Position of the project name and title
        project_name_y_position = (
            page_height - 180
        )  # Adjust as needed for space above the title
        title_y_position = (
            project_name_y_position - 33
        )  # Position title below project name
        
        text_y_position = (
            title_y_position - 33
        )  
        p.setFont("Helvetica-Bold", 30) 
        p.setFillColor(HexColor("#EC008C"))  
        p.drawString(40, project_name_y_position, project_name)  # Left-aligned

        # Draw the title
        p.setFont("Helvetica-Bold", 30)  
        p.setFillColor(HexColor("#000000"))  
        p.drawString(40, title_y_position, "JACKUP ANALYSIS") 
        p.drawString(40, text_y_position, "REPORT")
        
        
        # Set position for the line image (just below "REPORT")
        line_image_y_position = text_y_position - 30  # Adjust vertical position to be just below "REPORT"

        # Load and position the logo image (line image)
        logo_image_path = os.path.join(
            settings.BASE_DIR, "static", "img", "line.png"
        )
        try:
            with open(logo_image_path, "rb") as image_file:
                logo_image = ImageReader(image_file)

                # Fixed dimensions for the logo
                fixed_logo_width = 62
                fixed_logo_height = 3

                # Adjust the logo position to be just below the "REPORT" text
                logo_x = 40  # Place logo on the left edge
                logo_y = line_image_y_position  # Position the line just below the "REPORT" text

                p.drawImage(
                    logo_image,
                    logo_x,
                    logo_y,
                    width=fixed_logo_width,
                    height=fixed_logo_height,
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")
            
        dot_jpg_list = request.session.get("dot_jpg_list", [])
        image_y_position = page_height - 363  # adjust as needed

        for image_data in dot_jpg_list:
            for key, value in image_data.items():
                try:
                    # Decode the base64 string to bytes
                    image_bytes = base64.b64decode(value)
                    image = ImageReader(BytesIO(image_bytes))
                    # Adjust dimensions as needed, these are just placeholders
                    image_width = 140
                    image_height = 45

                    # To move the image towards the right, adjust the x position
                    right_margin = 400  # Adjust this value to move the image more or less to the right
                    image_x = (page_width - image_width) - right_margin

                    p.drawImage(
                        image,
                        image_x,
                        image_y_position,
                        width=image_width,
                        height=image_height,
                    )
                    image_y_position -= (
                        image_height + 20
                    )  # Move down for the next image
                except Exception as e:
                    print(f"Error loading image: {e}")

        # Load and place the image to cover the full page width and 55% of the page height
        image_path = os.path.join(settings.BASE_DIR, "static", "img", "cargo.webp")
        try:
            with open(image_path, "rb") as image_file:
                image = ImageReader(image_file)
                original_width, original_height = image.getSize()

                # Set desired dimensions to the full width of the page
                desired_width = page_width  # full page width
                desired_height = (
                    page_height * 0.45
                )  # 45% of the page height, adjust if different height is needed

                # Calculate scales based on width and height
                scale_width = desired_width / original_width
                scale_height = desired_height / original_height
                scale = max(
                    scale_width, scale_height
                )  # Ensuring the image covers the intended height

                # Apply scale
                image_width = original_width * scale
                image_height = original_height * scale

                # Calculate position to align the image top with the page top
                image_x = (page_width - image_width) / 2
                image_y = 0  # Align the top of the image with the top of the page

                p.drawImage(
                    image, image_x, image_y, width=image_width, height=image_height
                )
        except Exception as e:
            print(f"Error loading image: {e}")

        p.showPage()

        try:
            bg_image_path = os.path.join(settings.BASE_DIR, "static", "img", "cover_page_75%.png")
            if os.path.exists(bg_image_path):
                p.drawImage(
                    bg_image_path,
                    0,
                    0,
                    width=page_width,
                    height=page_height,
                    preserveAspectRatio=False,  # Force full stretch
                    mask='auto'
                )
        except Exception as e:
            print(f"Error applying background image: {e}")

        # Draw logo
        try:
            logo_path = os.path.join(settings.BASE_DIR, "static", "img", "fusie.png")
            if os.path.exists(logo_path):
                p.drawImage(
                    logo_path,
                    260,
                    page_height - 40,
                    width=90,
                    height=30,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")
            
        # Extract project name
        project_name = report_data.get(
            "project_name", ""
        )  # Fallback if project name not found
        
        # Position of the project name and title
        project_name_y_position = (
            page_height - 150
        )  # Adjust as needed for space above the title
        title_y_position = (
            project_name_y_position - 33
        )  # Position title below project name
        
        text_y_position = (
            title_y_position - 33
        )  
        p.setFont("Helvetica-Bold", 20) 
        p.setFillColor(HexColor("#EC008C"))  
        p.drawString(40, project_name_y_position, project_name)  # Left-aligned

        # Draw the title
        p.setFont("Helvetica-Bold", 20)  
        p.setFillColor(HexColor("#000000"))  
        p.drawString(40, title_y_position, "JACKUP ANALYSIS REPORT")

        # Reset the fill color to black or any other default color you need for the rest of the text
        p.setFillColor(HexColor("#000000"))  # Reset the color to black

        # Fetch the report data
        report_data = {}
        try:
            data_instance = saved_data_cargo_and_tank.objects.get(
                name=name, user_id=user_id, pickle_name=pickle_name
            )
            report_data = data_instance.report
            # Manually order the keys without "Document Number"
            ordered_report_details = {
                # "Document Number": report_data.get("Document Number", ""),  # Exclude this line
                # Include other necessary details here
            }
        except saved_data_cargo_and_tank.DoesNotExist:
            ordered_report_details = None

        doc_number = report_data.get("document_number", "")

        y_position = page_height - margin - 200
        
        x_position = 40
        y_offset = y_position + 5

        # Draw the bold label
        p.setFont("Helvetica-Bold", 14)
        p.drawString(x_position, y_offset, "DOCUMENT NUMBER : ")

        # Measure the width of the bold label to offset the regular part
        label_width = p.stringWidth("DOCUMENT NUMBER : ", "Helvetica-Bold", 14)

        # Draw the normal value after the label
        p.setFont("Helvetica", 14)
        p.drawString(x_position + label_width, y_offset, f"{doc_number}")
        
        # Draw the cover page with ordered data
        draw_cover_page(
            p, request.POST, project_name, report_data, ordered_report_details
        )
        
        project_name = report_data.get("document_title", "")

        labels = ["DOCUMENT", "DATE", "PROJECT TITLE", "PROJECT NO", "PREPARED", "CHECKED"]
        values = [
            report_data.get("document_title", ""),
            datetime.now().strftime("%d/%m/%Y"),
            report_data.get("project_name", ""),
            report_data.get("project_number", ""),
            report_data.get("prepared_by", ""),
            report_data.get("checked_by", ""),
        ]

        x_position = 40
        y_position = page_height - margin - 230  # Adjusted starting point
        draw_custom_table(p, labels, values, x_position, y_position)
        
        p.showPage()

        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        try:
            bg_image_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_dot_image.png")
            if os.path.exists(bg_image_path):
                p.drawImage(
                    bg_image_path,
                    0,
                    0,
                    width=page_width,
                    height=page_height,
                    preserveAspectRatio=False,  # Force full stretch
                    mask='auto'
                )
        except Exception as e:
            print(f"Error applying background image: {e}")
            
        # Draw logo
        try:
            logo_path = os.path.join(settings.BASE_DIR, "static", "img", "fusie.png")
            if os.path.exists(logo_path):
                p.drawImage(
                    logo_path,
                    260,
                    page_height - 40,
                    width=90,
                    height=30,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")
            
        # Draw pg no
        try:
            pg_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_number.png")
            if os.path.exists(pg_path):
                p.drawImage(
                    
                    pg_path,
                    550,
                    page_height - 35,
                    width=23,
                    height=50,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")

        # Draw page number only (bottom right corner)
        try:
            p.setFont("Helvetica", 10)
            p.setFillColor(HexColor("#000000"))
            p.drawRightString(
                page_width - 47.5,  # Right margin
                page_height - top_margin + 50,  # 30 points from bottom
                f"{p.getPageNumber()}"
            )
        except Exception as e:
            print(f"Error writing page number: {e}")

        # Initialize a page counter to simulate page numbers
        current_page_number = p.getPageNumber()

        sections = [
            ("1   Introduction ", report_data),
            ("     1.1   Abbreviations ", report_data),
            ("     1.2   Reference System ", report_data),
            ("2   Perspective Views ", report_data),
            ("     2.1   Top View ", report_data),
            ("     2.2   Front View ", report_data),
            ("     2.3   Side View ", report_data),
            ("     2.4   Tank Level Indicator ", report_data),
            ("3   Calculation And Results ", report_data),
            ("     3.1   Summary ", report_data),
            ("     3.2   Tank Data ", report_data),
            ("     3.3   Cargo Data ", report_data),
            ("     3.4   COG Envelope ", report_data),
            ("     3.5   SWL Graph ", report_data),
            ("     3.6   SWL Table ", report_data),
            ("     3.7   Leg Distribution ", report_data),
            ("     3.8   Boom & Lift Data ", report_data),
            ("     3.9   Jackup Data ", report_data),
            ("     3.10   Crane Parameters ", report_data),
            ("     3.11   Drilling Platform ", report_data),
        ]

        # Collect TOC entries with simulated page numbers
        for title, _ in sections:
            toc_entries.append((title, current_page_number))
            # Simulate a new page being needed for each section
            current_page_number += 1  # Increment page number for each section

        # Now render the Table of Contents
        draw_text(
            p,
            "TABLE OF CONTENTS",
            margin,
            page_height - margin - 40,
            font="Helvetica-Bold",
            font_size=14,
            color=HexColor("#2596be"),
        )

        y_position = page_height - margin - 70

        # Set positions for the text and page number
        text_position = margin
        page_number_position = margin + 435  # Position for page numbers

        for text, page_number in toc_entries:
            p.setFont("Helvetica", 12)  # Regular font for TOC entries

            # Calculate the width of the text
            text_width = p.stringWidth(text, "Helvetica", 12)

            # Calculate the number of dots
            dot_width = p.stringWidth(".", "Helvetica", 12)
            dots_needed = int(
                (page_number_position - (text_position + text_width)) / dot_width
            )
            dots = "." * dots_needed

            # Combine text and dots
            entry_with_dots = f"{text}{dots}"
            draw_text(
                p,
                entry_with_dots,
                text_position,
                y_position,
                font="Helvetica",
                font_size=12,
                color=colors.black,
            )
            draw_text(
                p,
                str(page_number),
                page_number_position,
                y_position,
                font="Helvetica",
                font_size=12,
                color=colors.black,
            )

            y_position -= 25
            if y_position < margin:
                add_new_page(p, doc_number=doc_no, project_name=project_name)
                y_position = page_height - margin - 70

        p.showPage()
        
        try:
            bg_image_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_dot_image.png")
            if os.path.exists(bg_image_path):
                p.drawImage(
                    bg_image_path,
                    0,
                    0,
                    width=page_width,
                    height=page_height,
                    preserveAspectRatio=False,  # Force full stretch
                    mask='auto'
                )
        except Exception as e:
            print(f"Error applying background image: {e}")

        # Set starting position below the header
        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )

        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )
        draw_text(
            p,
            "1",
            left_margin,
            y_position,
            color=colors.HexColor("#2596be"),
            outside_margin=True,
        )
        draw_text(
            p, "INTRODUCTION", left_margin, y_position, color=colors.HexColor("#2596be")
        )

        y_position = check_space_and_add_new_page(
            y_position, 20 + 10, p, doc_number=doc_no, project_name=project_name
        )
        draw_text(p, "1.1", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "ABBREVIATIONS", left_margin, y_position - 30)
        y_position -= 25
        y_position -= 10

        abbreviations = {
            "COG": "Center Of Gravity",
            "ECCX": "Eccentricity in the X-direction",
            "ECCY": "Eccentricity in the Y-direction",
            "EW": "Elevated weight",
            "LCG": "Longitudinal Center of Gravity",
            "TCG": "Transverse Center of Gravity",
            "VCG": "Vertical Center of Gravity",
        }
        y_position -= 10
        y_position = draw_abbreviations_table(
            p, y_position, left_margin, doc_no, project_name, abbreviations
        )
        p.showPage()

        # Set starting position below the header
        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )

        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )
        draw_text(p, "1.2", left_margin, y_position - 0, outside_margin=True)
        draw_text(p, "REFERENCE SYSTEM", left_margin, y_position - 0)
        y_position -= 5
        reference_system_text = """
        The vessel coordinate system is used as main reference grid (see Figure 1),unless 
        noted otherwise. The origin is located at the aft (APP or aft perpendicular), on the
        centreline and at keel level (or baseline), with:

        •   the X-axis (longitudinal) positive towards the bow;
        •   the Y-axis (transversal) positive to portside;
        •   the Z-axis (vertical) positive upwards.

        Following definitions are used for translations and rotations (right-handed system):

        •   surge motion, along X-axis and positive towards the bow;
        •   sway motion, along Y-axis and positive towards portside;
        •   heave motion, along Z-axis and positive upwards;
        •   roll motion, about the longitudinal axis (X-axis); starboard down positive
        •   pitch motion, about the transversal axis (Y-axis); bow down positive
        •   yaw motion, about the vertical axis (Z-axis); bow portside positive

        Headings are relative to the vessel system and usually defined as ‘coming from’."""

        # Draw the reference system details. Adjust text formatting as needed.
        p.setFont("Helvetica", 11)
        y_position -= 10  # Adjust spacing
        lines = reference_system_text.split("\n")
        for line in lines:
            p.drawString(left_margin, y_position, line.strip())
            y_position -= 15  # Line spacing

        # Load and display the reference system image
        image_path = os.path.join(
            settings.BASE_DIR, "static", "img", "reference_system_img.png"
        )
        try:
            with open(image_path, "rb") as image_file:
                image = ImageReader(image_file)
                image_width = 400  # Set the width of the image
                image_height = 250  # Set the height of the image
                y_position -= 10  # Additional space above the image
                p.drawImage(
                    image,
                    left_margin,
                    y_position - image_height,
                    width=image_width,
                    height=image_height,
                )
                y_position -= (
                    image_height  # Adjust y_position for text following the image
                )
        except Exception as e:
            print(f"Error loading image: {e}")

        # Draw the caption for the image
        caption_text = "Figure 1-1 Vessel reference system"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 10, caption_text)
        y_position -= 20

        p.showPage()

        # Set starting position below the header
        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )

        # Handle screenshots received in the POST request
        top_view_screenshot = request.POST.get("top_view_screenshot")
        side_view_screenshot = request.POST.get("side_view_screenshot")
        front_view_screenshot = request.POST.get("front_view_screenshot")

        # Decode the base64 images if they exist
        top_view_image = (
            ImageReader(BytesIO(base64.b64decode(top_view_screenshot.split(",")[1])))
            if top_view_screenshot
            else None
        )
        side_view_image = (
            ImageReader(BytesIO(base64.b64decode(side_view_screenshot.split(",")[1])))
            if side_view_screenshot
            else None
        )
        front_view_image = (
            ImageReader(BytesIO(base64.b64decode(front_view_screenshot.split(",")[1])))
            if front_view_screenshot
            else None
        )

        if top_view_image:
            y_position = check_space_and_add_new_page(
                y_position, 300, p, doc_number=doc_no, project_name=project_name
            )
            p.drawImage(top_view_image,
                0,
                0,
                width=page_width,
                height=page_height,
                preserveAspectRatio=False,  # Force full stretch
                mask='auto')
            y_position +=10  # Adjust the position after the image

        # Draw logo
        try:
            logo_path = os.path.join(settings.BASE_DIR, "static", "img", "fusie.png")
            if os.path.exists(logo_path):
                p.drawImage(
                    logo_path,
                    260,
                    page_height - 40,
                    width=90,
                    height=30,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")
            
        # Draw pg no
        try:
            pg_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_number.png")
            if os.path.exists(pg_path):
                p.drawImage(
                    pg_path,
                    550,
                    page_height - 35,
                    width=23,
                    height=50,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")

        # Draw page number only (bottom right corner)
        try:
            p.setFont("Helvetica", 10)
            p.setFillColor(HexColor("#000000"))
            p.drawRightString(
                page_width - 47.5,  # Right margin
                page_height - top_margin + 50,  # 30 points from bottom
                f"{p.getPageNumber()}"
            )
        except Exception as e:
            print(f"Error writing page number: {e}")
            
        draw_text(
            p,
            "2",
            left_margin,
            y_position,
            color=HexColor("#2596be"),
            outside_margin=True,
        )
        draw_text(
            p, "PERSPECTIVE VIEWS", left_margin, y_position, color=HexColor("#2596be")
        )

        # Top View
        y_position -= 30  # Adjust for the title spacing
        draw_text(p, "2.1", left_margin, y_position, outside_margin=True)
        draw_text(p, "TOP VIEW", left_margin, y_position)
        y_position -= 65  # Adjust space before the image

        # Add a new page for the next view
        p.showPage()
        
        # Set starting position below the header
        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )

        if side_view_image:
            y_position = check_space_and_add_new_page(
                y_position, 300, p, doc_number=doc_no, project_name=project_name
            )
            p.drawImage(side_view_image,
                0,
                0,
                width=page_width,
                height=page_height,
                preserveAspectRatio=False,  # Force full stretch
                mask='auto')
            y_position -= 30  # Adjust the position after the image

        # Draw logo
        try:
            logo_path = os.path.join(settings.BASE_DIR, "static", "img", "fusie.png")
            if os.path.exists(logo_path):
                p.drawImage(
                    logo_path,
                    260,
                    page_height - 40,
                    width=90,
                    height=30,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")
            
        # Draw pg no
        try:
            pg_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_number.png")
            if os.path.exists(pg_path):
                p.drawImage(
                    pg_path,
                    550,
                    page_height - 35,
                    width=23,
                    height=50,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")

        # Draw page number only (bottom right corner)
        try:
            p.setFont("Helvetica", 10)
            p.setFillColor(HexColor("#000000"))
            p.drawRightString(
                page_width - 47.5,  # Right margin
                page_height - top_margin + 50,  # 30 points from bottom
                f"{p.getPageNumber()}"
            )
        except Exception as e:
            print(f"Error writing page number: {e}")
        
        # Front View
        y_position = (
            page_height - top_margin - header_height - cell_height
        )  # Reset y_position for the new page
        draw_text(p, "2.2", left_margin, y_position, outside_margin=True)
        draw_text(p, "FRONT VIEW", left_margin, y_position)
        y_position -= 65  # Adjust space before the image

        # Add a new page for the next view
        p.showPage()
        
        # Set starting position below the header
        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )

        if front_view_image:
            y_position = check_space_and_add_new_page(
                y_position, 300, p, doc_number=doc_no, project_name=project_name
            )
            p.drawImage(front_view_image,
                0,
                0,
                width=page_width,
                height=page_height,
                preserveAspectRatio=False,  # Force full stretch
                mask='auto')
            y_position -= 30  # Adjust the position after the image

        # Draw logo
        try:
            logo_path = os.path.join(settings.BASE_DIR, "static", "img", "fusie.png")
            if os.path.exists(logo_path):
                p.drawImage(
                    logo_path,
                    260,
                    page_height - 40,
                    width=90,
                    height=30,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")
            
        # Draw pg no
        try:
            pg_path = os.path.join(settings.BASE_DIR, "static", "img", "blue_number.png")
            if os.path.exists(pg_path):
                p.drawImage(
                    pg_path,
                    550,
                    page_height - 35,
                    width=23,
                    height=50,
                    mask="auto"
                )
        except Exception as e:
            print(f"Error loading logo image: {e}")

        # Draw page number only (bottom right corner)
        try:
            p.setFont("Helvetica", 10)
            p.setFillColor(HexColor("#000000"))
            p.drawRightString(
                page_width - 47.5,  # Right margin
                page_height - top_margin + 50,  # 30 points from bottom
                f"{p.getPageNumber()}"
            )
        except Exception as e:
            print(f"Error writing page number: {e}")
            
        # Side View
        y_position = (
            page_height - top_margin - header_height - cell_height
        )  # Reset y_position for the new page
        draw_text(p, "2.3", left_margin, y_position, outside_margin=True)
        draw_text(p, "SIDE VIEW", left_margin, y_position)
        y_position -= 65  # Adjust space before the image

        # Add a new page for the next section
        p.showPage()

        # Set starting position below the header
        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )

        # Tank Layout
        y_position = (
            page_height - top_margin - header_height - cell_height
        )  # Reset y_position for the new page
        draw_text(p, "2.4", left_margin, y_position, outside_margin=True)
        draw_text(p, "TANK LEVEL INDICATOR", left_margin, y_position)
        y_position -= 30

        # Decode the DXF screenshot
        graphics_screenshot = request.POST.get("graphics_screenshot")
        if graphics_screenshot:
            try:
                base64_data = graphics_screenshot.split(",")[1]
                screenshot_image = base64.b64decode(base64_data)

                # Determine the maximum dimensions available for the image on the PDF page
                max_image_width = 570  # Assuming margins are defined
                max_image_height = (
                    570  # Example fixed height or calculate based on available space
                )

                # Add image to PDF dynamically
                add_image_to_pdf(
                    p,
                    screenshot_image,
                    200,
                    y_position,
                    max_image_width,
                    max_image_height,
                )
                y_position -= 300  # Adjust the position after the image
            except Exception as e:
                print(f"Error processing DXF screenshot: {e}")
        else:
            print("No DXF screenshot received.")

        # Add a new page for the next view
        p.showPage()
        # Set starting position below the header
        y_position = page_height - top_margin - header_height - cell_height
        doc_no = report_data.get("document_number", "")
        add_new_page(p, doc_number=doc_no, project_name=project_name, first_page=True)
        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )

        y_position = check_space_and_add_new_page(
            y_position, 30, p, doc_number=doc_no, project_name=project_name
        )
        draw_text(
            p,
            "3",
            left_margin,
            y_position,
            color=HexColor("#2596be"),
            outside_margin=True,
        )
        draw_text(
            p,
            "CALCULATION AND RESULTS",
            left_margin,
            y_position,
            color=HexColor("#2596be"),
        )

        y_position = check_space_and_add_new_page(
            y_position, 20 + 10, p, doc_number=doc_no, project_name=project_name
        )
        draw_text(p, "3.1", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "SUMMARY", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-1 Summary"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 25
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30 + cell_height,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        raw_data = request.POST.get("summary_data")
        if raw_data :
            try :
                summary_data = json.loads(raw_data)
                html_summary = summary_html_from_json(summary_data)
                soup = BeautifulSoup(html_summary, "html.parser")
                y_position = draw_table(
                    soup,
                    y_position - 30,
                    p,
                    first_column_width=100,
                    doc_number=doc_no,
                    project_name=project_name,
                )
            except json.JSONDecodeError:
                soup = BeautifulSoup(raw_data, "html.parser")
                y_position = draw_table(
                    soup,
                    y_position - 30,
                    p,
                    first_column_width=100,
                    doc_number=doc_no,
                    project_name=project_name,
                )

        estimated_table_height = cell_height * 5
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        draw_text(p, "3.2", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "TANK DATA", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-2 Tank Data"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 35
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30 + cell_height,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        raw_tank_data = request.POST.get("tank_data")
        if raw_tank_data :
            try :
                tank_data = json.loads(raw_tank_data)
                tank_data_html = tank_html_from_json(tank_data)
                soup = BeautifulSoup(tank_data_html, "html.parser")
                y_position = draw_tank_table(
                    soup,
                    y_position - 30,
                    p,
                    first_column_width=57,
                    second_column_width=45,
                    third_column_width=55,
                    fourth_column_width=55,
                    fifth_column_width=45,
                    sixth_column_width=45,
                    seventh_column_width=45,
                    eighth_column_width=45,
                    doc_number=doc_no,
                    project_name=project_name,
                )
            except json.JSONDecodeError:
                soup = BeautifulSoup(raw_tank_data, "html.parser")
                y_position = draw_tank_table(
                    soup,
                    y_position - 30,
                    p,
                    first_column_width=57,
                    second_column_width=45,
                    third_column_width=55,
                    fourth_column_width=55,
                    fifth_column_width=45,
                    sixth_column_width=45,
                    seventh_column_width=45,
                    eighth_column_width=45,
                    doc_number=doc_no,
                    project_name=project_name,
                )

        estimated_table_height = cell_height * 5
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        draw_text(p, "3.3", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "CARGO DATA", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-3 Cargo Data"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 35
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30 + cell_height,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        raw_cargo_data = request.POST.get("cargo_data")
        if raw_cargo_data :
            try :
                cargo_data = json.loads(raw_cargo_data)
                cargo_data_html = cargo_html_from_json(cargo_data)
                soup = BeautifulSoup(cargo_data_html, "html.parser")
                y_position = draw_empty_table(
                    soup,
                    y_position - 30,
                    p,
                    first_column_width=120,
                    second_column_width=50,
                    third_column_width=37,
                    fourth_column_width=37,
                    fifth_column_width=37,
                    sixth_column_width=37,
                    seventh_column_width=37,
                    eighth_column_width=37,
                    doc_number=doc_no,
                    project_name=project_name,
                )
            except json.JSONDecodeError:
                soup = BeautifulSoup(raw_cargo_data, "html.parser")
                y_position = draw_empty_table(
                    soup,
                    y_position - 30,
                    p,
                    first_column_width=120,
                    second_column_width=50,
                    third_column_width=37,
                    fourth_column_width=37,
                    fifth_column_width=37,
                    sixth_column_width=37,
                    seventh_column_width=37,
                    eighth_column_width=37,
                    doc_number=doc_no,
                    project_name=project_name,
                )

        graph_height = 300
        caption_height = 60
        space_needed_for_title_and_graph = caption_height + graph_height
        y_position = check_space_and_add_new_page(
            y_position,
            space_needed_for_title_and_graph,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        draw_text(p, "3.4", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "COG ENVELOPE", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Figure 3-1 COG Envelope"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= caption_height
        squareX2 = request.POST.get("squareX2", "10")  # Default values if not provided
        squareY2 = request.POST.get("squareY2", "10")  # Default values if not provided
        leverCoordinates = [
            float(x)
            for x in request.POST.get("leverCoordinates", "[0, 0]")
            .strip("[]")
            .split(",")
        ]
        # Generate the COG Envelope graph
        graph_image_data = generate_cog_envelope_graph(
            squareX2, squareY2, leverCoordinates
        )
        if graph_image_data:
            y_position -= graph_height
            img = Image.open(BytesIO(graph_image_data))
            p.drawInlineImage(
                img, left_margin - 24, y_position, width=465, height=graph_height
            )

        estimated_table_height = cell_height * 5
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        
        graph_height = 280
        caption_height = 60
        space_needed_for_title_and_graph = caption_height + graph_height
        y_position = check_space_and_add_new_page(
            y_position,
            space_needed_for_title_and_graph,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        draw_text(p, "3.5", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "SWL GRAPH", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Figure 3-2 SWL Graph"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 25
        y_position -= 30
        # Extract values BEFORE using them
        soup = BeautifulSoup(request.POST.get("crane_parameters_html"), "html.parser")
        ra_value = float(soup.find(id="Ra").text.strip())
        swlreq_value = float(soup.find(id="SWLreq").text.strip())

        # Now you can safely pass them into the graph generator
        table_html = request.POST.get("swl_graph_html")
        graph_image_data = swl_graph(table_html, ra_value, swlreq_value)

        if graph_image_data:
            y_position -= graph_height
            img = Image.open(BytesIO(graph_image_data))
            p.drawInlineImage(
                img, left_margin - 24, y_position, width=421, height=graph_height
            )

        estimated_table_height = cell_height * 5
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        
        draw_text(p, "3.6", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "SWL TABLE", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-4 SWL Table"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 25
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
            header_height=cell_height,
        )
        soup = BeautifulSoup(request.POST.get("swl_table_html"), "html.parser")
        y_position = draw_table(
            soup,
            y_position - 30,
            p,
            first_column_width=197,
            doc_number=doc_no,
            project_name=project_name,
        )
        estimated_table_height = cell_height * 5
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        
        draw_text(p, "3.7", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "LEG DISTRIBUTION", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-5 Leg Distribution"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 25
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30 + cell_height,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        soup = BeautifulSoup(request.POST.get("leg_table_html"), "html.parser")
        y_position = draw_table(
            soup,
            y_position - 30,
            p,
            first_column_width=197,
            doc_number=doc_no,
            project_name=project_name,
        )

        y_position -= 10
        estimated_table_height = cell_height * 5
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        draw_text(p, "3.8", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "BOOM & LIFT DATA", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-6 Boom & Lift Data"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 25
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30 + cell_height,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        soup = BeautifulSoup(request.POST.get("crane_table_html"), "html.parser")
        y_position = draw_table_with_colors(
            soup,
            y_position - 30,
            p,
            first_column_width=150,
            doc_number=doc_no,
            project_name=project_name,
        )

        estimated_table_height = cell_height * 5
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        draw_text(p, "3.9", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "JACKUP DATA", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-7 Jackup Data"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 25
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30 + cell_height,
            p,
            doc_number=doc_no,
            project_name=project_name,
        )
        soup = BeautifulSoup(request.POST.get("jackup_table_html"), "html.parser")
        y_position = draw_table_with_colors(
            soup,
            y_position - 30,
            p,
            first_column_width=217,
            doc_number=doc_no,
            project_name=project_name,
        )

        estimated_table_height = cell_height * (5 + 1)  # +1 for the header row
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )
        
        draw_text(p, "3.10", left_margin, y_position - 30, outside_margin=True)
        draw_text(p, "CRANE PARAMETERS", left_margin, y_position - 30)
        y_position -= 10
        caption_text = "Table 3-8 Crane Parameters"
        p.setFont("Helvetica-Oblique", 10)  # Set to italic
        p.drawString(left_margin, y_position - 50, caption_text)
        y_position -= 25
        y_position -= 30
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
            header_height=cell_height,
        )
        soup = BeautifulSoup(request.POST.get("crane_parameters_html"), "html.parser")
        y_position = draw_table_with_colors(
            soup,
            y_position - 30,
            p,
            first_column_width=197,
            doc_number=doc_no,
            project_name=project_name,
        )
        # Assuming 'soup' is the BeautifulSoup object containing the HTML
        ra_value = soup.find(id="Ra").text.strip()  # Extract Ra value
        swlreq_value = soup.find(id="SWLreq").text.strip()  # Extract SWLreq value

        # Convert to float for plotting
        ra_value = float(ra_value)
        swlreq_value = float(swlreq_value)
        
        estimated_table_height = cell_height * (5 + 1)  # +1 for the header row
        y_position = check_space_and_add_new_page(
            y_position,
            30,
            p,
            table_height_estimate=estimated_table_height,
            doc_number=doc_no,
            project_name=project_name,
        )

        if request.POST.get("drilling_table_html") :
        
            draw_text(p, "3.11", left_margin, y_position - 30, outside_margin=True)
            draw_text(p, "DRILLING PLATFORM", left_margin, y_position - 30)
            y_position -= 10
            caption_text = "Table 3-9 Drilling Platform"
            p.setFont("Helvetica-Oblique", 10)  # Set to italic
            p.drawString(left_margin, y_position - 50, caption_text)
            y_position -= 25
            y_position -= 30
            y_position = check_space_and_add_new_page(
                y_position,
                30,
                p,
                table_height_estimate=estimated_table_height,
                doc_number=doc_no,
                project_name=project_name,
                header_height=cell_height,
            )
            soup = BeautifulSoup(request.POST.get("drilling_table_html"), "html.parser")
            y_position = draw_table(
                soup,
                y_position - 30,
                p,
                first_column_width=197,
                doc_number=doc_no,
                project_name=project_name,
            )

        # Check y_position before drawing each section
        if y_position < bottom_margin + footer_height:
            add_new_page(p)
            y_position = page_height - top_margin - header_height - cell_height
        p.save()

        buffer.seek(0)
        pdf_bytes = buffer.read()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        response_data = {
            "pdf_base64": base64_pdf
        }

    return JsonResponse(response_data)

