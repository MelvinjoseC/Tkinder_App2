"""
This module contains views and utility functions for handling cargo operations,
file uploads, session management, and database interactions in the application.

It includes functionalities for:
- Handling cargo creation, deletion, and updates.
- Managing user sessions.
- Solving stability calculations and jackup data handling.
"""

import base64
import json
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from django.http import (
    JsonResponse,
    QueryDict,
)
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import (
    Cargo,
    Pickle,
    saved_data_cargo_and_tank,
)


# Declare variables
namep = []
ship = None
tank_data = {}
cargo_data = {}
save_data = {}
selected_name = None
global_cargo_data = None
selected_name = None

# Intact_Stability/views.py
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404

def spa(request):
    index_path = Path(settings.BASE_DIR, "frontend_build", "index.html")
    if not index_path.exists():
        raise Http404("Frontend build not found. Run `npm run build` and copy it.")
    return FileResponse(open(index_path, "rb"))

@login_required(login_url="/")
@csrf_exempt
def index(request):
    """
    View function for the index page.

    GET: Retrieves all cargos belonging to the logged-in user
    and renders them in the index.html template.

    POST: Creates a new cargo with the given name. If a cargo with the same
    name already exists, appends a version number to the name to ensure
    uniqueness.

    DELETE: Deletes a cargo with the given name that belongs to the
    logged-in user.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - HttpResponse: Rendered index.html template with user's cargos (for GET).
    - JsonResponse: JSON response indicating success or failure
    (for POST and DELETE).
    """
    if request.method == "GET":
        # Serve the React single-page application bundled under frontend_build.
        return spa(request)

    # elif request.method == "POST":
    #     action = request.POST.get("action")
    #     cargo_name = request.POST.get("CARGO_NAME")

    #     if not cargo_name:
    #         return JsonResponse(
    #             {"success": False, "message": "Cargo name is required."}, status=400
    #         )

    #     if action == "undo_delete":
    #         new_cargo = Cargo.objects.create(CARGO_NAME=cargo_name, user=request.user)
    #         return JsonResponse(
    #             {"success": True, "message": "Cargo restored successfully."}
    #         )

    #     def generate_unique_name(original_name):
    #         """
    #         Generate a new unique cargo name by appending a version number
    #         to the original name.

    #         Parameters:
    #         - original_name (str): The original cargo name.

    #         Returns:
    #         - str: A new unique cargo name.
    #         """
    #         version = 1
    #         new_name = f"{original_name}{version}"
    #         while Cargo.objects.filter(CARGO_NAME=new_name, user=request.user).exists():
    #             version += 1
    #             new_name = f"{original_name}{version}"
    #         return new_name

    #     if Cargo.objects.filter(CARGO_NAME=cargo_name, user=request.user).exists():
    #         cargo_name = generate_unique_name(cargo_name)

    #     new_cargo = Cargo(CARGO_NAME=cargo_name, user=request.user)
    #     new_cargo.save()
    #     return JsonResponse({"success": True, "new_cargo_name": cargo_name})

    # elif request.method == "DELETE":
    #     data = QueryDict(request.body.decode("utf-8"))
    #     cargo_name = data.get("CARGO_NAME")

    #     if not cargo_name:
    #         return JsonResponse(
    #             {"success": False, "message": "Cargo name is required."}, status=400
    #         )

    #     cargo = Cargo.objects.filter(CARGO_NAME=cargo_name, user=request.user).first()
    #     if cargo:
    #         try:
    #             cargo.delete()
    #             return JsonResponse({"success": True})
    #         except Exception as e:
    #             return JsonResponse(
    #                 {"success": False, "message": f"Error deleting cargo: {str(e)}"},
    #                 status=500,
    #             )
    #     else:
    #         return JsonResponse({"success": False, "message": "Cargo not found."})


def get_table_names(request):
    """
    Retrieve names of all tables in the database.

    Executes a SQL query to fetch all table names.
    Returns a JSON response with the table names.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response with table names under "tables" key.
    """
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        table_names = [row[0] for row in cursor.fetchall()]

    return JsonResponse({"tables": table_names})


@csrf_exempt
def save_screenshot(request):
    """
    Save a screenshot from the provided image data.

    This function handles POST requests. It decodes the base64 image data
    from the request and saves it as a PNG file in the MEDIA_ROOT directory.
    The file is saved with the name provided in the 'view_name' field.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response indicating success or error.
    """
    if request.method == "POST":
        image_data = request.POST.get("image_data")
        view_name = request.POST.get("view_name")

        # Decode the image data and save it as a PNG file
        image_data = base64.b64decode(image_data.split(",")[1])
        image_directory = settings.MEDIA_ROOT
        image_path = os.path.join(image_directory, f"{view_name}.png")

        # Ensure the directory exists
        if not os.path.exists(image_directory):
            os.makedirs(image_directory)

        # Save the image file
        with open(image_path, "wb") as f:
            f.write(image_data)

        return JsonResponse({"status": "success"})
    else:
        return JsonResponse({"status": "error", "message": "Invalid request method"})


def my_view(request):
    """
    Display user-specific data on the index page.

    Filters and shows Cargo, Pickle, and SavedDataCargoAndTank records
    for the logged-in user.

    Parameters:
    - request: HttpRequest object.

    Returns:
    - Rendered 'index.html' template with user-specific data:
        - 'user_cargos': Cargo records.
        - 'user_pickles': Pickle records.
        - 'user_saved_data': SavedDataCargoAndTank records.
    """
    if request.user.is_authenticated:
        # Filter Cargo records for logged-in user
        user_cargos = Cargo.objects.filter(user=request.user)

        # Filter Pickle records for logged-in user
        user_pickles = Pickle.objects.filter(user=request.user)

        # Filter SavedDataCargoAndTank records for logged-in user
        user_saved_data = saved_data_cargo_and_tank.objects.filter(user=request.user)

        # You can now pass these filtered records to your template or
        # use them as needed
        return render(
            request,
            "index.html",
            {
                "user_cargos": user_cargos,
                "user_pickles": user_pickles,
                "user_saved_data": user_saved_data,
            },
        )


def fetch_report(request, name):
    """
    Fetch the report data for a given cargo name.

    This view retrieves the report data associated with the given 'name'
    from the 'saved_data_cargo_and_tank' model. If the data is found,
    it returns the report in a JSON response. If the specified cargo name
    does not exist, it returns a 404 error.

    Parameters:
    - request: The HTTP request object.
    - name: The name of the cargo whose report data is to be retrieved.

    Returns:
    - JsonResponse: Contains the report data if found.
    - JsonResponse: Error message and 404 status if the data is not found.
    """
    if request.method == "GET":
        # Fetch the object, filtering out deleted entries
        try:
            data = saved_data_cargo_and_tank.objects.get(name=name)
            return JsonResponse({"report": data.report})
        except saved_data_cargo_and_tank.DoesNotExist:
            return JsonResponse({"error": "Data not found"}, status=404)


@csrf_exempt
def update_report(request, identifier):
    """
    Update the report data for a given cargo entry.

    This view updates the report details for the entry identified by
    the provided 'identifier'. It expects a POST request with a JSON
    body containing updated report fields such as "Checked By", "Prepared By",
    "Project Name", "Revision Date", and so on. The function also renames the
    entry based on the new Document Title and Document Number.

    Parameters:
    - request: The HTTP request object.
    - identifier: The name (identifier) of the report entry to update.

    Returns:
    - JsonResponse: A success message with the new name
        if the update is successful.
    - JsonResponse: A 404 error if the report entry is not found.
    - JsonResponse: A 500 error with the exception message if an error occurs.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            report_item = saved_data_cargo_and_tank.objects.get(name=identifier)

            # Load the current report data or initialize as empty dict if None
            current_report_data = report_item.report or {}

            # Update the report data with new values from the request
            current_report_data["Checked By"] = data.get(
                "Checked By", current_report_data.get("Checked By")
            )
            current_report_data["Prepared By"] = data.get(
                "Prepared By", current_report_data.get("Prepared By")
            )
            current_report_data["Project Name"] = data.get(
                "Project Name", current_report_data.get("Project Name")
            )
            current_report_data["Revision Date"] = data.get(
                "Revision Date", current_report_data.get("Revision Date")
            )
            current_report_data["Document Title"] = data.get(
                "Document Title", current_report_data.get("Document Title")
            )
            current_report_data["Project Number"] = data.get(
                "Project Number", current_report_data.get("Project Number")
            )
            current_report_data["Document Number"] = data.get(
                "Document Number", current_report_data.get("Document Number")
            )

            # Update the name field based on the
            # new Document Title and Document Number
            new_name = (
                f"{current_report_data['Document Title'] or ''}_"
                f"{current_report_data['Document Number'] or ''}"
            )
            report_item.name = new_name

            # Save the updated report data back to the model
            report_item.report = current_report_data
            report_item.save()

            return JsonResponse(
                {"success": "Report updated successfully", "new_name": new_name}
            )
        except saved_data_cargo_and_tank.DoesNotExist:
            return JsonResponse({"error": "Report not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
