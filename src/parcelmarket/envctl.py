"""An environment variables controller
"""

from logging import getLogger
from json import loads, JSONDecodeError


BOOL_VALUES = ('true', 't', 'on', '1', 'false', 'f', 'off', '0', "")
BOOL_TRUE_VALUES = ('true', 't', 'on', '1')

PARAMS_STR = ["CS_BringerScore","CS_ALLOCATION"]
PARAMS_BOOL = ["CROWDSHIPPING_NETWORK", "COMBINE_DELIVERY_PICKUP_TOUR",
               "HYPERCONNECTED_NETWORK", "printKPI"]
PARAMS_NUM = ["CONSOLIDATED_MAXLOAD", "CS_WILLINGNESS", "PARCELS_DROPTIME_CAR",
              "PARCELS_DROPTIME_BIKE", "PARCELS_DROPTIME_PT", "VOT","PlatformComission",
              "CS_Costs","TradCost","Car_CostKM",
              'CarSpeed','WalkBikeSpeed','CarCO2',
              "CS_MaxParcelDistance"]
PARAMS_LIST_STR = ["Gemeenten_studyarea", "Gemeenten_CS",
                   "hub_zones", "parcelLockers_zones", "ParcelLockersfulfilment"]
PARAMS_LIST_BOOL = []
PARAMS_LIST_NUM = ["SCORE_ALPHAS", "SCORE_COSTS","CS_COMPENSATION",
                   "CS_BaseBringerWillingess", "CS_Willingess2Send"]
PARAMS_JSON = ["HyperConect", "CS_BringerFilter", "CS_BringerUtility"]
# "CS_UtilityFunction", 
logger = getLogger("parcelmarket.envctl")


def to_bool(value):
    """Translates a string to boolean value.

    :param value: The input string
    :type value: str
    :raises ValueError: raises value error if the string is not recognized.
    :return: The translated boolean value
    :rtype: bool
    """
    val = str(value).lower().strip()
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
        for key in PARAMS_STR:
            config_env[key] = env[key]
        for key in PARAMS_BOOL:
            config_env[key] = to_bool(env[key])
        for key in PARAMS_NUM:
            config_env[key] = float(env[key])
        for key in PARAMS_LIST_STR:
            config_env[key] = [] if env[key] == '' else env[key].split(',')
        for key in PARAMS_LIST_BOOL:
            config_env[key] = [] if env[key] == '' else list(map(to_bool, env[key].split(',')))
        for key in PARAMS_LIST_NUM:
            config_env[key] = [] if env[key] == '' else list(map(float, env[key].split(',')))
        for key in PARAMS_JSON:
            config_env[key] = {} if env[key] == '' else loads(env[key])
    except KeyError as exc:
        raise KeyError(f"[{key}] Failed while parsing environment configuration") from exc
    except JSONDecodeError as exc:
        raise ValueError(f"[{key}] Failed while parsing JSON environment configuration") from exc
    except ValueError as exc:
        raise ValueError(f"[{key}] Failed while parsing environment configuration") from exc

    return config_env
