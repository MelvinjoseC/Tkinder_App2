from scipy.interpolate import RectBivariateSpline, interp1d



def get_ls_plot(ship, draft_aft, cargo_data, tank_data, trim):
    """
    Function to get ls plot data
    Args:
        ship: ship pickle
        draft_aft: draft at aft perpendicular
        cargo_data: dict of cargo_data
        tank_data: dict of tanks data
        trim: trim of the vessel

    Returns: Dict containing ls results

    """
    sf = []
    bm = []
    x_loc, lightship_distribution = get_lightship_distribution(ship)

    tank_weight_distribution_list = get_tank_weight_distribution(ship, tank_data)
    cargo_weight_distribution_list = get_cargo_weight_distribution(cargo_data)
    distribution_list = tank_weight_distribution_list + cargo_weight_distribution_list

    if distribution_list:
        x_val, weight_distribution = get_weight_dn(
            x_vals=x_loc,
            lightship_distribution=lightship_distribution,
            distribution_list=distribution_list,
        )
    else:
        x_val, weight_distribution = x_loc, lightship_distribution

    ls_bd_val, ls_buoyancy_distribution = get_ls_buoyancy_distribution(ship)

    total_dead_weight = 0
    total_dead_weight = sum([cargo["weight"]*cargo["length"] for cargo in cargo_data]) + sum([tank["weight"] for tank in tank_data])

    vessel_length = ship["ship_data.json"]["vessel_data"][0]["loa"]


    buoyancy_distribution = get_buoyancy_distribution(x_vals=x_val,weight_distribution=weight_distribution,ls_x_vals=ls_bd_val, ls_buoyancy_distribution=ls_buoyancy_distribution,length= vessel_length, total_dead_weight=total_dead_weight, draft_aft=draft_aft , trim=trim )

    sf = []

    for wd,bd in zip(weight_distribution,buoyancy_distribution):
        if sf == []:
            sf.append(round(((bd - wd) * 9.81)))
        else:
            sf.append(round(((bd - wd) * 9.81 + sf[-1])))

    sf_var_list = []
    last_val = 0
    for index, val in enumerate(x_val):
        if index == 0:
            sf_var_list.append(0.0)
        else:
            value = (
                (0.5 * (sf[index] - sf[index - 1]) + sf[index - 1])
                * (x_val[index] - x_val[index - 1])
            ) + last_val
            sf_var_list.append(value)
            last_val = value
    for index, val in enumerate(sf_var_list):
        value = val - (sf_var_list[-1] * (x_val[index] / x_val[-1]))
        bm.append(round(value, 2))

    sf_max_value = max(sf, key=abs)
    sf_max_index = sf.index(sf_max_value)
    sf_max_loc = x_val[sf_max_index]

    bm_max_value = max(bm, key=abs)
    bm_max_index = bm.index(bm_max_value)
    bm_max_loc = x_val[bm_max_index]

    longitudinal_strength = ship["ship_data.json"]["longitudinal_strength"][0]
    sf_limit = longitudinal_strength["sf_max"]
    bm_limit = longitudinal_strength["bm_max"]

    return {
        "location": x_val,
        "wd": weight_distribution,
        "bd": buoyancy_distribution,
        "sf": sf,
        "bm": bm,
        "checks": {
            "sf_limit": sf_limit,
            "sf_max": sf_max_value,
            "uc_sf": abs(sf_max_value / sf_limit),
            "bm_limit": bm_limit,
            "bm_max": bm_max_value,
            "uc_bm": abs(bm_max_value / bm_limit),
        },
    }


def get_lightship_distribution(ship):
    """
    Function to retrieve lightship distribution of vessel
    Args:
        ship: ship pickle

    Returns: tuple of list containing location and corresponding weight distribution

    """
    ls_dn = ship["lightship_distribution.csv"]
    x_values = ls_dn["x"].to_list()
    y_values = ls_dn["y"].to_list()
    return x_values, y_values


def get_ls_buoyancy_distribution(ship):
    """
    Function to retrieve buoyancy distribution of vessel
    Args:
        ship: ship pickle

    Returns: tuple of list containing location and corresponding buoyancy distribution

    """
    ls_dn = ship["buoyancy_distribution.csv"]
    x_values = ls_dn["x"].to_list()
    y_values = ls_dn["y"].to_list()
    return x_values, y_values


def get_buoyancy_distribution(x_vals,weight_distribution, ls_x_vals,ls_buoyancy_distribution, total_dead_weight, length, draft_aft, trim):
    """
    Function to get buoyancy distribution of the vessel
    Args:
        x_vals: new x locations
        weight_distribution: total weight distribution
        ls_x_vals: ls sampling points
        ls_buoyancy_distribution: ls buoyancy list
        total_dead_weight: total additional weight
        length: length of the vessel
        draft_aft: draft at aft perpendicular
        trim: trim of the vessel

    Returns:   list containing total buoyancy distribution of the vessel

    """

    bd_interp_func = interp1d(ls_x_vals,ls_buoyancy_distribution, kind='linear', bounds_error=False, fill_value=0)
    sample_y_vals = [bd_interp_func(val) for val in x_vals]
    draft_vals = [draft_aft+trim/(length*x) if x!=0 else draft_aft+trim/length for x in x_vals]
    buoyancy_distribution = [bd+total_dead_weight*d/sum(draft_vals) for bd,d in zip(sample_y_vals,draft_vals)]
    
    correction_factor = 1+(sum(weight_distribution) -sum(buoyancy_distribution)) / sum(buoyancy_distribution)
    total_buoyancy_distribution = [bd*correction_factor for bd in buoyancy_distribution]

    return total_buoyancy_distribution


def get_weight_dn(x_vals, lightship_distribution, distribution_list):
    """
    Function to add tank and cargo weights to lightship distribution
    Args:
        x_vals: light ship x - location values
        lightship_distribution: lightship weight values
        distribution_list: additional weight acting on the vessel due to cargo and tanks

    Returns: tuple of list containing location and corresponding weight distribution

    """
    for dn in distribution_list:
        weight = dn[0]
        x_min = dn[1]
        x_max = dn[2]

        # Find indices within the range
        indices_in_range = [i for i, value in enumerate(x_vals) if x_min < value < x_max]

        # If there are no values within the range, continue to the next dn
        if not indices_in_range:
            continue

        for index in indices_in_range:
            ad_x = x_vals[index]
            additional_weight = lightship_distribution[index]

            if index == indices_in_range[0]:
                lightship_distribution[index] = round(weight * ((ad_x - x_min) / (x_max - x_min)) + additional_weight, 2)
            else:
                lightship_distribution[index] = round(weight * ((ad_x - x_vals[index - 1]) / (x_max - x_min)) + additional_weight, 2)

    return x_vals, lightship_distribution



def get_cargo_weight_distribution(cargo_data):
    """
    Function to get cargo weight distribution
    Args:
        cargo_data: dict of cargo_data

    Returns: list of lists containing distributed weight and cargo extends

    """
    cargo_weight_distribution_list = []
    for cargo in cargo_data:
        cargo_weight = cargo["weight"]
        cargo_length = cargo["length"]
        cargo_lcg = cargo["lcg"]

        x1, x2 = cargo_lcg - cargo_length / 2, cargo_lcg + cargo_length / 2
        cargo_weight_distribution_list.append([cargo_weight, x1, x2])
    return cargo_weight_distribution_list


def get_tank_weight_distribution(ship, tank_data):
    """
    Function to get tank weight distribution
    Args:
        ship: ship pickle
        tank_data: dict of tanks data

    Returns: list of lists containing distributed weight and tank extends

    """
    tank_weight_distribution_list = []
    tank_extents = ship["tank_extent.json"]
    for tank in tank_data:
        if tank["weight"] != 0:
            tank_name = tank["tank_name"]
            tank_weight = tank["weight"]
            x1, x2 = (
                tank_extents[tank_name][0]["aft_extent"],
                tank_extents[tank_name][0]["forward_extent"],
            )

            tank_weight_distribution_list.append([tank_weight, x1, x2])
    return tank_weight_distribution_list
