"""
This module manages operations related to vessels, including:
- Uploading and processing vessel-related pickle files.
- Retrieving vessel names and images.
- Handling vessel data visualization.
- CRUD operations on Pickle objects (representing vessels).
- Handling file uploads, including extracting & storing images from pickle files.
- Session management for vessel-related data.

Each function is associated with specific tasks such as data retrieval,
visualization, file handling, and database interactions, with appropriate
error handling for failed operations.
"""

import base64
import json
import pickle
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from .models import (
    Pickle,
    saved_data_cargo_and_tank,
)
from .views import spa   # use React SPA for HTML routes


# Declare variables
namep = []
ship = None
tank_data = {}
cargo_data = {}
save_data = {}
selected_name = None
global_cargo_data = None
selected_name = None

@csrf_exempt
@login_required  # Ensure the user is logged in
def get_all_vessel_names_for_vessel_database(request):
    """
    Get all vessel names and images belonging to the logged-in user.

    Retrieves the names and images of all vessel objects associated-
    with the logged-in user.
    These names and images are extracted from the saved_data_cargo_and_tank
    objects related to the user's ID.

    Parameters:
    - request (HttpRequest): The HTTP request object.

    Returns:
    - JsonResponse: JSON response containing a list of vessels with
        their names and images under the key "vessels".
    """
    # Filter the saved_data_cargo_and_tank objects by the logged-in user's ID
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

def vessel_display(request):
    if request.method == "GET":
        return spa(request)
    return JsonResponse({"detail": "Method not allowed"}, status=405)



@csrf_exempt
def vessel_view(request):
    """
    View function to handle vessel data visualization.
 
    Handles both POST and GET requests:
    - POST: Retrieves the pickle file name from the request, processes the
      Pickle object to extract vessel data and model information, and
      stores this data in the session. Renders the vessel view template with
      the processed data.
    - GET: Retrieves the vessel data and models with textures from the session
      and renders the vessel view template.
 
    Args:
        request (HttpRequest): The HTTP request object.
 
    Returns:
        HttpResponse: Rendered vessel view template with the appropriate data.
        HttpResponse: Error response for invalid or unhandled requests.
    Raises:
        Pickle.DoesNotExist: if the requested Pickle object is not found.
        Exception: Catches any other exceptions and returns an error message.
    """
    if request.method == "GET":
 
        try:
            pickle_file_name = request.GET.get("pickle_name")  # instead of body
            if not pickle_file_name:
                return JsonResponse({"error": "Missing pickle_name"}, status=400)

            pickle_obj = get_pickle_object(pickle_file_name, request.user)

            vessel_data_dict_json, models_with_textures_json = process_pickle_data(pickle_obj)

            return JsonResponse(
                {
                    "models_with_textures": models_with_textures_json,
                    "vessel_data_dict": vessel_data_dict_json,
                    "pickle_name": pickle_file_name,
                }
            )
        except Pickle.DoesNotExist:
            return HttpResponse("Pickle not found", status=404)
 
        except Exception as e:
            return HttpResponse(f"An error occurred: {str(e)}", status=500)
 
    # elif request.method == "GET":
    #     if (
    #         "vessel_data_dict" in request.session
    #         and "models_with_textures" in request.session
    #     ):
    #         vessel_data_dict_json = request.session["vessel_data_dict"]
    #         models_with_textures_json = request.session["models_with_textures"]
 
    #         return JsonResponse(
    #             {
    #                 "models_with_textures": models_with_textures_json,
    #                 "vessel_data_dict": vessel_data_dict_json,
    #             },
    #         )
 
    #     return HttpResponse("Invalid request", status=400)
 
    # return HttpResponse("Method not allowed", status=405)


def favicon_view(request):
    """
    View function to handle requests for the favicon.

    This function returns a 204 No Content response
    since no favicon is provided.
    """
    return HttpResponse(status=204)  # No Content response

@csrf_exempt
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

@csrf_exempt
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

@csrf_exempt
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


@login_required
@csrf_exempt
def upload_file(request):
    """
    Handle the file upload process.
 
    This function handles POST requests to upload a file.
    It checks if a file with the same name already exists for the user and,
    if not, creates a new Pickle object to store the file.
    The function also processes the file's contents and extracts image data,
    which is returned in the response.
 
    Args:
        request (HttpRequest): The HTTP request object containing the
            uploaded file.
 
    Returns:
        JsonResponse: A JSON response indicating success or error,
            and any extracted image data.
    """
    if request.method == "POST":
        # Ensure a file was actually uploaded
        if "uploaded_file" not in request.FILES:
            return JsonResponse(
                {"success": False, "message": "No file was provided"}, status=400
            )
 
        uploaded_file = request.FILES["uploaded_file"]
        file_name = uploaded_file.name
 
        # Check if a file with the same name already exists for this user
        if Pickle.objects.filter(name=file_name, user=request.user).exists():
            return JsonResponse(
                {
                    "success": False,
                    "message": "A file with this name already exists!",
                },
                status=400,
            )
 
        # Attempt to process the file
        try:
            file_data = uploaded_file.read()
 
            # Attempt to unpickle
            try:
                pickle_data = pickle.loads(file_data)
            except pickle.UnpicklingError:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Failed to unpickle the uploaded file",
                    },
                    status=400,
                )
 
            # Attempt to extract 'vessel.png' if it exists within '.' key
            vessel_image_data = None
            if "vessel.png" in pickle_data:
                vessel_image_data = pickle_data["vessel.png"]
           
           
            leg_data_exists = False
            if "ship_data.json" in pickle_data:
                ship_data_json = pickle_data["ship_data.json"]
                if "leg_data" in ship_data_json:  # Direct key check instead of string conversion
                    leg_data_exists = True
 
            crane_data_exists = "crane_data" in str(pickle_data)
 
            # Determine vessel type
            if crane_data_exists and leg_data_exists:
                vessel_type = 'LC'
            elif crane_data_exists:
                vessel_type = 'C'
            elif leg_data_exists:
                vessel_type = 'L'
            else:
                vessel_type = 'N'
 
            # Create a new record in your Pickle model
            new_pickle = Pickle(
                name=file_name,
                data=file_data,
                user=request.user,
                image=vessel_image_data,  # Save vessel.png as a BLOB if you want
                vessel_type=vessel_type
            )
            new_pickle.save()
 
 
           
            # Build base64 images list
            image_base64_list = []
            if vessel_image_data:
                image_base64 = base64.b64encode(vessel_image_data).decode("utf-8")
                image_base64_list.append({"file_name": file_name, "data": image_base64})
 
            # Response data
            response_data = {
                "success": True,
                "message": "File uploaded and processed",
                "file_name": file_name,
                "images": image_base64_list,
            }
 
            # If no vessel image was found
            if not image_base64_list:
                response_data["message"] = "File uploaded but no vessel.png found"
 
            return JsonResponse(response_data)
 
        except Exception as e:
            # Catch any other unexpected errors
            return JsonResponse({"success": False, "message": str(e)}, status=500)
 
    # If not POST, return a simple error
    return JsonResponse(
        {"success": False, "message": "Invalid request method"}, status=405
    )
@csrf_exempt
@login_required
def index2(request, vessel_name=None):
    """
    View function for managing vessels.

    GET: Retrieves all vessels (pickles) and renders them in the
      index.html template.

    POST: Creates a new vessel (pickle) with the given name if it
      doesn't already exist.

    DELETE: Deletes a vessel (pickle) with the given name.

    Parameters:
    - request (HttpRequest): The HTTP request object.
    - vessel_name (str, optional): The name of the vessel to be deleted
      (for DELETE method).

    Returns:
    - HttpResponse: Rendered index.html template with all pickles (for GET).
    - JsonResponse: JSON response indicating success or failure (for POST
      and DELETE).
    """
    user_id = request.user.id
    if request.method == "GET":
        pickles = Pickle.objects.filter(user=request.user)
        pickles_list = list(pickles.values())  # Convert queryset to list
        return JsonResponse(pickles_list, safe=False)

    elif request.method == "POST":
        action = request.POST.get("action")
        vessel_name = request.POST.get("name")

        if action == "undo_delete":
            if vessel_name:
                Pickle.objects.create(user=request.user, name=vessel_name)
                return JsonResponse({"success": True, "message": "Vessel restored."})
            else:
                return HttpResponseBadRequest("Vessel name is required for undo.")

        elif action == "create":
            if vessel_name:
                Pickle.objects.create(user=request.user, name=vessel_name)
                return JsonResponse({"success": True, "message": "Vessel created."})
            else:
                return HttpResponseBadRequest("Vessel name is required for creation.")

    elif request.method == "DELETE" and vessel_name:
        try:
            vessel = Pickle.objects.get(
                user=request.user, name=vessel_name, user_id=user_id
            )
            vessel.delete()
            saved_data_cargo_and_tank.objects.filter(pickle_name=vessel_name).delete()
            return JsonResponse(
                {"success": True, "message": "Vessel deleted successfully."}
            )
        except Pickle.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "Vessel not found."}, status=404
            )

    return HttpResponseBadRequest("Invalid request method or missing data.")
