"""
This module provides views for calculating ship stability and related criteria,
retrieving and saving data, and interacting with the database for
jackup-related operations.
It processes various weight and cargo data, including drilling platform data,
to calculate dead weight, total weight, and other stability-related metrics.
Additionally module handles saving the calculated data to the database and
returning the results in a structured JSON format.

"""

import base64
import io
import json
import pickle
import pandas as pd
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from collections import defaultdict
from django.db.models import Q
from django.views.decorators.http import require_GET
from .crane import calculate_crane_and_swl
from .criteria import get_criteria_data
from .helpers import (
    get_fixed_weight,
    get_gz_curve,
    get_leg_load_distribution,
    get_lightship_weight,
    get_tank_weight,
    optimize_trim,
)

from .ls_plot import get_ls_plot
from .models import (
    Cargo,
    Pickle,
    saved_data_cargo_and_tank,
)
import re

@login_required  # Ensure the user is logged in
def get_all_vessel_names_for_intactstability(request):
    """
    Get all vessel names and images belonging to the logged-in user.

    Retrieves the names and images of all vessel objects associated
    with the logged-in user.
    These names and images are extracted from the Pickle objects
    related to the user's ID.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing a list of vessels with
      their names and images under the key "vessels".
    """
    # Filter the Pickle objects by the logged-in user's ID
    user_vessels = Pickle.objects.filter(user_id=request.user.id).values(
        "name", "image"
    )

    vessels = []
    for vessel in user_vessels:
        image_base64 = None

        # Convert the image BLOB to a base64 string
        if vessel["image"]:  # Check if the image column has data
            image_base64 = base64.b64encode(vessel["image"]).decode("utf-8")

        vessels.append({"name": vessel["name"], "image": image_base64})

    return JsonResponse({"vessels": vessels})


def get_saved_names(request):
    """
    Retrieve names associated with a saved Pickle object.

    If the request method is POST, fetches the 'pickle_name' from
    the request POST data.
    Retrieves the Pickle object with the provided name,
    processes the data to get 'ship'.
    Then, fetches names related to the Pickle object
    from 'saved_data_cargo_and_tank'.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing the names related
        to the Pickle object.
    - HttpResponse: Error response if the Pickle object is not found.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Invalid method"}, status=405)

    namep = request.GET.get("pickle_name")
    if not namep:
        return JsonResponse({"error": "pickle_name is required"}, status=400)

    # Ensure the pickle exists for this user
    exists = Pickle.objects.filter(
        user=request.user, name=namep, user_id=request.user.id
    ).exists()
    if not exists:
        return JsonResponse({"error": "Pickle object not found"}, status=404)

    # Get distinct names directly from the DB
    names = list(
        saved_data_cargo_and_tank.objects.filter(
            user=request.user, pickle_name=namep
        ).values_list("name", flat=True).distinct()
    )

    return JsonResponse({"names": names})




def get_ship_from_pickle(record):
    """
    Deserialize and retrieve ship data from a pickle record.

    Parameters:
    - record (bytes or bytearray): The pickled ship data.

    Returns:
    - tuple: Tuple containing ship data and an error message.
      - ship_data (dict): The deserialized ship data.
      - error_msg (str or None): Error message if an error occurred during
          deserialization, otherwise None.
    """
    if not record:
        return None, "No record provided for unpickling."

    if not isinstance(record, (bytes, bytearray)):
        return None, ("Invalid type for unpickling. Expected bytes or bytearray.")

    ship_data = pickle.loads(record)  # This can still raise exceptions

    if not ship_data:
        return None, "Failed to deserialize ship data."

    return ship_data, None


@require_http_methods(["POST"])  # Ensure this view only accepts POST requests.
def create_worksheet(request):
    """
    Save a new record with the provided name and report details.

    This view accepts a POST request with JSON data including a 'name' field.
    It checks if the provided name already exists, and if not,
    creates a new record
    with default cargo and tank data structures along with
    additional report details.

    Parameters:
    - request (HttpRequest): The HTTP request object containing JSON data.

    Returns:
    - JsonResponse: JSON response indicating success or failure.
      - Success: A new record is created with the provided name
            and report details.
      - Failure: Error message if 'name' is not provided or already exists.
    """
    # Initialize variables
    name = None
    error_message = None

    # Attempt to parse JSON data from the request body
    data = json.loads(request.body)
    name = data.get("name")
    user = request.user
    pickle_name = data.get("pickle_name")
    report_details = {
        "document_title": data.get("documentTitle", ""),
        "document_number": data.get("documentNumber", ""),
        "project_name": data.get("projectName", ""),
        "project_number": data.get("projectNumber", ""),
        "prepared_by": data.get("preparedBy", ""),
        "checked_by": data.get("checkedBy", ""),
        "revision_date": data.get("revisionDate", ""),
    }
    try:
        pickle_obj = Pickle.objects.get(user=request.user, name=pickle_name)
        # Check if 'name' is provided
        if name is None:
            error_message = "Name not provided"

        # Check if the name already exists
        elif saved_data_cargo_and_tank.objects.filter(
            name=name, pickle_name=pickle_name, user=user
        ).exists():
            error_message = "Name already exists"

        # Handle errors and prevent saving
        if error_message:
            return JsonResponse({"success": False, "error": error_message}, status=400)

        ship, error = get_ship_from_pickle(pickle_obj.data)
        if error:
            return HttpResponse(error)

            # If no errors, proceed to create a new record
        tank_list = get_tank_list(ship)
        tank_data = {val: 0 for val in tank_list}
        default_data_structure = {"cargo": [], "tank": tank_data, "criteria": {},"user_input":{},"boomdata":{}}

        saved_data_cargo_and_tank.objects.create(
            user=user,
            name=name,
            datas=default_data_structure,
            pickle_name=pickle_name,
            report=report_details,
        )

        return JsonResponse({"success": True})

    except Pickle.DoesNotExist:
        return HttpResponse("Pickle object not found", status=404)


def get_tank_list(ship):
    """
    Get a list of tanks from the active vessel pickle data.

    Parameters:
    - ship: Active vessel pickle data containing tank information.

    Returns:
    - list: A list of tank names extracted from the ship's pickle data.
    """
    tank_list = [val[:-4] for val in ship.get("Tanks").keys()]
    return tank_list


@require_GET
def get_worksheet_data(request):
    """
    Retrieve the report data associated with a specific cargo.

    This function takes the 'name' parameter from the GET request
    and returns the corresponding report data stored in the
    saved_data_cargo_and_tank model.

    If the 'name' parameter is missing, it returns a 400 Bad Request error.
    If no data is found for the given name, it returns a 404 Not Found error.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: A JSON response containing the report data,
      or an error message if the data is not found
      or the 'name' parameter is missing.
    """
    name = request.GET.get("name")
    pickle_name = request.GET.get("pickle_name")
    if not name:
        return JsonResponse({"error": "Name parameter is required"}, status=400)

    try:
        saved_data = saved_data_cargo_and_tank.objects.get(
            user=request.user, name=name, pickle_name=pickle_name
        )
        report_data = saved_data.report
        return JsonResponse(report_data)
    except saved_data_cargo_and_tank.DoesNotExist:
        return JsonResponse({"error": "Data not found"}, status=404)


@csrf_exempt
def edit_worksheet(request):
    """
    Rename an existing entry and optionally update the associated report.

    This function accepts a POST request with JSON data containing the
    old name, new name, and an optional updated report. It renames
    the entry in the `saved_data_cargo_and_tank` model and updates the
    report data if provided.

    If the old name or new name is missing, or if the entry cannot be found,
    it returns an error response.

    Parameters:
    - request (HttpRequest): The HTTP request object containing JSON
      data with 'old_name', 'new_name', and optionally 'updated_report'.

    Returns:
    - JsonResponse: A success message if the operation is successful,
      or an error message if the request is invalid or the entry is not found.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            old_name = data.get("old_name")
            new_name = data.get("new_name")
            updated_report = data.get("updated_report")
            pickle_name = data.get("pickle_name")

            if not old_name or not new_name:
                return JsonResponse(
                    {"success": False, "message": "Invalid names provided"}
                )

            try:
                saved_data = saved_data_cargo_and_tank.objects.get(
                    user=request.user, name=old_name, pickle_name=pickle_name
                )
                
            except saved_data_cargo_and_tank.DoesNotExist:
                return JsonResponse({"success": False, "message": "Name not found"})
            
            saved_data.name = new_name
            if updated_report:
                saved_data.report = updated_report
            saved_data.save()   

            return JsonResponse(
                {"success": True, "message": "Details updated successfully"}
            )

        except Exception as e:
            return JsonResponse({"success": False, "message": "Name already exists"})

    return JsonResponse({"success": False, "message": "Invalid request method"})


@csrf_exempt  # Temporarily disable CSRF for this view for simplicity
def duplicate_worksheet(request):
    """
    Handle the duplication of a record in the saved_data_cargo_and_tank table.
 
    This function takes a POST request to duplicate an existing record by
    generating a new name with an incremented number and copying the data from
    the original record.
    The function retrieves the next available duplicate number based on the
    existing records, then inserts a new record with the updated name,
    duplicating the content of the original record.
 
    Args:
        request (HttpRequest): The HTTP request object containing the name
        to duplicate in the request body.
 
    Returns:
        JsonResponse: A JSON response indicating the status of the operation.
        If successful, it returns the new name. If an error occurs,
        it returns an error message.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            name_to_duplicate = data.get("name")
            user = request.user
            pickle_name = data.get("pickle_name")

            # Get the original record
            original = saved_data_cargo_and_tank.objects.get(
                name=name_to_duplicate,
                user=user,
                pickle_name=pickle_name
            )

            # Extract original doc title and project name
            report = original.report or {}
            doc_title = report.get("document_title", "").strip()
            current_proj_name = report.get("project_name", "").strip()

            # Match all project_names that start with the current project name
            existing = saved_data_cargo_and_tank.objects.filter(
                user=user,
                pickle_name=pickle_name,
                report__document_title=doc_title,
                report__project_name__startswith=current_proj_name
            )

            # Look for project names that match pattern like: A(1), A(1)(2), etc.
            pattern = re.compile(rf"^{re.escape(current_proj_name)}\((\d+)\)$")
            suffixes = []
            for record in existing:
                pname = record.report.get("project_name", "")
                match = pattern.match(pname)
                if match:
                    suffixes.append(int(match.group(1)))

            next_suffix = max(suffixes, default=0) + 1
            new_proj_name = f"{current_proj_name}({next_suffix})"
            new_name = f"{doc_title}_{new_proj_name}"

            # Copy and update report
            new_report = report.copy()
            new_report["project_name"] = new_proj_name

            # Save new duplicate
            saved_data_cargo_and_tank.objects.create(
                name=new_name,
                datas=original.datas,
                pickle_name=pickle_name,
                user=user,
                report=new_report,
                jackup_data=original.jackup_data,
                crane_data=original.crane_data,
                lcg_value=original.lcg_value
            )

            return JsonResponse({"status": "success", "new_name": new_name})

        except saved_data_cargo_and_tank.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Original worksheet not found"}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)


def delete_worksheet(request):
    """
    Deletes an entry from the saved data based on the provided name.

    Parameters:
    - request: HttpRequest object containing POST data with 'name' parameter.

    Returns:
    - JsonResponse: JSON response indicating success or failure.
      - Success: Entry with the given name is deleted.
      - Failure: Entry with the given name not found or other errors.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body)
        name = data.get("name")
        pickle_name = data.get("pickle_name")

        if not name or not pickle_name:
            return JsonResponse({"success": False, "error": "Missing parameters"}, status=400)

        deleted, _ = saved_data_cargo_and_tank.objects.filter(
            name=name, user=request.user, pickle_name=pickle_name
        ).delete()

        if deleted == 0:
            return JsonResponse({"success": False, "error": "Entry not found"}, status=404)

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_pickle_name(request):
    """
    Retrieve the pickle name associated with a given name and pickle_name.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing the 'pickle_name' associated
        with the provided 'name'.
    - JsonResponse: Error response if 'name' or 'pickle_name' is not provided.
    """
    user = request.user
    name2 = request.GET.get("name", None)
    namep = request.session.get("pickle_name")
    
    pickle_name = (
        request.GET.get("pickle_name", None)
    )  # Use namep as a fallback

    if name2 and pickle_name:
        # Filter by name, user, and pickle_name
        entry = get_object_or_404(
            saved_data_cargo_and_tank, name=name2, user=user, pickle_name=pickle_name
        )
        return JsonResponse({"pickle_name": entry.pickle_name}, safe=False)
    else:
        return JsonResponse({"error": "Name or Pickle Name not provided"}, status=400)


@login_required(login_url="/")
def new_page(request, pickle_name, name):
    """
    View function for rendering a new page with data.

    Retrieves an object based on the provided 'name' and 'pickle_name' from
    the saved_data_cargo_and_tank model.
    Prepares context data including the retrieved object and
    'pickle_name' to pass to the template.

    Parameters:
    - request (HttpRequest): The HTTP request object.
    - pickle_name (str): The pickle name associated with the data.
    - name (str): The name used to retrieve the object from the database.

    Returns:
    - HttpResponse: Rendered template displaying the retrieved object
        and pickle name.
    """
    user = request.user
    # Filter by name, user, and pickle_name to ensure a unique entry is retrieved
    entry = saved_data_cargo_and_tank.objects.filter(
        name=name, user=user, pickle_name=pickle_name
    )

    # Prepare any additional data you want to pass to the template here
    context = {
        "entry": entry,  # Pass the retrieved object to the template
        "pickle_name": pickle_name,  # Also pass the pickle_name for display
    }

    # Render the template with the provided context
    return render(request, "pickle_data_display.html", context)


def get_pickle_object(pickle_name, user):
    """
    Retrieve a Pickle object from the database.

    This function retrieves a Pickle object based on the given pickle name
    and user.
    If the object is not found, it raises a 404 error.

    Args:
        pickle_name (str): The name of the pickle object to retrieve.
        user (User): The user to whom the pickle object belongs.

    Returns:
        Pickle: The Pickle object retrieved from the database.

    Raises:
        Http404: If the Pickle object with the given name and
        user is not found.
    """
    return get_object_or_404(Pickle, name=pickle_name, user=user)


def process_pickle_data(pickle_obj):
    """
    Process a Pickle object to extract vessel data and model information.

    This function processes a Pickle object, extracting vessel data and
    model information.It converts the vessel data into a JSON-serializable-
    format and encodes any `.obj` and `.jpg` files related to the hull in
    base64 for further use.

    Args:
        pickle_obj (Pickle): A Pickle object containing vessel and model data.

    Returns:
        tuple: A tuple containing:
            - vessel_data_dict_json (str): The vessel data in JSON format.
            - models_with_textures_json (str): JSON-encoded list of model data,
                including corresponding textures.

    Raises:
        KeyError: If expected keys ('ship_data.json' or 'Hull') are missing
        from the Pickle data.
    """
    pickle_data = get_ship_from_pickle(pickle_obj.data)
    vessel_data_for_view = pickle_data[0]["ship_data.json"]["vessel_data"]
    # Access the dictionary within the first row of the DataFrame
    pedestal_base_point = None
    boom_base_point = None
    if (
        "crane_data.json" in pickle_data[0]
        and "crane_1" in pickle_data[0]["crane_data.json"]
    ):
        a = pickle_data[0]["crane_data.json"]["crane_1"].iloc[0]
        pedestal_base_point = a.get("pedestal_base_point")
        boom_base_point = a.get("boom_base_point")

    vessel_data_dict = list(vessel_data_for_view.items())
    vessel_data_dict_json = json.dumps(vessel_data_dict)
    model_data_list = []
    if "Hull" in pickle_data[0] and isinstance(pickle_data[0]["Hull"], dict):
        hull_data = pickle_data[0]["Hull"]
        for key, file_data in hull_data.items():
            if file_data is not None:
                file_data_base64 = base64.b64encode(file_data).decode("utf-8")
                extension = key.split(".")[-1]

                if extension == "webp":
                    # Prepend the data URI prefix for webp textures
                    file_data_base64 = "data:image/webp;base64," + file_data_base64

                # Only include obj and webp files
                if extension in ["obj", "webp"]:
                    model_data_list.append(
                        {"name": key, "data": file_data_base64, "type": extension}
                    )

    models_with_textures = []
    for model in model_data_list:
        if model["type"] == "obj":
            # Update here: from .jpg to .webp
            corresponding_texture = next(
                (
                    item
                    for item in model_data_list
                    if item["type"] == "webp"
                    and item["name"] == model["name"].replace(".obj", ".webp")
                ),
                None,
            )

            models_with_textures.append(
                {
                    "obj_filename": model["name"],
                    "model": model["data"],
                    "texture": (
                        corresponding_texture["data"] if corresponding_texture else None
                    ),
                    "pedestal_base_point": pedestal_base_point,
                    "boom_base_point": boom_base_point,
                }
            )

    return vessel_data_dict_json, json.dumps(models_with_textures)


def get_data_by_name(request):
    """
    Retrieve data related to a specific name.

    If 'name' is provided in the GET request,
    updates the global variable 'selected_name'
    and fetches relevant data from the database.
    Encodes Hull data (if exists) to Base64.
    Retrieves cargo and tank data, encodes cargo mesh files and
    Hull data (obj and jpg) to Base64.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing the requested data:
        - 'tank_data': Tank data associated with the name.
        - 'cargo_data': Cargo data associated with the name.
        - 'mesh_files_info': Information about cargo mesh files with
                Base64 encoded contents.
        - 'obj_data': List of dictionaries with Hull .obj file names and
                Base64 encoded contents.
        - 'jpg_data': List of dictionaries with Hull .jpg file names and
                Base64 encoded contents.
        - 'leg_data_check': Boolean indicating whether 'leg_data' was found
                inside "ship_data.json".
    """
    drill_platform_check = False
    name = request.GET.get("name", None)
    user_id = request.user.id
    pickle_name = request.GET.get("pickle_name")

    try:
        pickle_obj = Pickle.objects.get(user=request.user, name=pickle_name)
        ship, error = get_ship_from_pickle(pickle_obj.data)
        if error:
            return HttpResponse(error)
        if name and user_id and pickle_name:
            data_instance = saved_data_cargo_and_tank.objects.get(
                name=name, user_id=user_id, pickle_name=pickle_name
            )
            drilling_platform = {}

            if (
                "drilling platform" in ship.get("ship_data.json", {})
                and not ship["ship_data.json"]["drilling platform"].empty
            ):
                drill_platform_check = True
            else:
                drill_platform_check = False

            if drill_platform_check == True:
                drillingplatform_lcg_value_from_pickle = ship["ship_data.json"][
                    "drilling platform"
                ].iloc[0]
                if data_instance.lcg_value:
                    drilling_platform = data_instance.lcg_value
                else:
                    drilling_platform = ship["ship_data.json"][
                        "drilling platform"
                    ].iloc[0]
                    data_instance.lcg_value = drilling_platform
            else:
                drilling_platform = {
                    "weight": 0,
                    "lcg": 0,
                    "vcg": 0,
                    "tcg": 0,
                }
                data_instance.lcg_value = drilling_platform
                drillingplatform_lcg_value_from_pickle = 0

            report_data = data_instance.report
            stability_filters = data_instance.datas.get(
                "stability_filtered_criteria", []
            )
            weather_filters = data_instance.datas.get("weather_filtered_criteria", [])
            pickle_file_name = data_instance.pickle_name

            pickle_file = Pickle.objects.get(
                user=request.user,
                name=pickle_file_name,
                user_id=user_id,
            )  # Filter by user and pickle_file_name

            vessel_type = pickle_file.vessel_type

            pickle_data = get_ship_from_pickle(pickle_file.data)

            obj_data_base64_list = []
            jpg_data_base64_list = []
            dxf_data_list = []
            dot_jpg_list = []
            request.session["dot_jpg_list"] = dot_jpg_list

            # Check if the first element in pickle_data has '.' (dot) and
            # extract any '.jpg' files
            if "." in pickle_data[0]:
                nested_dict = pickle_data[0]["."]
                for key in nested_dict.keys():
                    if key.endswith("logo.jpg"):
                        file_data = nested_dict[key]
                        if file_data is not None:
                            file_data_base64 = base64.b64encode(file_data).decode(
                                "utf-8"
                            )
                            dot_jpg_list.append({key: file_data_base64})

            # Check if "Hull" key exists and has a dictionary as its value
            if "Hull" in pickle_data[0] and isinstance(pickle_data[0]["Hull"], dict):
                hull_data = pickle_data[0]["Hull"]
                for key in hull_data.keys():
                    if key.endswith(".obj") or key.endswith(".webp"):
                        file_data = hull_data[key]
                        if file_data is not None:
                            file_data_base64 = base64.b64encode(file_data).decode(
                                "utf-8"
                            )
                            if key.endswith(".obj"):
                                obj_data_base64_list.append({key: file_data_base64})
                            elif key.endswith(".webp"):
                                jpg_data_base64_list.append({key: file_data_base64})

            # Assuming pickle_data contains the ship dictionary
            ship_data = pickle_data[0]
            for key, value in ship_data.items():
                if key.endswith(".dxf") and value is not None:
                    dxf_content_base64 = base64.b64encode(value).decode("utf-8")
                    dxf_data_list.append({key: dxf_content_base64})

            # Retrieve cargo_data and update the global variable
            cargo_data = data_instance.datas.get("cargo", None)
            criteria_data = data_instance.datas.get("criteria", None)

            mesh_files_info = []
            if cargo_data:
                for item in cargo_data:
                    if "mesh_name" in item and "name" in item:
                        cargo_mesh = Cargo.objects.filter(
                            MESH=item["mesh_name"]
                        ).first()
                        if cargo_mesh and cargo_mesh.MESHFILE:
                            mesh_file_base64 = base64.b64encode(
                                cargo_mesh.MESHFILE
                            ).decode("utf-8")
                            mesh_files_info.append(
                                {
                                    "mesh_name": item["name"],
                                    "mesh_file_base64": mesh_file_base64,
                                    "lcg": item.get("lcg", 0),
                                    "vcg": item.get("vcg", 0),
                                    "tcg": item.get("tcg", 0),
                                }
                            )

            tank_data = data_instance.datas.get("tank", None)
            if tank_data:
                sorted_tank_data = dict(
                    sorted(
                        tank_data.items(),
                        key=lambda item: item[0].lower()  # alphabetical, case-insensitive
                    )
                )
            else:
                sorted_tank_data = None
            # Add error handling for 'crane_data.json'
            try:
                pedestal_base_point = ship["crane_data.json"]["crane_1"][0][
                    "pedestal_base_point"
                ]
                boom_base_point = ship["crane_data.json"]["crane_1"][0][
                    "boom_base_point"
                ]
            except KeyError:
                pedestal_base_point = None
                boom_base_point = None

            # Check if 'leg_data' exists inside "ship_data.json"
            leg_data_exists = False
            if "ship_data.json" in pickle_data[0]:
                ship_data_json = pickle_data[0]["ship_data.json"]
                leg_data_exists = "leg_data" in ship_data_json
            boom_working_modes = {}

            if "Crane Data" in ship:
                swl_table = ship["Crane Data"]
                if isinstance(swl_table, dict):
                    for boom_name, boom_data in swl_table.items():
                        if isinstance(boom_data, dict):
                            working_mode_dict = {}
                            for working_mode, file_dict in boom_data.items():
                                if isinstance(file_dict, dict):
                                    csv_files = [
                                        filename.replace(".csv", "")
                                        for filename in file_dict.keys()
                                        if isinstance(filename, str)
                                        and filename.endswith(".csv")
                                    ]
                                    working_mode_dict[working_mode] = csv_files
                                    boom_working_modes[boom_name] = working_mode_dict
            crane_data_to_front = data_instance.crane_data or {
                "name": "SELECT WEIGHT HERE",
                "weight": 0,
                "lcg": 0,
                "tcg": 0,
                "vcg": 0,
            }
            user_input=data_instance.datas["user_input"] or {
                "WCF" : 1.10,
                "DAF" : 1.10,
                "DAFincl" : 1.10,
                "Mrigging" : 15.40,
                "WCFrigging" : 1.10,
                "Mhook" : 0.00,
                "Mblock" : 0.00
            }

            jackupdata_table = data_instance.jackup_data or {
                'maxEW': 5000, 
                'squareX2': 2, 
                'squareY2': 2, 
                'legsYPosition': -25, 
                'seabedYPosition': -20
            }
            boomdata=data_instance.datas["boomdata"]
            
            response_data = {
                "tank_data": sorted_tank_data,
                "cargo_data": cargo_data,
                "stability_filtered_criteria": stability_filters,
                "weather_filtered_criteria": weather_filters,
                "mesh_files_info": mesh_files_info,
                "obj_data": obj_data_base64_list,
                "jpg_data": jpg_data_base64_list,
                "dxf_data": dxf_data_list,
                "img_data": dot_jpg_list,
                "criteria_data": criteria_data,
                "pedestal_base_point": pedestal_base_point,
                "boom_base_point": boom_base_point,
                "leg_data_check": leg_data_exists,
                "report_data": report_data,
                "vessel_type": vessel_type,
                "boom_working_modes": boom_working_modes,
                "drilling_platform": drilling_platform,
                "drill_platform_check": drill_platform_check,
                "drillingplatform_lcg_value_from_pickle": drillingplatform_lcg_value_from_pickle,
                "crane_data_to_front": crane_data_to_front,
                "user_input":user_input,
                "jackup_data": jackupdata_table,
                "boomdata":boomdata
            }

            if not response_data["tank_data"] and not response_data["cargo_data"]:
                return JsonResponse(
                    {"error": "No tank or cargo data found"}, status=400
                )
            return JsonResponse(response_data)

    except saved_data_cargo_and_tank.DoesNotExist:
        return JsonResponse({"error": "Data not found"}, status=404)
    except Pickle.DoesNotExist:
        return JsonResponse({"error": "Pickle data not found for the user"}, status=404)

    return JsonResponse({"error": "Name or ID or pickle name not provided"}, status=400)


def solve(request):
    """
    Main function to calculate ship stability and criteria.

    This function handles the POST request with ship and weight data.
    It calculates tank, lightship, fixed weight, dead weight, total weight,
    and floating status data.
    Finally, it computes the GZ curve and stability criteria data for the ship.

    Parameters:
    - request (HttpRequest): The HTTP request object containing weight data.

    Returns:
    - JsonResponse: JSON response with calculated ship stability data
      including tank, lightship, fixed weight,
      dead weight, total weight, floating status, GZ curve, and
      stability criteria.
    """
    tank_data = {}
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST method is allowed")

    unique_name = request.POST.get("name", None)
    user_id = request.user.id
    pickle_name = request.POST.get("pickle_name")

    try:
        weight_data = json.loads(request.POST.get("weight_data", "[]"))
        criteria_limits = json.loads(request.POST.get("criteria_data", "{}"))
        try:
            filtered_criteria = json.loads(request.POST.get("filtered_criteria", "{}"))
        except json.JSONDecodeError as e:
            filtered_criteria = {"stability": [], "weather": []}

        platform_data = json.loads(request.POST.get("platform_data", "{}"))
       

        raw_data = request.POST.get("pickle_name3", "{}")  # Get JSON string or default to empty dict
        try:
            worksheet_data = json.loads(raw_data)
        except json.JSONDecodeError:
            worksheet_data = {}  # Fallback if invalid JSON is received


        if not isinstance(weight_data, list) or not isinstance(criteria_limits, dict):
            return HttpResponseBadRequest("Invalid JSON format")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return HttpResponseBadRequest("Invalid JSON")

    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # Clear previous tank data
    tank_data.clear()

    tank_fill_data_raw = request.POST.get("tank_fill_data")
    if tank_fill_data_raw:
        try:
            tank_fill_list = json.loads(tank_fill_data_raw)
            for item in tank_fill_list:
                name = item.get("name")
                fill = item.get("fill")
                if name and isinstance(fill, (int, float)):
                    tank_data[name] = float(fill)
                else:
                    print(f"Invalid tank entry: {item}")
        except json.JSONDecodeError as e:
            print(f"Error decoding tank_fill_data: {e}")

    saved_entry = saved_data_cargo_and_tank.objects.filter(
        name=unique_name,
        # user=request.user,
        user_id=user_id,
        pickle_name=pickle_name,
    ).first()
    stability_criteria = filtered_criteria.get("stability", [])
    weather_criteria = filtered_criteria.get("weather", [])
    if saved_entry:
        saved_data_json = saved_entry.datas
        saved_data_json["cargo"] = weight_data
        saved_data_json["tank"] = tank_data
        saved_data_json["criteria"] = criteria_limits
        saved_data_json["stability_filtered_criteria"] = stability_criteria
        saved_data_json["weather_filtered_criteria"] = weather_criteria
        saved_data_json["drilling_platform"] = platform_data

        saved_entry.datas = saved_data_json
        saved_entry.lcg_value = platform_data
        saved_entry.save()

    else:
        data_to_save = {
            "cargo": weight_data,
            "tank": tank_data,
            "stability_filtered_criteria": stability_criteria,
            "weather_filtered_criteria": weather_criteria,
            "drilling_platform": platform_data,
        }

        new_entry = saved_data_cargo_and_tank(
            user=request.user,
            name=unique_name,
            user_id=user_id,
            pickle_name=pickle_name,
            datas=data_to_save,
            lcg_value=platform_data,
        )
        new_entry.save()

    try:

        pickle_obj = Pickle.objects.get(user=request.user, name=pickle_name)

        ship, error = get_ship_from_pickle(pickle_obj.data)
        if error:
            return HttpResponse(error)

        tank_vals, (tank_weight, tank_lcg, tank_tcg, tank_vcg, tank_fsm) = (
            get_tank_weight(ship, tank_data)
        )

        if isinstance(platform_data, dict):
            weight_data.append(platform_data)

        valid_weight_data = [item for item in weight_data if "weight" in item]
        (
            fixed_weight,
            fixed_weight_lcg,
            fixed_weight_tcg,
            fixed_weight_vcg,
        ) = get_fixed_weight(valid_weight_data)

        fixed_weight_data = {
            "total_weight": fixed_weight,
            "total_lcg": fixed_weight_lcg,
            "total_tcg": fixed_weight_tcg,
            "total_vcg": fixed_weight_vcg,
        }

        (
            lightship_weight,
            lightship_lcg,
            lightship_tcg,
            lightship_vcg,
        ) = get_lightship_weight(ship)

        lightship_weight_data = {
            "total_weight": lightship_weight,
            "total_lcg": lightship_lcg,
            "total_tcg": lightship_tcg,
            "total_vcg": lightship_vcg,
        }

        tank_weight_data = {
            "total_weight": tank_weight,
            "total_lcg": tank_lcg,
            "total_tcg": tank_tcg,
            "total_vcg": tank_vcg,
        }

        dead_weight = tank_weight + fixed_weight
        if dead_weight != 0:
            dead_weight_lcg = (
                tank_weight * tank_lcg + fixed_weight * fixed_weight_lcg
            ) / dead_weight
            dead_weight_tcg = (
                tank_weight * tank_tcg + fixed_weight * fixed_weight_tcg
            ) / dead_weight
            dead_weight_vcg = (
                tank_weight * tank_vcg + fixed_weight * fixed_weight_vcg
            ) / dead_weight
        else:
            dead_weight_lcg = 0
            dead_weight_tcg = 0
            dead_weight_vcg = 0

        dead_weight_data = {
            "total_weight": dead_weight,
            "total_lcg": dead_weight_lcg,
            "total_tcg": dead_weight_tcg,
            "total_vcg": dead_weight_vcg,
        }

        total_weight = dead_weight + lightship_weight
        if total_weight != 0:
            total_weight_lcg = (
                dead_weight * dead_weight_lcg + lightship_weight * lightship_lcg
            ) / total_weight
            total_weight_tcg = (
                dead_weight * dead_weight_tcg + lightship_weight * lightship_tcg
            ) / total_weight
            total_weight_vcg = (
                dead_weight * dead_weight_vcg + lightship_weight * lightship_vcg
            ) / total_weight
        else:
            total_weight_lcg = 0
            total_weight_tcg = 0
            total_weight_vcg = 0

        total_weight_data = {
            "total_weight": total_weight,
            "total_lcg": total_weight_lcg,
            "total_tcg": total_weight_tcg,
            "total_vcg": total_weight_vcg,
        }

        vessel_data = ship["ship_data.json"]["vessel_data"]
        length = vessel_data[0]["loa"]
        depth = vessel_data[0]["depth"]
        breadth = vessel_data[0]["breadth"]

        vcg_corr = total_weight_vcg - tank_fsm / total_weight

        floating_status = optimize_trim(
            ship,
            total_weight,
            total_weight_lcg,
            total_weight_tcg,
            total_weight_vcg,
            vcg_corr,
            length,
        )
        trim = floating_status["trim"]

        gz_curve_data = get_gz_curve(
            ship, total_weight, total_weight_vcg, total_weight_tcg, trim
        )

        gmt_corr = floating_status["kmt"] - total_weight_vcg
        draft = floating_status["draft"]
        max_draft = draft + floating_status["trim"]

        criteria_data = get_criteria_data(
            gz_curve=gz_curve_data,
            length=length,
            depth=depth,
            draft=draft,
            breadth=breadth,
            total_weight=total_weight,
            gmt_corr=gmt_corr,
            max_draft=max_draft,
            criteria_limits=criteria_limits,
        )

        draft_aft = draft + floating_status["draft_aft"]

        ls_data = get_ls_plot(
            ship=ship,
            draft_aft=draft_aft,
            tank_data=tank_vals,
            cargo_data=weight_data,
            trim=trim,
        )

        floating_status['tcb'] = 0.00

        response_data = {
            "tank_vals": tank_vals,
            "tank_weight_data": tank_weight_data,
            "lightship_data": lightship_weight_data,
            "fixed_weight_data": fixed_weight_data,
            "dead_weight_data": dead_weight_data,
            "total_weight_data": total_weight_data,
            "floating_status": floating_status,
            "gz_curve": gz_curve_data,
            "criteria_data": criteria_data,
            "ls_data": ls_data,
            "weight_data": weight_data,
            "criteria_table": criteria_data,
            "drilling_platform": platform_data,
        }

        return JsonResponse(response_data)
    except Pickle.DoesNotExist:
        return HttpResponse("Pickle object not found", status=404)


@login_required  # Ensure that only logged-in users can access this view
def get_cargo_names(request):
    """
    Get names of cargos associated with the logged-in user.

    This function retrieves the names of cargos belonging to
    the current logged-in user
    and returns them as a JSON response.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing a list of cargo names.
    """
    # Filter the cargos by the current user
    cargo_names = list(
        Cargo.objects.filter(user=request.user).values_list("CARGO_NAME", flat=True)
    )

    return JsonResponse(cargo_names, safe=False)


@login_required  # Ensure that only logged-in users can access this view
def get_cargoname_data(request):
    """
    Get cargo data based on the provided cargo_name and
    the logged-in user's ID.

    This function retrieves cargo data for a given cargo_name from
    the Cargo model,
    filtered by the logged-in user's ID. It then generates a
    new unique cargo_data_name based
    on existing counts of the same cargo_name and appends the
    cargo data to the global_cargo_data list.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing the cargo data
        for the provided cargo_name.
      - If the cargo is found, returns the cargo data.
      - If the cargo is not found, returns an error response with status 404.
      - If the cargo_name is not provided in the request, returns an
            error response with status 400.
    """
    global_cargo_data = []

    cargo_name = request.GET.get("cargo_name")
    if not cargo_name:
        return JsonResponse({"error": "Cargo name not provided"}, status=400)

    # Fetch cargo data from Cargo model, filtered by both CARGO_NAME
    # and the logged-in user
    cargo = Cargo.objects.filter(CARGO_NAME=cargo_name, user=request.user).first()

    if cargo:
        # Initialize the list to store existing counts for the cargo name
        existing_counts = []

        # Check each item in global_cargo_data for cargo_name and
        # extract the count
        for item in global_cargo_data:
            name_parts = item["name"].split(" (")
            if name_parts[0] == cargo_name:
                if len(name_parts) > 1:
                    try:
                        count = int(name_parts[1].rstrip(")"))
                        existing_counts.append(count)
                    except ValueError:
                        # If the count is not an integer, ignore it
                        pass

        # Determine the new count based on the maximum found count
        if existing_counts:
            new_count = max(existing_counts) + 1
            cargo_data_name = f"{cargo_name} ({new_count})"
        else:
            # If no counts found and the name already exists, start numbering
            if any(item["name"] == cargo_name for item in global_cargo_data):
                cargo_data_name = f"{cargo_name} (1)"
            else:
                # If the name does not exist at all, use it as is
                cargo_data_name = cargo_name

        # Construct the cargo data dictionary
        cargo_data = {
            "name": cargo_data_name,
            "weight": float(cargo.WEIGHT),
            "lcg": float(cargo.LCG),
            "vcg": float(cargo.VCG),
            "tcg": float(cargo.TCG),
            "mesh_name": cargo.MESH,
            "length": float(cargo.LENGTH),
            "breadth": float(cargo.BREADTH),
            "height": float(cargo.HEIGHT),
            "color": cargo.COLOR,
            "diameter": float(cargo.DIAMETER),
        }

        # Append cargo_data to global_cargo_data
        global_cargo_data.append(cargo_data)

        return JsonResponse(cargo_data)
    else:
        return JsonResponse({"error": "Cargo not found"}, status=404)


def delete_cargo_entry(request):
    """
    Delete a cargo entry from the worksheet.

    This API deletes a cargo entry from the worksheet
    based on the provided row name
    and cargo entry name. The cargo entry is removed from the saved data.

    Parameters:
    - request (HttpRequest): The HTTP request object containing POST data.

    Returns:
    - JsonResponse: JSON response indicating success or failure.
      - Success: Cargo entry deleted successfully.
      - Failure: Missing required parameters, cargo entry not found,
        or internal server error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST request required."}, status=405)

    row_name = request.POST.get("row_name")
    cargo_entry_name = request.POST.get("cargo_entry_name")
    pickle_name = request.POST.get("pickle_name")
    name = request.POST.get("name")
    user_id = request.user.id

    if not row_name or not cargo_entry_name:
        return JsonResponse({"error": "Missing required parameters."}, status=400)

    try:
        rows = saved_data_cargo_and_tank.objects.filter(
            pickle_name=pickle_name, name=name, user_id=user_id
        )
        for row in rows:
            data = row.datas
            cargo_list = data.get("cargo", [])
            # Check if cargo entry name is in this row
            if any(cargo.get("name") == row_name for cargo in cargo_list):
                updated_cargo_list = [
                    cargo for cargo in cargo_list if cargo.get("name") != row_name
                ]
                data["cargo"] = updated_cargo_list
                # Check if the cargo_entry_name matches the crane_data name
                if row.crane_data and row.crane_data.get("name") == row_name:
                    # Set crane_data to NULL or empty object if names match
                    row.crane_data = {}
                # Uncomment this line if you want an empty dictionary instead

                # Update the row with the new cargo and crane data

                row.datas = data
                row.save()
                return JsonResponse(
                    {"success": True, "message": "Cargo entry deleted successfully."}
                )

        return JsonResponse({"error": "Cargo entry not found."}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_cargo_mesh_file(request):
    """
    Retrieve cargo's mesh file and associated data.

    Retrieves the mesh file and cargo data (LCG, VCG, TCG)
    for a given cargo name.
    The cargo's mesh file is returned as an attachment with the
    filename "{cargo_name}.obj".
    The cargo data (LCG, VCG, TCG) is added to the response headers as
    JSON under 'X-Additional-Info'.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - HttpResponse: Response containing the cargo's mesh file.
    - JsonResponse: JSON response if cargo name is not provided, mesh data
        not found, or cargo not found.
    """
    cargo_name = request.GET.get("cargoName")

    if not cargo_name:
        return JsonResponse({"error": "Cargo name not provided"})

    try:
        cargo = Cargo.objects.get(CARGO_NAME=cargo_name, user=request.user)

        # Since MESHFILE is a BinaryField, you directly get bytes.
        mesh_content = cargo.MESHFILE
        if not mesh_content:
            return JsonResponse({"error": "Mesh data not found"})

        # Fetch LCG, VCG, TCG data and convert them to strings
        lcg = str(cargo.LCG)
        vcg = str(cargo.VCG)
        tcg = str(cargo.TCG)

        # Creating a response dictionary
        response_data = {
            "LCG": lcg,
            "VCG": vcg,
            "TCG": tcg,
            "MeshFileName": f"{cargo_name}.obj",
        }

        # Adding mesh file content to the response
        response = HttpResponse(io.BytesIO(mesh_content), content_type="text/plain")
        response["Content-Disposition"] = f"attachment; filename={cargo_name}.obj"

        # Adding LCG, VCG, TCG data to the response as JSON
        response["X-Additional-Info"] = json.dumps(response_data)

        return response

    except ObjectDoesNotExist:
        return JsonResponse({"error": "Cargo not found"})


import math


def solve_jackup_get_data(request):
    """
    Main function to calculate ship stability and criteria.
    """
    tank_data = {}
    is_editable = True  # Default to editable
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST method is allowed")

    try:
        user = request.user
        data = json.loads(request.body)
        restricted_users = ["testuser", "testuser2"]
        pickle_name = data.get("pickle_name")
        worksheet_data = data.get("name")
        jackup_save_data = json.loads(request.body) if request.body else {}
        weight_data = jackup_save_data.get("cargo", {})
        cargoNameInCrane = jackup_save_data.get("selectedCargoInCrane")
        if not cargoNameInCrane:  # If None or empty
            cargoNameInCrane = "SELECT WEIGHT HERE"

        lcg_value = jackup_save_data.get("drilling_platform")
        tank_data = jackup_save_data.get("tank", {})

        # Extract lcg, tcg, vcg, weight, and name from weight_data
        valid_weight_data = [item for item in weight_data if "name" in item]
        cargo_list = []  # Use a list to store cargo info

        # Prepare tank_data
        tank_data = jackup_save_data.get("tank", {})
        # Extract lcg, tcg, vcg, weight, and name from weight_data
        valid_weight_data = [item for item in weight_data if "name" in item]
        cargo_list = []  # Use a list to store cargo info

        # Loop through weight_data and add each cargo's info to the cargo_list
        for cargo in valid_weight_data:
            cargo_name = cargo.get("name", "")
            if cargo_name.lower() == "drilling platform":
                continue  # Skip this cargo if the name is "drilling platform"

            cargo_info = {
                "name": cargo_name,
                "weight": cargo.get("weight", 1),
                "lcg": cargo.get("lcg", 0),
                "tcg": cargo.get("tcg", 0),
                "vcg": cargo.get("vcg", 0),
            }
            # Append each cargo's info to the list
            cargo_list.append(cargo_info)

        # After processing weight_data, append the drilling_platform -
        # values to cargo_list
        if user.username in restricted_users:
            is_editable = False
        if lcg_value:
            cargo_list.append(lcg_value)  # Add drilling_platform info to the list

        filtered_cargo = {}

        # Filter the cargo data to match the name of the cargo in the crane
        if cargoNameInCrane == "SELECT WEIGHT HERE":
            filtered_cargo = {
                "name": "SELECT WEIGHT HERE",
                "weight": 0,
                "lcg": 0,
                "tcg": 0,
                "vcg": 0,
            }
        else:
            # Filter the cargo data to match the name of the cargo in the crane
            filtered_cargo = next(
                (
                    cargo
                    for cargo in cargo_list
                    if cargo.get("name") == cargoNameInCrane
                ),
                {},
            )
        if not filtered_cargo:
            filtered_cargo = {
                "name": "SELECT WEIGHT HERE",
                "weight": 0,
                "lcg": 0,
                "tcg": 0,
                "vcg": 0,
            }

        # lcg_value = jackup_save_data.get("drilling_platform")

        if jackup_save_data:
            jackup_data = jackup_save_data.get("jackup_data", {})

            datas = {
                key: value
                for key, value in jackup_save_data.items()
                if key != "jackup_data"
            }

            if not isinstance(datas, dict) or not isinstance(jackup_data, dict):
                return HttpResponseBadRequest("Invalid JSON format")

            # Saving or updating the jackup_save_data in the database
            if worksheet_data:
                saved_entry = saved_data_cargo_and_tank.objects.filter(
                    user=request.user.id, name=worksheet_data, pickle_name=pickle_name
                ).first()
                if saved_entry:
                    saved_entry.datas["tank"] = tank_data
                    saved_entry.datas["cargo"] = datas["cargo"]
                    saved_entry.datas["user_input"] = datas["user_input"]
                    saved_entry.datas["selectedCargoInCrane"] = datas[
                        "selectedCargoInCrane"
                    ]
                    saved_entry.datas["boomdata"] = datas["boomdata"]
                    saved_entry.jackup_data = jackup_data
                    # Save LCG value to the database
                    for key in ["lcg", "weight", "tcg", "vcg", "lcg_a", "lcg_f"]:
                        if lcg_value.get(key) is None:
                            existing_value = (
                                saved_entry.lcg_value.get(key)
                                if saved_entry.lcg_value
                                else None
                            )
                            if existing_value is not None:
                                lcg_value[key] = (
                                    existing_value  # Set from existing saved value
                                )
                            else:
                                lcg_value[key] = 0

                    saved_entry.lcg_value = lcg_value

                    # Now update the crane_data if it has changed or is new
                    if filtered_cargo and (
                        not saved_entry.crane_data
                        or filtered_cargo != saved_entry.crane_data
                    ):
                        saved_entry.crane_data = filtered_cargo

                    # Save the updated entry
                    saved_entry.save()

                else:
                    # Handle the case where the selected_name does not exist in the database
                    new_entry = saved_data_cargo_and_tank(
                        name=worksheet_data,
                        datas=datas,
                        jackup_data=jackup_data,
                        lcg_value=lcg_value,  # Save LCG value in a new entry
                        crane_data=filtered_cargo,  # Save crane_data in a new entry
                    )
                    new_entry.save()
            else:
                return JsonResponse({"error": "Selected name not provided"}, status=400)

    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
 


    # Use valid_weight_data for processing weight data
    saved_entry = saved_data_cargo_and_tank.objects.filter(
        user=request.user.id, pickle_name=pickle_name, name=worksheet_data
    ).first()
    valid_weight_data = []
    try:
        pickle_obj = Pickle.objects.get(
            user=request.user, name=pickle_name, user_id=request.user.id
        )

        ship, error = get_ship_from_pickle(pickle_obj.data)
        if error:
            return HttpResponse(error)
        
        if isinstance(lcg_value, dict):
            weight_data.append(lcg_value)

        valid_weight_data = [item for item in weight_data if "weight" in item]
        # Calculate fixed weight data
        (
            fixed_weight,
            fixed_weight_lcg,
            fixed_weight_tcg,
            fixed_weight_vcg,
        ) = get_fixed_weight(valid_weight_data)

        fixed_weight_data = {
            "total_weight": fixed_weight,
            "total_lcg": fixed_weight_lcg,
            "total_tcg": fixed_weight_tcg,
            "total_vcg": fixed_weight_vcg,
        }

        # Calculate lightship weight data
        (
            lightship_weight,
            lightship_lcg,
            lightship_tcg,
            lightship_vcg,
        ) = get_lightship_weight(ship)

        lightship_weight_data = {
            "total_weight": lightship_weight,
            "total_lcg": lightship_lcg,
            "total_tcg": lightship_tcg,
            "total_vcg": lightship_vcg,
        }

        # Clear previous tank data

        if not ship:
            return JsonResponse({"error": "Ship data not available"}, status=400)

        # Calculate tank weight data
        tank_vals, (tank_weight, tank_lcg, tank_tcg, tank_vcg, tank_fsm) = (
            get_tank_weight(ship, tank_data)
        )
        tank_weight_data = {
            "total_weight": tank_weight,
            "total_lcg": tank_lcg,
            "total_tcg": tank_tcg,
            "total_vcg": tank_vcg,
        }

        # Calculate dead weight data
        dead_weight = tank_weight + fixed_weight
        if dead_weight != 0:
            dead_weight_lcg = (
                tank_weight * tank_lcg + fixed_weight * fixed_weight_lcg
            ) / dead_weight
            dead_weight_tcg = (
                tank_weight * tank_tcg + fixed_weight * fixed_weight_tcg
            ) / dead_weight
            dead_weight_vcg = (
                tank_weight * tank_vcg + fixed_weight * fixed_weight_vcg
            ) / dead_weight
        else:
            dead_weight_lcg = 0
            dead_weight_tcg = 0
            dead_weight_vcg = 0

        dead_weight_data = {
            "total_weight": dead_weight,
            "total_lcg": dead_weight_lcg,
            "total_tcg": dead_weight_tcg,
            "total_vcg": dead_weight_vcg,
        }

        # Calculate total weight data
        total_weight = dead_weight + lightship_weight
        if total_weight != 0:
            total_weight_lcg = (
                dead_weight * dead_weight_lcg + lightship_weight * lightship_lcg
            ) / total_weight
            total_weight_tcg = (
                dead_weight * dead_weight_tcg + lightship_weight * lightship_tcg
            ) / total_weight
            total_weight_vcg = (
                dead_weight * dead_weight_vcg + lightship_weight * lightship_vcg
            ) / total_weight
        else:
            total_weight_lcg = 0
            total_weight_tcg = 0
            total_weight_vcg = 0

        total_weight_data = {
            "total_weight": total_weight,
            "total_lcg": total_weight_lcg,
            "total_tcg": total_weight_tcg,
            "total_vcg": total_weight_vcg,
        }

        [pedestal_base_x, pedestal_base_y, pedestal_base_z] = ship["crane_data.json"][
            "crane_1"
        ][0]["pedestal_base_point"]

        [boom_base_x, boom_base_y, boom_base_z] = ship["crane_data.json"]["crane_1"][0][
            "boom_base_point"
        ]
        # Correct VCG
        vcg_corr = total_weight_vcg - tank_fsm / total_weight

        # Calculate leg load distribution
        leg_data, lever_coordinates = get_leg_load_distribution(
            ship=ship,
            total_weight=total_weight,
            total_lcg=total_weight_lcg,
            total_tcg=total_weight_tcg,
        )
        saved_entry2 = saved_data_cargo_and_tank.objects.filter(
            user=request.user.id, pickle_name=pickle_name, name=worksheet_data
        ).first()

        if saved_entry2 and "user_input" in saved_entry2.datas:
            user_input = saved_entry2.datas["user_input"]
        else:
            user_input = jackup_save_data.get("user_input", {})
            
        if saved_entry2 and "boomdata" in saved_entry2.datas:
            boomdata = saved_entry2.datas["boomdata"]
        else:
            boomdata = jackup_save_data.get("boomdata", {})

        Mrigging = user_input.get("Mrigging", 0.00)
        Mhook = user_input.get("Mhook", 0.00)
        WCF = user_input.get("WCF", 0.00)
        WCFrigging = user_input.get("WCFrigging", 0.00)
        Mblock = user_input.get("Mblock", 0.00)
        DAF = user_input.get("DAF", 1)  # Default to 1 to avoid division by zero
        DAFincl = user_input.get("DAFincl", 1)  # Default to 1 to avoid division by zer
        # Assuming filtered_cargo is already populated and is a dictionary
        crane_data_to_front = (
            saved_entry2.crane_data if saved_entry2 else filtered_cargo
        )
        crane_data = ship["crane_data.json"]

        # Check if crane_data_to_front is None or empty and provide default values
        if not crane_data_to_front:
            crane_data_to_front = {
                "weight": 0,  # Default weight
                "lcg": 0,  # Default lcg
                "tcg": 0,  # Default tcg
                "vcg": 0,  # Default vcg
                "name": "SELECT WEIGHT HERE",  # Adding a default name
            }

        # Populate cargo_data directly from crane_data_to_front (filtered_cargo) -
        # without assuming a list
        cargo_data = {
            "crane_1": [
                crane_data_to_front.get("weight", 0),  # Fetch weight(default to 0)
                crane_data_to_front.get("lcg", 0),  # Fetch lcg or default to 0
                crane_data_to_front.get("tcg", 0),  # Fetch tcg or default to 0
                crane_data_to_front.get("vcg", 0),  # Fetch vcg or default to 0
            ]
        }

        if (
            not crane_data_to_front
            or crane_data_to_front.get("name", "") == "SELECT WEIGHT HERE"
        ):
            # Set the default crane angles to zero when there's no valid cargo name
            crane_orientations = {
                "crane_1": {
                    "slew_angle": 0,
                    "boom_angle": 0,
                    "required_outreach": 0,
                    "weight": 0,
                    "required_swl_table": get_swl_table(ship.get("Crane Data", {})),
                }
            }
            calculated_output_values = {
                "SHLbe": 0.0,
                "SHLub": 0.0,
                "SWLreq": 0.0,
                "SWL": 0.0,
                "SWLcorr": 0.0,
                "UCl": 0.0,
                "Rm": 0.0,
                "UCr": 0.0,
            }
        else:

            # Call the function with cargo_data
            result = calculate_crane_and_swl(
                ship,
                crane_data,
                cargo_data,
                Mrigging,
                Mhook,
                WCFrigging,
                WCF,
                DAF,
                DAFincl,
                Mblock,
                boomdata,
            )
            # Access the crane orientations and required SWL values from the result
            crane_orientations = result["crane_orientations"]
            calculated_output_values = result["calculated_output_values"]

        # Append drilling_platform values to weight_data
        # if isinstance(weight_data, list):
        #     # Add drilling_platform to weight_data as a new dictionary entry
        #     weight_data.append(
        #         {
        #             "name": "drilling_platform",
        #             "weight": lcg_value.get("weight", 0),
        #             "lcg": lcg_value.get("lcg", 0),
        #             "tcg": lcg_value.get("tcg", 0),
        #             "vcg": lcg_value.get("vcg", 0),
        #             "color": "white",
        #             "diameter": 0,
        #             "height": 10,
        #             "length": 10,
        #             "mesh_name": "nickel",
        #             "breadth": 10,
        #             "x": 0.1,
        #             "y": 0.2,
        #             "z": 0.3,
        #         }
        #     )

        # Retrieve jackup_data from saved_data_cargo_and_tank if available
        jackup_data2 = (
            saved_entry2.jackup_data
            if saved_entry2
            else jackup_save_data.get("jackup_data", {})
        )
        lcg_value = (
            saved_entry2.lcg_value
            if saved_entry2
            else jackup_save_data.get("drilling_platform")
        )

        response_data = {
            "tank_vals": tank_vals,
            "tank_weight_data": tank_weight_data,
            "lightship_data": lightship_weight_data,
            "fixed_weight_data": fixed_weight_data,
            "dead_weight_data": dead_weight_data,
            "total_weight_data": total_weight_data,
            "weight_data": weight_data,
            "leg_data": leg_data,
            "lever_coordinates": lever_coordinates,
            "jackup_data": jackup_data2,  # Include jackup_data in the response
            "pedestal_base_point": [pedestal_base_x, pedestal_base_y, pedestal_base_z],
            "boom_base_point": [boom_base_x, boom_base_y, boom_base_z],
            "crane_orientations": crane_orientations,
            "crane_data_to_front": crane_data_to_front,
            "drilling_platform": lcg_value,  # Return LCG value in the response
            "is_editable": is_editable,  # for restrcting certain users
            "user_input": user_input,
            "calculated_output_values": calculated_output_values,
        }

        return JsonResponse(response_data)
    except Pickle.DoesNotExist:
        return HttpResponse("Pickle object not found", status=404)


def get_all_vessel_names_for_jackup(request):
    """
    Get all vessel names and images belonging to the logged-in user.

    Retrieves the names and images of all vessel objects associated
    with the logged-in user.
    These names and images are extracted from the Pickle objects
    related to the user's ID.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing a list of vessels with
      their names and images under the key "vessels".
    """
    # Filter the Pickle objects by the logged-in user's ID
    user_vessels = Pickle.objects.filter(
        user_id=request.user.id, vessel_type__in=["L", "LC"]
    ).values("name", "image")

    vessels = []
    for vessel in user_vessels:
        image_base64 = None

        # Convert the image BLOB to a base64 string
        if vessel["image"]:  # Check if the image column has data
            image_base64 = base64.b64encode(vessel["image"]).decode("utf-8")

        vessels.append({"name": vessel["name"], "image": image_base64})

    return JsonResponse({"vessels": vessels})




def get_all_vessel_names_for_lifting(request):
    """
    Get all vessel names and images belonging to the logged-in user.

    Retrieves the names and images of all vessel objects associated
    with the logged-in user.
    These names and images are extracted from the Pickle objects
    related to the user's ID.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing a list of vessels with
      their names and images under the key "vessels".
    """
    # Filter the Pickle objects by the logged-in user's ID
    user_vessels = Pickle.objects.filter(
        user_id=request.user.id, vessel_type__in=["C", "LC"]
    ).values("name", "image")

    vessels = []
    for vessel in user_vessels:
        image_base64 = None

        # Convert the image BLOB to a base64 string
        if vessel["image"]:  # Check if the image column has data
            image_base64 = base64.b64encode(vessel["image"]).decode("utf-8")

        vessels.append({"name": vessel["name"], "image": image_base64})

    return JsonResponse({"vessels": vessels})



def solve_crane_get_data(request):
    """
    Main function to calculate ship stability and criteria.
    """
    tank_data = {}
    is_editable = True  # Default to editable
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST method is allowed")

    try:
        user = request.user
        data = json.loads(request.body)
        pickle_name = data.get("pickle_name")
        worksheet_data = data.get("name")
        restricted_users = ["testuser", "dtestuser2"]
        jackup_save_data = json.loads(request.body) if request.body else {}
        weight_data = jackup_save_data.get("cargo", {})
        cargoNameInCrane = jackup_save_data.get("selectedCargoInCrane")
        if not cargoNameInCrane:  # If None or empty
            cargoNameInCrane = "SELECT WEIGHT HERE"

        lcg_value = jackup_save_data.get("drilling_platform")
        tank_data = jackup_save_data.get("tank", {})
        # Extract lcg, tcg, vcg, weight, and name from weight_data
        valid_weight_data = [item for item in weight_data if "name" in item]
        cargo_list = []  # Use a list to store cargo info

        # Loop through weight_data and add each cargo's info to the cargo_list
        for cargo in valid_weight_data:
            cargo_name = cargo.get("name", "")
            if cargo_name.lower() == "drilling platform":
                continue  # Skip this cargo if the name is "drilling platform"

            cargo_info = {
                "name": cargo_name,
                "weight": cargo.get("weight", 1),
                "lcg": cargo.get("lcg", 0),
                "tcg": cargo.get("tcg", 0),
                "vcg": cargo.get("vcg", 0),
            }
            # Append each cargo's info to the list
            cargo_list.append(cargo_info)

        # After processing weight_data, append the drilling_platform -
        # values to cargo_list
        if user.username in restricted_users:
            is_editable = False
        if lcg_value:
            cargo_list.append(lcg_value)  # Add drilling_platform info to the list

        filtered_cargo = {}

        # Filter the cargo data to match the name of the cargo in the crane
        if cargoNameInCrane == "SELECT WEIGHT HERE":
            filtered_cargo = {
                "name": "SELECT WEIGHT HERE",
                "weight": 0,
                "lcg": 0,
                "tcg": 0,
                "vcg": 0,
            }
        else:
            # Filter the cargo data to match the name of the cargo in the crane
            filtered_cargo = next(
                (
                    cargo
                    for cargo in cargo_list
                    if cargo.get("name") == cargoNameInCrane
                ),
                {},
            )
        if not filtered_cargo:
            filtered_cargo = {
                "name": "SELECT WEIGHT HERE",
                "weight": 0,
                "lcg": 0,
                "tcg": 0,
                "vcg": 0,
            }

        # lcg_value = jackup_save_data.get("drilling_platform")

        if jackup_save_data:
            jackup_data = jackup_save_data.get("jackup_data", {})

            datas = {
                key: value
                for key, value in jackup_save_data.items()
                if key not in ["pickle_name", "name", "jackup_data"]
            }
            if not isinstance(datas, dict) or not isinstance(jackup_data, dict):
                return HttpResponseBadRequest("Invalid JSON format")

            # Saving or updating the jackup_save_data in the database
            if worksheet_data:
                saved_entry = saved_data_cargo_and_tank.objects.filter(
                    user=request.user.id, name=worksheet_data, pickle_name=pickle_name
                ).first()
                if saved_entry:
                    saved_entry.datas["tank"] = tank_data
                    saved_entry.datas["cargo"] = datas["cargo"]
                    saved_entry.datas["user_input"] = datas["user_input"]
                    saved_entry.datas["selectedCargoInCrane"] = datas[
                        "selectedCargoInCrane"
                    ]
                    saved_entry.datas["boomdata"] = datas["boomdata"]

                    # saved_entry.datas = datas

                    saved_entry.jackup_data = jackup_data
                    # Save LCG value to the database
                    for key in ["lcg", "weight", "tcg", "vcg", "lcg_a", "lcg_f"]:
                        if lcg_value.get(key) is None:
                            existing_value = (
                                saved_entry.lcg_value.get(key)
                                if saved_entry.lcg_value
                                else None
                            )
                            if existing_value is not None:
                                lcg_value[key] = (
                                    existing_value  # Set from existing saved value
                                )
                            else:
                                lcg_value[key] = 0

                    saved_entry.lcg_value = lcg_value

                    # Now update the crane_data if it has changed or is new
                    if filtered_cargo and (
                        not saved_entry.crane_data
                        or filtered_cargo != saved_entry.crane_data
                    ):
                        saved_entry.crane_data = filtered_cargo

                    # Save the updated entry
                    saved_entry.save()

                else:
                    # Handle the case where the selected_name does not exist in the database
                    new_entry = saved_data_cargo_and_tank(
                        name=worksheet_data,
                        datas=datas,
                        jackup_data=jackup_data,
                        lcg_value=lcg_value,  # Save LCG value in a new entry
                        crane_data=filtered_cargo,  # Save crane_data in a new entry
                    )
                    new_entry.save()
            else:
                return JsonResponse({"error": "Selected name not provided"}, status=400)

    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # Use valid_weight_data for processing weight data
    saved_entry = saved_data_cargo_and_tank.objects.filter(
        user=request.user.id, pickle_name=pickle_name, name=worksheet_data
    ).first()
    valid_weight_data = []

    try:
        pickle_obj = Pickle.objects.get(
            user=request.user, name=pickle_name, user_id=request.user.id
        )

        ship, error = get_ship_from_pickle(pickle_obj.data)
        if error:
            return HttpResponse(error)
        
        if isinstance(lcg_value, dict):
            weight_data.append(lcg_value)

        valid_weight_data = [item for item in weight_data if "weight" in item]


        # Calculate fixed weight data
        (
            fixed_weight,
            fixed_weight_lcg,
            fixed_weight_tcg,
            fixed_weight_vcg,
        ) = get_fixed_weight(valid_weight_data)

        fixed_weight_data = {
            "total_weight": fixed_weight,
            "total_lcg": fixed_weight_lcg,
            "total_tcg": fixed_weight_tcg,
            "total_vcg": fixed_weight_vcg,
        }

        # Calculate lightship weight data
        (
            lightship_weight,
            lightship_lcg,
            lightship_tcg,
            lightship_vcg,
        ) = get_lightship_weight(ship)

        lightship_weight_data = {
            "total_weight": lightship_weight,
            "total_lcg": lightship_lcg,
            "total_tcg": lightship_tcg,
            "total_vcg": lightship_vcg,
        }

        # Calculate tank weight data
        tank_vals, (tank_weight, tank_lcg, tank_tcg, tank_vcg, tank_fsm) = (
            get_tank_weight(ship, tank_data)
        )
        tank_weight_data = {
            "total_weight": tank_weight,
            "total_lcg": tank_lcg,
            "total_tcg": tank_tcg,
            "total_vcg": tank_vcg,
        }

        # Calculate dead weight data
        dead_weight = tank_weight + fixed_weight
        if dead_weight != 0:
            dead_weight_lcg = (
                tank_weight * tank_lcg + fixed_weight * fixed_weight_lcg
            ) / dead_weight
            dead_weight_tcg = (
                tank_weight * tank_tcg + fixed_weight * fixed_weight_tcg
            ) / dead_weight
            dead_weight_vcg = (
                tank_weight * tank_vcg + fixed_weight * fixed_weight_vcg
            ) / dead_weight
        else:
            dead_weight_lcg = 0
            dead_weight_tcg = 0
            dead_weight_vcg = 0

        dead_weight_data = {
            "total_weight": dead_weight,
            "total_lcg": dead_weight_lcg,
            "total_tcg": dead_weight_tcg,
            "total_vcg": dead_weight_vcg,
        }

        # Calculate total weight data
        total_weight = dead_weight + lightship_weight
        if total_weight != 0:
            total_weight_lcg = (
                dead_weight * dead_weight_lcg + lightship_weight * lightship_lcg
            ) / total_weight
            total_weight_tcg = (
                dead_weight * dead_weight_tcg + lightship_weight * lightship_tcg
            ) / total_weight
            total_weight_vcg = (
                dead_weight * dead_weight_vcg + lightship_weight * lightship_vcg
            ) / total_weight
        else:
            total_weight_lcg = 0
            total_weight_tcg = 0
            total_weight_vcg = 0

        total_weight_data = {
            "total_weight": total_weight,
            "total_lcg": total_weight_lcg,
            "total_tcg": total_weight_tcg,
            "total_vcg": total_weight_vcg,
        }

        [pedestal_base_x, pedestal_base_y, pedestal_base_z] = ship["crane_data.json"][
            "crane_1"
        ][0]["pedestal_base_point"]

        [boom_base_x, boom_base_y, boom_base_z] = ship["crane_data.json"]["crane_1"][0][
            "boom_base_point"
        ]
        # Correct VCG
        vcg_corr = total_weight_vcg - tank_fsm / total_weight

        # Calculate leg load distribution
        # leg_data, lever_coordinates = get_leg_load_distribution(
        #     ship=ship,
        #     total_weight=total_weight,
        #     total_lcg=total_weight_lcg,
        #     total_tcg=total_weight_tcg,
        # )
        saved_entry2 = saved_data_cargo_and_tank.objects.filter(
            user=request.user.id, pickle_name=pickle_name, name=worksheet_data
        ).first()
        if saved_entry2 and "user_input" in saved_entry2.datas:
            user_input = saved_entry2.datas["user_input"]
        else:
            user_input = jackup_save_data.get("user_input", {})
        if saved_entry2 and "boomdata" in saved_entry2.datas:
            boomdata = saved_entry2.datas["boomdata"]
        else:
            boomdata = jackup_save_data.get("boomdata", {})

        Mrigging = user_input.get("Mrigging", 0.00)
        Mhook = user_input.get("Mhook", 0.00)
        WCF = user_input.get("WCF", 0.00)
        WCFrigging = user_input.get("WCFrigging", 0.00)
        Mblock = user_input.get("Mblock", 0.00)
        DAF = user_input.get("DAF", 1)  # Default to 1 to avoid division by zero
        DAFincl = user_input.get("DAFincl", 1)  # Default to 1 to avoid division by zer

        # Assuming filtered_cargo is already populated and is a dictionary
        crane_data_to_front = (
            saved_entry2.crane_data if saved_entry2 else filtered_cargo
        )
        crane_data = ship["crane_data.json"]

        # Check if crane_data_to_front is None or empty and provide default values
        if not crane_data_to_front:
            crane_data_to_front = {
                "weight": 0,  # Default weight
                "lcg": 0,  # Default lcg
                "tcg": 0,  # Default tcg
                "vcg": 0,  # Default vcg
                "name": "SELECT WEIGHT HERE",  # Adding a default name
            }

        # Populate cargo_data directly from crane_data_to_front (filtered_cargo) -
        # without assuming a list
        cargo_data = {
            "crane_1": [
                crane_data_to_front.get("weight", 0),  # Fetch weight(default to 0)
                crane_data_to_front.get("lcg", 0),  # Fetch lcg or default to 0
                crane_data_to_front.get("tcg", 0),  # Fetch tcg or default to 0
                crane_data_to_front.get("vcg", 0),  # Fetch vcg or default to 0
            ]
        }
        if (
            not crane_data_to_front
            or crane_data_to_front.get("name", "") == "SELECT WEIGHT HERE"
        ):
            # Set the default crane angles to zero when there's no valid cargo name
            crane_orientations = {
                "crane_1": {
                    "slew_angle": 0,
                    "boom_angle": 0,
                    "required_outreach": 0,
                    "weight": 0,
                    "required_swl_table": get_swl_table(ship.get("Crane Data", {})),
                }
            }
            calculated_output_values = {
                "SHLbe": 0.0,
                "SHLub": 0.0,
                "SWLreq": 0.0,
                "SWL": 0.0,
                "SWLcorr": 0.0,
                "UCl": 0.0,
                "Rm": 0.0,
                "UCr": 0.0,
            }

        else:

            result = calculate_crane_and_swl(
                ship,
                crane_data,
                cargo_data,
                Mrigging,
                Mhook,
                WCFrigging,
                WCF,
                DAF,
                DAFincl,
                Mblock,
                boomdata,
            )
            # Access the crane orientations and required SWL values from the result
            crane_orientations = result["crane_orientations"]
            calculated_output_values = result["calculated_output_values"]

            # Append drilling_platform values to weight_data
            # if isinstance(weight_data, list):
            # Add drilling_platform to weight_data as a new dictionary entry
            weight_data.append(
                {
                    "name": "drilling_platform",
                    "weight": lcg_value.get("weight", 0),
                    "lcg": lcg_value.get("lcg", 0),
                    "tcg": lcg_value.get("tcg", 0),
                    "vcg": lcg_value.get("vcg", 0),
                    "lcg_a": lcg_value.get("lcg_a", 0),
                    "lcg_f": lcg_value.get("lcg_f", 0),
                    "color": "white",
                    "diameter": 0,
                    "height": 1,
                    "length": 1,
                    "mesh_name": "nickel",
                    "breadth": 1,
                    "x": 0.1,
                    "y": 0.2,
                    "z": 0.3,
                }
            )

        # Retrieve jackup_data from saved_data_cargo_and_tank if available
        # jackup_data2 = (
        #     saved_entry2.jackup_data
        #     if saved_entry2
        #     else jackup_save_data.get("jackup_data", {})
        # )
        lcg_value = (
            saved_entry2.lcg_value
            if saved_entry2
            else jackup_save_data.get("drilling_platform")
        )
        boom_working_modes = {}
        if "Crane Data" in ship:
            swl_table = ship["Crane Data"]
        if isinstance(swl_table, dict):
            for boom_name, boom_data in swl_table.items():
                if isinstance(boom_data, dict):
                    working_mode_dict = {}
                    for working_mode, file_dict in boom_data.items():
                        if isinstance(file_dict, dict):
                            csv_files = [
                                filename.replace(".csv", "")
                                for filename in file_dict.keys()
                                if isinstance(filename, str)
                                and filename.endswith(".csv")
                            ]
                            working_mode_dict[working_mode] = csv_files
                            boom_working_modes[boom_name] = working_mode_dict

        response_data = {
            "tank_vals": tank_vals,
            "tank_weight_data": tank_weight_data,
            "lightship_data": lightship_weight_data,
            "fixed_weight_data": fixed_weight_data,
            "dead_weight_data": dead_weight_data,
            "total_weight_data": total_weight_data,
            "weight_data": weight_data,
            "pedestal_base_point": [pedestal_base_x, pedestal_base_y, pedestal_base_z],
            "boom_base_point": [boom_base_x, boom_base_y, boom_base_z],
            "crane_orientations": crane_orientations,
            "crane_data_to_front": crane_data_to_front,
            "drilling_platform": lcg_value,  # Return LCG value in the response
            "is_editable": is_editable,  # for restrcting certain users
            "user_input": user_input,
            "calculated_output_values": calculated_output_values,
        }

        return JsonResponse(response_data)

    except Pickle.DoesNotExist:
        return HttpResponse("Pickle object not found", status=404)


def get_swl_table(crane_data):
    for boom_key in crane_data:
        for operation_key in crane_data[boom_key]:
            for csv_key, swl_table in crane_data[boom_key][operation_key].items():
                if csv_key.endswith(".csv"):
                    return swl_table.to_dict()
    return {}
