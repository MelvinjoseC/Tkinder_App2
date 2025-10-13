import math
from scipy.interpolate import interp1d, RegularGridInterpolator


def get_tank_weight(ship, tank_data):
    """
    Calculate total weight and center of gravity for tanks based on filled percentages.

    This function calculates the total weight, LCG, TCG, and VCG for each tank
    based on the filled percentage provided in the 'tank_data'.

    Parameters:
    - ship (dict): The ship object containing tank properties.
    - tank_data (dict): Dictionary containing tank names as keys and their fill percentages.

    Returns:
    - tuple: A tuple containing:
        - list: List of dictionaries with tank properties and calculated values.
        - tuple: A tuple containing total weight, LCG, TCG, and VCG for all tanks combined.
    """
    tanks = ship.get("Tanks")

    tank_properties = ["volume", "weight", "lcg", "tcg", "vcg", "fsm"]

    tank_vals = []

    for tank in tanks:
        if tank.endswith(".csv"):
            ip_data = []

            for prop in tank_properties:
                ip_data.append(interp1d(tanks[tank]["fill percent"], tanks[tank][prop]))

            tank_name = tank.replace(".csv", "")

            tank_dict = {
                param: val(float(tank_data.get(tank_name, 0))).tolist()
                for param, val in zip(tank_properties, ip_data)
            }

            tank_dict["tank_name"] = tank_name

            tank_dict["fill_percent"] = tank_data.get(tank_name, 0)

            tank_vals.append(tank_dict)

    weight = sum(tank["weight"] for tank in tank_vals)

    if weight == 0:
        return tank_vals, (0, 0, 0, 0, 0)

    lcg = sum(tank["lcg"] * tank["weight"] for tank in tank_vals) / weight

    tcg = sum(tank["tcg"] * tank["weight"] for tank in tank_vals) / weight

    vcg = sum(tank["vcg"] * tank["weight"] for tank in tank_vals) / weight
    
    fsm = sum(tank["fsm"] for tank in tank_vals)

    return tank_vals, (weight, lcg, tcg, vcg, fsm)


def get_lightship_weight(ship):
    """
    Retrieve lightship weight and its center of gravity for a given ship.

    Parameters:
    - ship (dict): Dictionary containing ship data, including "ship_data.json" with lightship information.

    Returns:
    - Tuple: A tuple containing lightship weight, LCG, TCG, and VCG.
    """
    lightship_data = ship["ship_data.json"]["lightship"]

    lightship_weight = lightship_data[0]["lightship_weight"]

    lightship_lcg = lightship_data[0]["lightship_lcg"]

    lightship_tcg = lightship_data[0]["lightship_tcg"]

    lightship_vcg = lightship_data[0]["lightship_vcg"]

    return lightship_weight, lightship_lcg, lightship_tcg, lightship_vcg


def get_gz_curve(ship, weight, vcg, tcg, trim):
    """
    Calculate the GZ curve for a ship.

    Parameters:
    - ship (dict): Dictionary containing ship's cross curves data.
    - weight (float): The weight of the ship.
    - vcg (float): Vertical center of gravity.
    - tcg (float): Transverse center of gravity.
    - trim (float): The ship's trim.

    Returns:
    - dict: A dictionary representing the GZ curve.
    """
    gz_curve = {}
    kn = ship.get("Cross Curves")
    heel_range = list(kn["0.csv"].columns)[1:]
    trim_data = sorted([val for val in kn],key=lambda x: float(x[:-4]))
    trim_vals = [float(val[:-4]) for val in trim_data]
    weight_vals = list(kn["0.csv"]["DISPLACEMENT"])
    kn_data = {
        param: [kn[val][param].tolist() for val in trim_data] for param in heel_range
    }
    heel_range = list(kn_data.keys())
    list_interp_func = [
        RegularGridInterpolator(
            (trim_vals, weight_vals),
            kn_data[heel],
            method="linear",
            bounds_error=False,
            fill_value=None,
        )
        for heel in heel_range
    ]
    kn_curve = {
        heel: param_val((trim, weight)).tolist()
        for heel, param_val in zip(heel_range, list_interp_func)
    }
    for angle, kn in kn_curve.items():
        gz = (
            kn
            - vcg * math.sin(math.radians(float(angle)))
            - tcg * math.cos(math.radians(float(angle)))
        )
        gz_curve[angle] = gz
    return gz_curve

def optimize_trim(ship,weight, lcg, tcg, vcg, vcg_corr, length):
    """
    Function to get optimized trimmed output

    Args:
        ship: ship pickle
        weight: total weight on the ship(lightship weight + dead weight)
        lcg: average lcg of total weight
        tcg: average tcg of total weight
        vcg: average vcg of total weight
        vcg_corr : corrected vcg value after accounting for free surface moment
        length : total length of the vessel

    Returns: floating status of the vessel

    """

    trim_deg = 0
    params = ["draft", "lcb", "vcb", "lcf", "kml", "kmt", "mct", "tpc"]
    hs = ship.get("Hydrostatics")
    trim_data = sorted([val for val in hs],key=lambda x: float(x[:-4]))
    trim_vals = [float(val[:-4]) for val in trim_data]

    param_data = {
        param: [hs[val][param].tolist() for val in trim_data] for param in params
    }

    weight_data = [hs[val]["weight"].tolist() for val in trim_data]

    list_interp_func = [
        RegularGridInterpolator(
            (trim_vals, weight_vals),
            param_data[param],
            method="linear",
            bounds_error=False,
            fill_value=None,
        )
        for weight_vals, param in zip(weight_data,params)
    ]


    trim_meter = 0

    floating_status = {
        param: param_val((trim_meter, weight)).tolist()
        for param, param_val in zip(params, list_interp_func)
    }

    trim_meter = weight * (floating_status["lcb"] - lcg) / (floating_status["mct"] * 100)

    floating_status = {
        param: param_val((trim_meter, weight)).tolist()
        for param, param_val in zip(params, list_interp_func)
    }

    trim_deg = math.degrees(math.atan(trim_meter / length))
    floating_status["draft_aft"] = floating_status["draft"] + trim_meter/2
    floating_status["draft_fwd"] = floating_status["draft"] - trim_meter/2
    floating_status["trim"] = trim_deg
    floating_status["heel"] = math.degrees(math.atan(tcg / (floating_status["kmt"] - vcg_corr)))
    floating_status["gmt_solid"] = floating_status["kmt"] - vcg
    floating_status["gmt_liquid"] = floating_status["kmt"] - vcg_corr
    floating_status["gml"] = floating_status["kml"] - vcg
    return floating_status


def get_fixed_weight(weight_data):
    """
    Calculate total weight and center of gravity for fixed weights.

    This function calculates the total weight, LCG, TCG, and VCG for fixed weights.

    Parameters:
    - weight_data (list of dict): List of dictionaries with keys "weight", "lcg", "tcg", "vcg".

    Returns:
    - tuple: A tuple containing:
        - float: Total weight of fixed weights.
        - float: Calculated LCG for fixed weights.
        - float: Calculated TCG for fixed weights.
        - float: Calculated VCG for fixed weights.
    """ 
    weight, lcg, tcg, vcg = 0, 0, 0, 0

    for fixed_weight in weight_data:
        weight += fixed_weight["weight"]

        lcg += fixed_weight["weight"] * fixed_weight["lcg"]

        tcg += fixed_weight["weight"] * fixed_weight["tcg"]

        vcg += fixed_weight["weight"] * fixed_weight["vcg"]

    if weight != 0:
        lcg /= weight

        tcg /= weight

        vcg /= weight

    return round(weight, 4), lcg, tcg, vcg



def get_leg_load_distribution(ship, total_weight, total_lcg, total_tcg):
    """
    Function to calculate leg load
    Args:
        ship: current active vessel
        total_weight: total weight onboard
        total_lcg: average lcg of total weight
        total_tcg: average tcg of total structure

    Returns: leg load values as list of dict

    """

    leg_data = ship["ship_data.json"]["leg_data"][0]
    center_of_length = sum([val["lcg"] for val in leg_data]) / len(leg_data)
    center_of_breadth = sum([val["tcg"] for val in leg_data]) / len(leg_data)
    uniform_load = total_weight / len(leg_data)
    longitudinal_lever = total_lcg - center_of_length
    transverse_lever = total_tcg - center_of_breadth
    longitudinal_moment = total_weight * longitudinal_lever
    transverse_moment = total_weight * transverse_lever
    longitudinal_distance_bw_legs = max([leg["lcg"] for leg in leg_data]) - min(
        [leg["lcg"] for leg in leg_data]
    )
    transverse_distance_bw_legs = max([leg["tcg"] for leg in leg_data]) - min(
        [leg["tcg"] for leg in leg_data]
    )
    for leg in leg_data:

        lcg_part = (
            longitudinal_moment / (longitudinal_distance_bw_legs * 2)
            if leg["lcg"] > center_of_length
            else -longitudinal_moment / (longitudinal_distance_bw_legs * 2)
        )
        tcg_part = (
            transverse_moment / (transverse_distance_bw_legs * 2)
            if leg["tcg"] > center_of_breadth
            else -transverse_moment / (transverse_distance_bw_legs * 2)
        )
        leg["weight"] = uniform_load + lcg_part + tcg_part

    return leg_data,(longitudinal_lever,transverse_lever)