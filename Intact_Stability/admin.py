from django.contrib import admin
from .models import Cargo
from .models import Cargo, Pickle, saved_data_cargo_and_tank


admin.site.register(Cargo)
admin.site.register(Pickle)
admin.site.register(saved_data_cargo_and_tank)

