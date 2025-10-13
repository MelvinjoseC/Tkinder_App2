"""
This module defines various models used in the application for managing
cargo data, user sessions, and saved data related to cargo, tanks, and
other configurations.

The models include:
- PyMySQLBinaryField: A custom field for storing binary data.
- Cargo: Stores details of cargo objects.
- Pickle: Stores binary data (blobs) associated with a user.
- saved_data_cargo_and_tank: Stores saved cargo and tank configurations.
- UserSession: Associates a session with a user.
- cargo_template: Represents a cargo template with an optional mesh file.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import FileExtensionValidator
from django.db import models
from pymysql import Binary


class PyMySQLBinaryField(models.BinaryField):
    """
    A custom BinaryField that uses PyMySQL's Binary class for
    storing binary data.
    This field overrides the default behavior to ensure binary data is properly
    formatted when being prepared for the database.
    """

    def get_db_prep_value(self, value, connection, prepared=False):
        # Let's use PyMySQL's own Binary class
        if value is not None:
            return Binary(value)
        return value


class Cargo(models.Model):
    """
    This model represents the details of a cargo object,
    including its dimensions, weight, center of gravity details, and
    mesh details for use in a 3D visualization system.
    It also handles file uploads and ensures that specific fields are
    correctly validated and saved.
    """

    # Basic cargo details
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    CARGO_NAME = models.CharField(max_length=255)
    WEIGHT = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    # Dimensions
    LENGTH = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    BREADTH = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    HEIGHT = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    DIAMETER = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    # Coordinate fields
    X1 = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    X2 = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    Y1 = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    Y2 = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    Z1 = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    Z2 = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    COLOR = models.CharField(max_length=255, null=True, blank=True)

    # Mesh details
    MESH = models.CharField(max_length=255, null=True, blank=True)
    MESHFILE = models.BinaryField(
        validators=[FileExtensionValidator(allowed_extensions=["obj"])],
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        if isinstance(self.MESHFILE, InMemoryUploadedFile):
            # Read the file content and assign it to MESHFILE
            self.MESHFILE = self.MESHFILE.read()
        super().save(*args, **kwargs)

    # Center of gravity details
    LCG = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    VCG = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    TCG = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    def __str__(self):
        return self.cargo_name


class Pickle(models.Model):
    """
    This model represents a Pickle object, used to store binary data
    (such as serialized or blob data) along with a reference to the user.
    Each Pickle object has a unique name and can be associated with a
    specific user.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    name = models.CharField(
        max_length=255, unique=True
    )  # Rename 'name' to 'cargo_name'
    data = models.BinaryField()  # Use BinaryField to store binary data (blob)
    image = models.BinaryField(null=True, blank=True)  # New field for the image
    vessel_type = models.CharField(max_length = 20)
    def __str__(self):
        return self.name

    class Meta:
        """
        Metadata options for the Pickle model.

        This class defines the database table name to be used for this model.
        """

        db_table = "pickle"


class saved_data_cargo_and_tank(models.Model):
    """
    This model is used to store saved data related to cargo and
    tank configurations.
    It includes fields for name, user association, and
    JSON fields to store various data like cargo and tank data, jackup data,
    crane data, and report information.
    Additionally, it includes a field for storing LCG values.
    """

    name = models.CharField(max_length=255, unique=True, blank=False, null=False)
    datas = models.JSONField()

    pickle_name = models.CharField(max_length=255)

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    report = models.JSONField(null=True, blank=True)
    jackup_data = models.JSONField()
    crane_data = models.JSONField()
    lcg_value = models.JSONField()  # New field to store LCG value

    class Meta:
        """
        Metadata options for the saved_data_cargo_and_tank model.

        This class specifies the name of the database table to use for
        this model.
        """

        db_table = "saved_data_cargo_and_tank"
        unique_together = ("user","pickle_name", "name")


class UserSession(models.Model):
    """
    This model represents a session associated with a user.
    It stores a one-to-one relationship between the user and a session key,
    allowing session management for authenticated users.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40)

    def __str__(self):
        return self.user.username


class cargo_template(models.Model):
    """
    This model represents a template for cargo objects.
    It stores the name of the cargo template and a mesh file (in .obj format),
    which can be used for 3D visualization.
    The mesh file is optional and can be left blank or null.
    """

    NAME = models.CharField(max_length=255)
    MESHFILE = models.BinaryField(
        validators=[FileExtensionValidator(allowed_extensions=["obj"])],
        null=True,
        blank=True,
    )
from django.db import models
from django.contrib.auth.models import User

class UserAuthKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # Django automatically creates user_id
    auth_key = models.CharField(max_length=255, unique=True)
    one_timep = models.CharField(max_length=6, blank=True, null=True)  # New OTP field

    def __str__(self):
        return f"User {self.user.id} - {self.auth_key}"


