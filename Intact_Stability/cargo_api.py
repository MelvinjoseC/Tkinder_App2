"""
Handles cargo data management in the Django app. Provides views for:
- Retrieving and updating cargo information (e.g., name, dimensions, weight).
- Uploading cargo mesh files.
- Fetching table names and cargo details.

Requires user authentication for certain views. Returns JSON and binary responses.
"""

import base64
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
    QueryDict
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .models import (
    Cargo,
    cargo_template,
)
import json
from .views import spa

# Declare variables
cargo_data = {}
save_data = {}


def cargo_names(request):
    """
    Retrieve a list of all cargo names.

    This function handles GET requests and returns a JSON response
    containing a list of all cargo names in the Cargo model.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response with the list of cargo names.
    """
    if request.method == "GET":
        cargos = Cargo.objects.all().values_list("CARGO_NAME", flat=True)
        return JsonResponse(list(cargos), safe=False)


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
def cargo_display(request):
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
        accept = request.headers.get("Accept", "")
        if "text/html" in accept:
            return spa(request)

    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    if request.method == "GET":
        user_cargos = Cargo.objects.filter(user=request.user)
        return JsonResponse({"cargos": list(user_cargos.values("CARGO_NAME"))})

    elif request.method == "POST":
        action = request.POST.get("action")
        cargo_name = request.POST.get("CARGO_NAME")

        if not cargo_name:
            return JsonResponse(
                {"success": False, "message": "Cargo name is required."}, status=400
            )

        if action == "undo_delete":
            new_cargo = Cargo.objects.create(CARGO_NAME=cargo_name, user=request.user)
            return JsonResponse(
                {"success": True, "message": "Cargo restored successfully."}
            )

        def generate_unique_name(original_name):
            """
            Generate a new unique cargo name by appending a version number
            to the original name.

            Parameters:
            - original_name (str): The original cargo name.

            Returns:
            - str: A new unique cargo name.
            """
            version = 1
            new_name = f"{original_name}{version}"
            while Cargo.objects.filter(CARGO_NAME=new_name, user=request.user).exists():
                version += 1
                new_name = f"{original_name}{version}"
            return new_name

        if Cargo.objects.filter(CARGO_NAME=cargo_name, user=request.user).exists():
            cargo_name = generate_unique_name(cargo_name)

        new_cargo = Cargo(CARGO_NAME=cargo_name, user=request.user)
        new_cargo.save()
        return JsonResponse({"success": True, "new_cargo_name": cargo_name})

    elif request.method == "DELETE":
        try:
            # Parse JSON data from the body
            data = json.loads(request.body)
            cargo_name = data.get("CARGO_NAME")

            if not cargo_name:
                return JsonResponse(
                    {"success": False, "message": "Cargo name is required."}, status=400
                )

            cargo = Cargo.objects.filter(CARGO_NAME=cargo_name, user=request.user).first()
            if cargo:
                try:
                    cargo.delete()
                    return JsonResponse({"success": True})
                except Exception as e:
                    return JsonResponse(
                        {"success": False, "message": f"Error deleting cargo: {str(e)}"},
                        status=500,
                    )
            else:
                return JsonResponse({"success": False, "message": "Cargo not found."})
        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "message": "Invalid JSON format."}, status=400
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "message": f"Error: {str(e)}"}, status=500
            )


def datadisplay(request, cargo_name):
    """
    Display and update cargo data, including handling changes to CARGO_NAME.

    Retrieves cargo by cargo_name. If not found, returns error.

    POST:
    - Save uploaded "objFile" to MESHFILE and update MESH.
    - Update fields: CARGO_NAME, WEIGHT, LCG, VCG, TCG, LENGTH, BREADTH,
        HEIGHT, X1, X2, Y1, Y2, Z1, Z2.
    - Redirect to the updated CARGO_NAME URL if name changed.

    Parameters:
    - request (HttpRequest): The HTTP request object.
    - cargo_name (str): Name of cargo to display and update.

    Returns:
    - HttpResponse: Redirect to new URL if name changed,
        otherwise render template.
    - JsonResponse: Error message if cargo not found.
    """
    try:
        cargo = Cargo.objects.get(user=request.user, CARGO_NAME=cargo_name)
    except Cargo.DoesNotExist:
        return JsonResponse({"error": "Cargo not found."})

    if request.method == "POST":
        if "save_as" in request.POST:
            new_cargo_name = request.POST.get("new_cargo_name")
            if new_cargo_name:
                # Check if the new cargo name already exists
                if Cargo.objects.filter(
                    user=request.user, CARGO_NAME=new_cargo_name
                ).exists():
                    # Return a JsonResponse properly
                    return JsonResponse(
                        {
                            "error": "Cargo name already exists. Please choose a different name."
                        },
                        status=400,
                    )
                else:
                    new_cargo = Cargo(
                        user=request.user,
                        CARGO_NAME=new_cargo_name,
                        WEIGHT=request.POST.get("WEIGHT", cargo.WEIGHT),
                        LCG=request.POST.get("LCG", cargo.LCG),
                        VCG=request.POST.get("VCG", cargo.VCG),
                        TCG=request.POST.get("TCG", cargo.TCG),
                        LENGTH=request.POST.get("LENGTH", cargo.LENGTH),
                        BREADTH=request.POST.get("BREADTH", cargo.BREADTH),
                        HEIGHT=request.POST.get("HEIGHT", cargo.HEIGHT),
                        DIAMETER=request.POST.get("DIAMETER", cargo.DIAMETER),
                        X1=request.POST.get("X1", cargo.X1),
                        X2=request.POST.get("X2", cargo.X2),
                        Y1=request.POST.get("Y1", cargo.Y1),
                        Y2=request.POST.get("Y2", cargo.Y2),
                        Z1=request.POST.get("Z1", cargo.Z1),
                        Z2=request.POST.get("Z2", cargo.Z2),
                        COLOR=request.POST.get("selectedColor", cargo.COLOR),
                        MESHFILE=cargo.MESHFILE,
                        MESH=cargo.MESH,
                    )
                    new_cargo.save()
                    return JsonResponse({"success" : True, "message" : "Cargo saved as new entry","cargo_name":new_cargo_name})
        else:
            obj_file = request.FILES.get("objFile", None)
            if obj_file:
                cargo.MESHFILE = obj_file
                cargo.MESH = obj_file.name
                cargo.user_id = request.user.id
                cargo.save()

            new_cargo_name = request.POST.get("CARGO_NAME", None)
            if new_cargo_name and new_cargo_name != cargo.CARGO_NAME:
                if Cargo.objects.filter(
                    user=request.user, CARGO_NAME=new_cargo_name
                ).exists():
                    return JsonResponse(
                        {
                            "error": "Cargo name already exists. Please choose a different name."
                        },
                        status=400,
                    )
                cargo.CARGO_NAME = new_cargo_name

            # Update other fields
            cargo.WEIGHT = request.POST.get("WEIGHT", cargo.WEIGHT)
            cargo.LCG = request.POST.get("LCG", cargo.LCG)
            cargo.VCG = request.POST.get("VCG", cargo.VCG)
            cargo.TCG = request.POST.get("TCG", cargo.TCG)
            cargo.LENGTH = request.POST.get("LENGTH", cargo.LENGTH)
            cargo.BREADTH = request.POST.get("BREADTH", cargo.BREADTH)
            cargo.HEIGHT = request.POST.get("HEIGHT", cargo.HEIGHT)
            cargo.DIAMETER = request.POST.get("DIAMETER", cargo.DIAMETER)
            cargo.X1 = request.POST.get("X1", cargo.X1)
            cargo.X2 = request.POST.get("X2", cargo.X2)
            cargo.Y1 = request.POST.get("Y1", cargo.Y1)
            cargo.Y2 = request.POST.get("Y2", cargo.Y2)
            cargo.Z1 = request.POST.get("Z1", cargo.Z1)
            cargo.Z2 = request.POST.get("Z2", cargo.Z2)
            cargo.COLOR = request.POST.get("selectedColor", cargo.COLOR)
            cargo.user_id = request.user.id
            cargo.save()
            # if new_cargo_name != cargo_name:
            return JsonResponse({"success" : True,
                                    "message" : "Cargo updated successfully",
                                    "redirect" : new_cargo_name if new_cargo_name and new_cargo_name != cargo_name else None })
    return JsonResponse({
        "CARGO_NAME": cargo.CARGO_NAME,
        "WEIGHT": cargo.WEIGHT,
        "LCG": cargo.LCG,
        "VCG": cargo.VCG,
        "TCG": cargo.TCG,
        "LENGTH": cargo.LENGTH,
        "BREADTH": cargo.BREADTH,
        "HEIGHT": cargo.HEIGHT,
        "DIAMETER": cargo.DIAMETER,
        "X1": cargo.X1,
        "X2": cargo.X2,
        "Y1": cargo.Y1,
        "Y2": cargo.Y2,
        "Z1": cargo.Z1,
        "Z2": cargo.Z2,
        "COLOR": cargo.COLOR,
        "MESH": cargo.MESH,
    }) 




def get_model(request, CARGO_NAME):
    """
    Retrieve and download a cargo model file.

    Retrieves the Cargo object based on CARGO_NAME.
    If the cargo exists and has a MESHFILE, returns the MESHFILE data
      as a binary response
    with filename "{CARGO_NAME}.obj". If MESHFILE is empty,
      return an empty response.

    Parameters:
    - request (HttpRequest): The HTTP request object.
    - CARGO_NAME (str): Name of the cargo model to retrieve.

    Returns:
    - HttpResponse: Binary response with the cargo model data.
    - HttpResponse: Empty response if MESHFILE is empty.
    - HttpResponse: "Internal Server Error" response if an
        unexpected error occurs.
    """
    try:
        # Fetch the Cargo object based on CARGO_NAME
        cargo = get_object_or_404(Cargo, user=request.user, CARGO_NAME=CARGO_NAME)
        # Fetch the BLOB data from the `MESHFILE` field
        mesh_data = cargo.MESHFILE
        mesh_name = cargo.MESH
        length = cargo.LENGTH
        breadth = cargo.BREADTH
        height = cargo.HEIGHT
        diameter = cargo.DIAMETER
        color = cargo.COLOR if cargo.COLOR else "#ffffff"

        if mesh_data:
            # Return the MESHFILE data as a binary response
            response = HttpResponse(mesh_data, content_type="application/octet-stream")
            response["Content-Disposition"] = f'attachment; filename="{CARGO_NAME}.obj"'
            response["Cargo-Name"] = mesh_name
            response["Cargo-Length"] = str(length)
            response["Cargo-Breadth"] = str(breadth)
            response["Cargo-Height"] = str(height)
            response["Cargo-Color"] = color
            response["Cargo-Diameter"] = str(diameter)
            response["Access-Control-Expose-Headers"] = (
    "Cargo-Name, Content-Disposition"
)
            return response
        else:
            # Return an empty response if MESHFILE is empty
            return HttpResponse("")
    except Exception as e:
        print(f"Error: {e}")
        return HttpResponse("Internal Server Error", status=500)


def intact_stability_cargo_detail(request, NAME):
    """
    Retrieve details of a cargo template, including its name and mesh file.

    This view fetches a cargo template by its NAME from
    the `CargoTemplate` model and returns a JSON response containing
    the cargo's name and mesh file (if available).
    The mesh file is encoded in base64 format.

    Parameters:
    - request: The HTTP request object.
    - NAME: The name of the cargo template to retrieve.

    Returns:
    - JsonResponse: A JSON response containing the
        cargo data (name and mesh file).
    """
    cargo = get_object_or_404(cargo_template, NAME=NAME)
    cargo_data = {
        "name": cargo.NAME,
        "meshfile": (
            base64.b64encode(cargo.MESHFILE).decode("utf-8") if cargo.MESHFILE else None
        ),
    }
    return JsonResponse(cargo_data)
