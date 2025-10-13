import math
import pandas as pd
def calculate_crane_and_swl(ship, crane_data, cargo_data, Mrigging, Mhook, WCFrigging, WCF, DAF, DAFincl, Mblock,boomdata):
    """
    Function to calculate both crane orientations (boom angle and slew angle) and required SWL.
    Args:
        ship: Ship data to retrieve the crane load curve
        crane_data: Crane data in JSON format
        cargo_data: Cargo data to be lifted
        crane_load_curve: Crane load curve
        Mrigging: Rigging weight
        Mhook: Hook weight
        WCFrigging: Weight correction factor for rigging
        WCF: Weight correction factor
        DAF: Dynamic Amplification Factor
        DAFincl: Dynamic Amplification Factor included
        Mblock: Block weight

    Returns:
        A dictionary containing crane orientations and calculated SWL values.
    """

    crane_orientations = {}
    # Process each crane and its corresponding cargo
    for crane in crane_data:
        crane_details = crane_data[crane][0]  # Get the corresponding crane details

        # Retrieve the corresponding cargo details
        cargo_details = cargo_data.get(crane)
        if cargo_details:
            [x1, y1, z1] = crane_details["pedestal_base_point"]
            boom_type = boomdata["boom"].replace(" Boom", "")
          

            if boom_type in crane_details["boom_tip_point"]:
            # If it exists, fetch and print the corresponding value
                [x2, y2, z2] = crane_details["boom_tip_point"][boom_type]  
            else:
                 [x2, y2, z2] = crane_details["boom_tip_point"]
           
            [weight, x3, y3, z3] = cargo_details

            boom_length = x2 - x1
            required_outreach = math.sqrt((x3 - x1) ** 2 + (y3 - y1) ** 2)
            required_swl_table=get_swl_table(ship,boomdata)
            required_swl = calculate_required_swl(ship,required_swl_table, required_outreach,weight, Mrigging, Mhook, WCFrigging, WCF, DAF, DAFincl, Mblock)
            Ucr= required_swl["UCr"]
            Ucl=required_swl["UCl"]
            boom_angle= calculate_boom_angle(boom_length, required_outreach,Ucl,Ucr)
            slewangle=calculate_slew_angle(x1, y1, x2, y2, x3, y3)


         
            crane_orientations[crane] = {
                "slew_angle": slewangle,
                "boom_angle":boom_angle,
                "required_outreach": required_outreach,
                "weight": weight,
               "required_swl_table" :required_swl_table.to_dict()

            }
        else:
            crane_orientations[crane] = []  # Empty list if no cargo details


    # Return both crane orientations and required SWL values
    return {"crane_orientations": crane_orientations, "calculated_output_values": required_swl}

def calculate_slew_angle(x1, y1, x2, y2, x3, y3):
    """
    Function to calculate slew angle of the crane
    Args:
        x1: longitudinal location of boom base point
        y1: transverse location of boom base point
        x2: longitudinal location of boom tip point
        y2: transverse location of boom tip point
        x3: cargo lcg value
        y3: cargo tcg value

    Returns: slew angle

    """

    vector_A_x = x2 - x1
    vector_A_y = y2 - y1

    vector_B_x = x3 - x1
    vector_B_y = y3 - y1

    dot_product = vector_A_x * vector_B_x + vector_A_y * vector_B_y

    magnitude_A = math.sqrt(vector_A_x**2 + vector_A_y**2)
    magnitude_B = math.sqrt(vector_B_x**2 + vector_B_y**2)

    # Calculate the cosine of the angle
    cos_angle = dot_product / (magnitude_A * magnitude_B)

    # Calculate the angle in radians
    angle_radians = math.acos(cos_angle)

    # Convert the angle to degrees
    slew_angle = math.degrees(angle_radians)

    # Calculate the cross product to determine the orientation of the angle
    cross_product = vector_A_x * vector_B_y - vector_A_y * vector_B_x

    # Adjust the angle based on the cross product sign
    if cross_product < 0:
        slew_angle = 360 - slew_angle

 

    return slew_angle


def calculate_boom_angle(boom_length, required_outreach,Ucl,Ucr):
    """
    Function to calculate boom angle
    Args:
        boom_length: length of boom
        required_outreach: required outreach
        crane_load_curve: crane load curve
        weight: cargo weight
        UCl: Load utilization ratio.
        UCr: Outreach utilization ratio.

    Returns: Boom angles in degree

    """

    # # Check if the required outreach is possible
    # if required_outreach > boom_length or required_outreach < 0:
    #     return "Cargo outside maximum outreach!"
    if Ucr > 1 and Ucl > 1:
        return"Lift is beyond crane capacity and max radius!"
    if Ucl>1:
        return "Lift is beyond crane capacity!"
    if Ucr>1:
        return "Lift is beyond max radius!"    
   
    # Calculate the angle in radians
    boom_angle = math.acos(required_outreach / boom_length)

    # Convert the angle to degrees
    boom_angle_deg = math.degrees(boom_angle)

    if boom_angle_deg > 75:
        return "Cargo inside minimum outreach!"

    return boom_angle_deg


def calculate_required_swl(ship,required_swl_table,required_outreach,crane_weight,Mrigging,Mhook,WCFrigging, WCF,DAF, DAFincl,Mblock):
    """
    Function to calculate the required Safe Working Load (SWL) for a crane operation.

    Args:
        ship: Ship data used for reference or to access crane load curves.
        required_outreach: Horizontal distance from crane base to the load.
        crane_weight: Weight of the cargo/load to be lifted.
        Mrigging: Weight of the rigging components.
        Mhook: Weight of the crane hook.
        WCFrigging: Weight Correction Factor for rigging.
        WCF: Weight Correction Factor for overall system.
        DAF: Dynamic Amplification Factor (due to dynamic effects).
        DAFincl: Dynamic Amplification Factor already included in the load.
        Mblock: Weight of the crane block.

    Returns:
        A dictionary with:
            SHLbe: Basic static hook load before corrections.
            SHLub: Unfactored gross hook load.
            SWLreq: Required Safe Working Load.
            SWL: Interpolated actual SWL from crane load curve.
            SWLcorr: Corrected SWL for dynamic amplification.
            UCl: Load utilization ratio.
            Rm: Outreach at which the SWLreq can be met.
            UCr: Outreach utilization ratio .
    """
    SWL = 0.00
    Rm = 0.00
    Mnet = crane_weight
    Mgross = crane_weight
    Ra = required_outreach

    # Calculate SHLbe
    SHLbe = Mnet + Mrigging + Mhook
    # Calculate SHLub
    SHLub = (Mgross * WCF) + (Mrigging * WCFrigging) + Mhook

    # Calculate SWLreq
    if DAF > DAFincl:  # Prevent division by zero
        SWLreq = ((SHLub + Mblock) * DAF) / DAFincl - Mblock
    else:
        SWLreq = SHLub  # Handle case where DAFincl is zero

    # Calculate SWL
    # Fetch crane load curve from ship data
    if required_swl_table is not None:
            crane_load_curve = required_swl_table


    if Ra == 0.00:
        SWL = 0.00
    elif not crane_load_curve.empty:
        # Extract Radius and SWL as lists
        radius_list = crane_load_curve["Radius"].tolist()
        swl_list = crane_load_curve["SWL"].tolist()

        if Ra in radius_list:
            # If Ra directly matches a Radius value, fetch SWL
            SWL = swl_list[radius_list.index(Ra)]
        elif Ra > max(radius_list):
            SWL = swl_list[-1]
        elif Ra < min(radius_list):
            SWL = swl_list[0]
        else:
            # Find closest lower and upper values for interpolation
            lower_indices = [i for i in range(len(radius_list)) if radius_list[i] <= Ra]
            upper_indices = [i for i in range(len(radius_list)) if radius_list[i] >= Ra]

            if lower_indices and upper_indices:
                lower_idx = max(lower_indices)
                upper_idx = min(upper_indices)

                if lower_idx != upper_idx:  # Ensure it's an intermediate value
                    Rup, Swlup = radius_list[lower_idx], swl_list[lower_idx]
                    Rdown, SWldown = radius_list[upper_idx], swl_list[upper_idx]

                    # Apply interpolation formula
                    SWL = Swlup + (Ra - Rup) * (SWldown - Swlup) / (Rdown - Rup)

    if SWLreq == 0.00:
        Rm = 0.00
    else:
        swl_list = crane_load_curve["SWL"].tolist()    
        radius_list = crane_load_curve["Radius"].tolist()        

        # Calculate Rm            
        if SWLreq in swl_list:
            # If SWLreq directly matches an SWL value, fetch the corresponding Radius
            Rm = radius_list[swl_list.index(SWLreq)]
        elif SWLreq < min(swl_list):
            Rm = radius_list[-1]
        elif SWLreq > max(swl_list):
            Rm = radius_list[0]
        else:
            # Find closest lower and upper SWL values for interpolation
            lower_swl = max([swl for swl in swl_list if swl <= SWLreq], default=None)
            higher_swl = min([swl for swl in swl_list if swl >= SWLreq], default=None)

            if lower_swl is not None and higher_swl is not None and lower_swl != higher_swl:
                X1, X2 = higher_swl, lower_swl  # SWL values
                Y1 = radius_list[swl_list.index(X1)]  # Corresponding Radius for higher SWL
                Y2 = radius_list[swl_list.index(X2)]  # Corresponding Radius for lower SWL

                # Apply interpolation formula
                Rm = Y1 + (SWLreq - X1) * ((Y2 - Y1) / (X2 - X1))

    
        # Calculate SWLcorr
    if DAF > DAFincl:  # Prevent division by zero
        SWLcorr = ((SWL + Mblock) * DAFincl) / DAF - Mblock
    else:
        SWLcorr = SWL  # Handle case where DAFincl is zero

        # Calculate UCl
    UCl = SHLub / SWLcorr if SWLcorr != 0 else 0.00
    
        # Calculate UCr
    UCr = Ra / Rm if Rm != 0 else 0.00
    
    required_swl = {
            "SHLbe": SHLbe,
            "SHLub": SHLub,
            "SWLreq": SWLreq,
            "SWL": SWL,
            "SWLcorr": SWLcorr,
            "UCl": UCl,
            "Rm": Rm,
            "UCr": UCr
        }
    
    return required_swl

def get_swl_table(ship, boomdata):
    crane_data = ship.get("Crane Data", {})
    boom = boomdata.get('boom')
    operation = boomdata.get('operation')
    required_height = boomdata.get('height')

    # If any of the required keys is not selected, trigger fallback
    if not boom or not operation or not required_height:
        for boom_key in crane_data:
            for operation_key in crane_data[boom_key]:
                for csv_key, swl_table in crane_data[boom_key][operation_key].items():
                    if csv_key.endswith('.csv'):
                        return swl_table
        return None

    # If all values are present, try specific lookup
    if boom in crane_data:
        boom_section = crane_data[boom]
        if operation in boom_section:
            operation_section = boom_section[operation]
            csv_key = f"{required_height}.csv"
            if csv_key in operation_section:
                return operation_section[csv_key]

    # Explicit fallback if nothing found
    return None


        
 


           
