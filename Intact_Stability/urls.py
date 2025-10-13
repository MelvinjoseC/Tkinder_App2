"""
URL configuration for Loading_Computer project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from . import views
from .login_api import (
    CustomLogoutView,
    login_view,
    send_otp,
    verify_otp,
    disabled_check_auth_key,
    # check_auth_key,
)
from .report_generator import generate_pdf
from .jackup_report import generate_pdf_jackup
from .lifting_report import generate_pdf_lifting

from .cargo_api import (
    datadisplay,
    get_model,
    intact_stability_cargo_detail,
    cargo_names,
    cargo_display,
)
from .vessel_view_api import (
    get_all_vessel_names_for_vessel_database,
    vessel_view,
    upload_file,
    index2,
    favicon_view,
    vessel_display,
)

from .stability_api import (
    get_all_vessel_names_for_intactstability,
    get_saved_names,
    create_worksheet,
    get_worksheet_data,
    edit_worksheet,
    duplicate_worksheet,
    delete_worksheet,
    get_pickle_name,
    new_page,
    get_data_by_name,
    solve,
    get_cargo_names,
    get_cargoname_data,
    get_cargo_mesh_file,
    delete_cargo_entry,
    solve_jackup_get_data,
    get_all_vessel_names_for_jackup,
    get_all_vessel_names_for_lifting,
    solve_crane_get_data,

)

urlpatterns = [
    path("login/", login_view, name="login"),  # Login page as the default view
    path("home", views.index, name="home"),  # Home page (or other views)
    path("datadisplay/<str:cargo_name>/", datadisplay, name="datadisplay"),
    path("get_obj_file/<str:CARGO_NAME>/", get_model, name="get_model"),
    path("cargo/<str:NAME>/", intact_stability_cargo_detail, name="cargo-detail"),
    # path('Vessels/', views. get_obj_data, name='Vessels'),
    path("upload_file", upload_file, name="upload_file"),
    path("solve", solve, name="solve"),
    path("solve_jackup_get_data/", solve_jackup_get_data, name="solve_jackup"),
    path("solve_crane_get_data/", solve_crane_get_data, name="solve_crane"),
    path("get_cargo_names", get_cargo_names, name="get_cargo_names"),
    path("get_cargoname_data", get_cargoname_data, name="get_cargoname_data"),
    path("verify-otp/", verify_otp, name="verify_otp"),
    path("send-otp/", send_otp, name="send_otp"),
    path("api/check-auth-key/", disabled_check_auth_key, name="check_auth_key_disabled"),
    path(
        "get_all_vessel_names_for_vessel_database",
        get_all_vessel_names_for_vessel_database,
        name="get_all_vessel_names",
    ),
    path(
        "get_all_vessel_names_for_intactstability/",
        get_all_vessel_names_for_intactstability,
        name="get_all_vessel_names",
    ),
    path("save_screenshot/", views.save_screenshot, name="save_screenshot"),
    path("get_cargo_mesh_file", get_cargo_mesh_file, name="get_cargo_mesh_file"),
    path("create_worksheet/", create_worksheet, name="create_worksheet"),
    path("get_saved_names/", get_saved_names, name="get_saved_names"),
    path("get_data_by_name/", get_data_by_name, name="get_data_by_name"),
    path("delete_vessel/<str:vessel_name>/", index2, name="delete_vessel"),
    path("delete_worksheet/", delete_worksheet, name="delete_worksheet"),
    path("delete_cargo_entry/", delete_cargo_entry, name="delete_cargo_entry"),
    path("pdf-generation-url/", generate_pdf, name="generate_pdf"),
    path("pdf-generation-url-jackup/", generate_pdf_jackup, name="generate_pdf_jackup"),
    path("pdf-generation-url-lifting/", generate_pdf_lifting, name="generate_pdf_lifting"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("api/get-pickle-name/", get_pickle_name, name="get_pickle_name"),
    path("<str:pickle_name>/<str:name>/", new_page, name="new_page"),
    path("cargo-names", cargo_names, name="cargo-names"),
    path("vessel_view/", vessel_view, name="open_page"),
    path("edit_worksheet/", edit_worksheet, name="edit_worksheet"),
    path("get_worksheet_data/", get_worksheet_data, name="get_worksheet_data"),
    path("duplicate_worksheet/", duplicate_worksheet, name="duplicate_worksheet"),
    path("favicon.ico", favicon_view),
    path(
        "get_all_vessel_names_for_jackup/",
        get_all_vessel_names_for_jackup,
        name="get_all_vessel_names_for_jackup",
    ),
    path(
        "get_all_vessel_names_for_lifting/",
        get_all_vessel_names_for_lifting,
        name="get_all_vessel_names_for_lifting",
    ),
    path("cargo_display", cargo_display, name="cargo_display"),
    path("vessel_display", vessel_display, name="vessel_display"),

]
