"""An environment variables controller for Parcel Market
"""

from logging import getLogger
from json import loads, JSONDecodeError

from numpy.random import normal


BOOL_VALUES = ('true', 't', 'on', '1', 'false', 'f', 'off', '0')
BOOL_TRUE_VALUES = ('true', 't', 'on', '1')

PARAMS_BOOL = ["CROWDSHIPPING_NETWORK", "COMBINE_DELIVERY_PICKUP_TOUR",
               "HYPERCONNECTED_NETWORK", "printKPI", "TESTRUN"]
PARAMS_NUM = ["CONSOLIDATED_MAXLOAD", "CS_MaxParcelDistance",
              "PARCELS_DROPTIME_CAR", "PARCELS_DROPTIME_BIKE", "PARCELS_DROPTIME_PT",
              "PlatformComission", "CS_Costs", "TradCost",
              "CarSpeed", "WalkBikeSpeed", "CarCO2", "Car_CostKM", "VOT"]
PARAMS_STR = ["CS_BringerScore", "CS_ALLOCATION"]
PARAMS_LIST_STR = ["hub_zones", "parcelLockers_zones", "Gemeenten_studyarea", "Gemeenten_CS",
                   "CrowdshippingWithCouriers"]
PARAMS_LIST_NUM = ["SCORE_ALPHAS", "SCORE_COSTS"]
PARAMS_JSON = ["HyperConect", "CS_BringerFilter"]

logger = getLogger("parcelgen.envctl")


def to_bool(value):
    """Translates a string to boolean value.

    :param value: The input string
    :type value: str
    :raises ValueError: raises value error if the string is not recognized.
    :return: The translated boolean value
    :rtype: bool
    """
    val = str(value).lower()
    if val not in BOOL_VALUES:
        raise ValueError(f'error: {value} is not a recognized boolean value {BOOL_VALUES}')
    if val in BOOL_TRUE_VALUES:
        return True
    return False


def parse_env_values(env):
    """Parses environment values.

    :param env: The environment dictionary
    :type env: dict
    :raises KeyError: If a required key is missing
    :raises ValueError: If the value of the key is invalid
    :return: The configuration dictionary
    :rtype: dict
    """
    config_env = {}
    try:
        config_env["LABEL"] = env['LABEL']
        for key in PARAMS_BOOL:
            config_env[key] = to_bool(env[key])
        for key in PARAMS_NUM:
            config_env[key] = float(env[key])
        for key in PARAMS_JSON:
            config_env[key] = loads(env[key])
        for key in PARAMS_LIST_STR:
            if env[key] == '':
                config_env[key] = []
            else:
                config_env[key] = env[key].split(',')
        for key in PARAMS_LIST_NUM:
            if env[key] == '':
                config_env[key] = []
            else:
                config_env[key] = list(map(float, env[key].split(',')))
    except KeyError as exc:
        raise KeyError("Failed while parsing environment configuration") from exc
    except JSONDecodeError as exc:
        raise ValueError("Failed while parsing JSON environment configuration") from exc
    except ValueError as exc:
        raise ValueError("Failed while parsing environment configuration") from exc

    config_env["CS_BaseBringerWillingess"] = -1.4 + 0.1 * normal(0, 1)
    # config_env["CS_Willingess2Send"] =
    # config_env["CS_BringerUtility"] =
    # config_env["CS_COMPENSATION"] =


    return config_env
