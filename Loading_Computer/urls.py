# Loading_Computer/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

# Serve the built React SPA entry (index.html from frontend_build)
from Intact_Stability.views import spa

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("Intact_Stability.urls")),

    # Static XMLs via templates
    path("sitemap.xml", TemplateView.as_view(
        template_name="sitemap.xml", content_type="text/xml")),
    path("BingSiteAuth.xml", TemplateView.as_view(
        template_name="BingSiteAuth.xml", content_type="text/xml")),
]

# Serve built React public images (e.g., /img/NAME.webp)
urlpatterns += static("/img/", document_root=settings.BASE_DIR / "frontend_build" / "img")

# Catch-all for client-side routes in React (MUST be last).
# Excludes common server paths so it doesn't intercept them.
urlpatterns += [
    re_path(r"^(?!admin/|api/|static/|media/|sitemap\.xml$|BingSiteAuth\.xml$).*$", spa),
]

# In development, serve media files (optional)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
