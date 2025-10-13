import math
import numpy as np
from scipy.integrate import trapezoid
from scipy.interpolate import interp1d
from scipy.optimize import root_scalar


def get_criteria_data(
    gz_curve,
    length,
    depth,
    draft,
    breadth,
    total_weight,
    gmt_corr,
    max_draft,
    criteria_limits,
):
    """
    Function to compute criteria results

    Args:
        gz_curve: statical stability curve data
        length: length of the vessel
        depth: depth of the vessel
        draft: current floating draft
        breadth: breadth of the vessel
        total_weight: total weight acting on the vessel
        gmt_corr: meta-centric height after free surface correction
        max_draft: max draft of the vessel
        criteria_limits: user inputted limits


    Returns: Dict containing criteria results

    """

    x = [float(val) for val in list(gz_curve.keys())]
    y = list(gz_curve.values())

    interpolated_function = interp1d(
        x, y, kind="cubic", bounds_error=False, fill_value=None
    )

    range_of_stability, angle_of_loll = calculate_range_of_stability(x, y)

    criteria_data = {}

    # data block for cr 1
    cr_no = "cr_1"
    description = "Area under gz curve from 0° to 30°"
    required = 0.055
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    unit = "m rad"
    type = "stability criteria"
    attained = get_plot_area(x, y, 0, 30)
    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 2
    cr_no = "cr_2"
    description = "Area under gz curve from 0° to 40°"
    required = 0.09
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    unit = "m rad"
    type = "stability criteria"
    attained = get_plot_area(x, y, 0, 40)
    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 3
    cr_no = "cr_3"
    description = "Area under gz curve from 30° to 40°"
    required = 0.03
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    unit = "m rad"
    type = "stability criteria"
    attained = get_plot_area(x, y, 0, 40)
    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 4
    cr_no = "cr_4"
    description = "Righting lever at 30° angle of heel"
    required = 0.20
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    unit = "m"
    type = "stability criteria"

    attained = round(float(interpolated_function(30)), 2)
    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 5
    cr_no = "cr_5"
    description = "Angle of maximum GZ"
    required = 20.00
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    unit = "deg"
    type = "stability criteria"
    attained = get_max_righting_lever(interpolated_function, x)
    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 6
    cr_no = "cr_6"
    description = "Initial GM"

    required = 0.15
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    unit = "m"
    type = "stability criteria"
    attained = get_initial_gmt(x, y)
    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 7
    cr_no = "cr_7"
    description = "Range of stability"
    required = 36.00
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    unit = "deg"
    type = "stability criteria"
    attained = round(range_of_stability, 2)
    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 8
    cr_no = "cr_8"
    unit = "deg"
    type = "weather criteria"
    wind_load = 540
    required, attained = get_max_wind_load(
        length=length,
        depth=depth,
        draft=draft,
        breadth=breadth,
        wind_load=wind_load,
        total_weight=total_weight,
        gmt_corr=gmt_corr,
        angle_of_loll=angle_of_loll,
        max_draft=max_draft,
    )
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    description = "Heel angle under action of steady wind"
    status = "PASS" if attained <= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    # data block for cr 9

    cr_no = "cr_9"
    description = "GZ area exceeds wind heeling arm by 40%"
    unit = "m rad"
    type = "weather criteria"
    wind_velocity = 52
    windage_area = length * (depth - draft)
    windage_area_centroid_from_mid_draft = (
        draft / 2 + (((depth - draft) ** 2) / 2 * length) / windage_area
    )
    air_density = 1.225
    specific_gravity = 9.812
    windage_arm = (
        0.5
        * air_density
        * windage_area
        * windage_area_centroid_from_mid_draft
        * wind_velocity**2
        / (specific_gravity * 1000 * total_weight)
    )
    area_under_windage_arm_curve = windage_arm * range_of_stability * math.pi / 180
    required = round(1.4 * area_under_windage_arm_curve, 2)
    required = (
        criteria_limits[cr_no]["required"] if cr_no in criteria_limits else required
    )
    attained = get_plot_area(x, y, 0, range_of_stability)

    status = "PASS" if attained >= required else "FAIL"
    criteria_data[cr_no] = {
        "description": description,
        "required": required,
        "unit": unit,
        "type": type,
        "attained": attained,
        "status": status,
    }

    return criteria_data


def get_plot_area(x_vals, y_vals, start_x, end_x=None):
    """
    Function to get area under the curve
    Args:
        x_vals: angular values along the x direction
        y_vals: area values along the y direction
        start_x: starting angle
        end_x: ending angle

    Returns: float value showing area under the specified region

    """
    if end_x is None:
        end_x = x_vals[-1]

    x = np.array(x_vals)

    start_index = np.argmax(x >= start_x)
    end_index = np.argmax(x >= end_x) if end_x <= x[-1] else -1

    if start_index >= len(x) - 1 or start_index >= end_index:
        return 0

    area = trapezoid(
        y_vals[start_index : end_index + 1], x_vals[start_index : end_index + 1]
    ) * (math.pi / 180)

    area_in_m_rad = area * math.pi / 180

    return round(area_in_m_rad, 2)


def get_initial_gmt(x, y):
    """
    Function  to compute initial metacentric height
    Args:
        x: angular values along the x direction
        y: area values along the y direction

    Returns: Initial Metacentric Height

    """

    x1, x2 = x[:2]
    y1, y2 = y[:2]
    slope = (y2 - y1) / (x2 - x1)

    specified_x = 1 * 180 / math.pi

    initial_gmt = slope * specified_x + y1 - slope * x1

    return round(initial_gmt, 2)


def get_max_righting_lever(interpolated_function, x):
    """
    Function to get angle at which maximum righting lever occurs

    Args:
        interpolated_function: input scipy interpolation function
        x: angular values along the x direction

    Returns: Angle at which max righting lever occurs

    """

    interpolation_range = np.linspace(x[0], x[-1], 1000)

    interpolated_y = interpolated_function(interpolation_range)

    max_y_index = np.argmax(interpolated_y)
    x_max = interpolation_range[max_y_index]

    return round(x_max, 2)


def get_max_wind_load(
    length,
    depth,
    draft,
    breadth,
    wind_load,
    total_weight,
    gmt_corr,
    angle_of_loll,
    max_draft,
):
    """
    Function to compute heel angle due to steady wind

    Args:
        length: length of the vessel
        depth: depth of the vessel
        draft: current floating draft
        breadth: breadth of the vessel
        wind_load: wind load applicable in pascal
        total_weight: total weight acting on the vessel
        gmt_corr: meta-centric height after free surface correction
        angle_of_loll: angle of loll in gz curve
        max_draft: max draft of the vessel


    Returns:
        Maximum allowable heel angle and attained static heel angle
    """
    windage_area = length * (depth - draft)
    windage_area_centroid_from_mid_draft = (
        draft / 2 + (((depth - draft) ** 2) / 2 * length) / windage_area
    )
    overturning_moment = (
        wind_load * windage_area * windage_area_centroid_from_mid_draft / (9.812 * 1000)
    )
    static_angle_of_heel = (
        math.degrees(math.asin(overturning_moment / (total_weight * gmt_corr)))
        + angle_of_loll
    )
    maximum_angle_of_heel = math.degrees(math.atan((depth - max_draft) / breadth))
    return round(maximum_angle_of_heel, 2), round(static_angle_of_heel, 2)


def calculate_range_of_stability(x, y):
    """
    Function to compute range of stability

    Args:
        x: heel angle in degrees
        y: righting arm in meter

    Returns:
        Range of stability in degree
        Angle of loll in degree
    """

    interpolated_function = interp1d(
        x, y, kind="linear", bounds_error=False, fill_value="extrapolate"
    )

    roots = []

    # Detect zero crossings
    for i in range(len(x) - 1):
        if y[i] * y[i + 1] < 0:
            root_result = root_scalar(
                interpolated_function, bracket=[x[i], x[i + 1]], method="brentq"
            )
            if root_result.converged:
                roots.append(root_result.root)

    # Case handling based on initial GZ sign
    if all(val <= 0 for val in y):
        # Completely unstable
        angle_of_loll = 0.0
        second_intercept = 0.0
    elif all(val >= 0 for val in y):
        # Fully stable, no zero-crossing
        angle_of_loll = x[0]
        second_intercept = x[-1]
    elif y[0] >= 0:
        # Starts stable, becomes unstable
        angle_of_loll = x[0]
        second_intercept = roots[0] if roots else x[-1]
    else:
        # Starts unstable, gets stable, then unstable (typical loll case)
        angle_of_loll = roots[0] if roots else 0.0
        second_intercept = roots[1] if len(roots) > 1 else x[-1]

    range_of_stability = second_intercept - angle_of_loll

    return range_of_stability, angle_of_loll
