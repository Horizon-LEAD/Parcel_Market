"""Parcel Market utilities
"""

from logging import getLogger
import array
import os.path
from json import loads

import pandas as pd
import numpy as np
import shapefile as shp

BOOL_VALUES = ('true', 't', 'on', '1', 'false', 'f', 'off', '0')
BOOL_TRUE_VALUES = ('true', 't', 'on', '1')
PARAMS_BOOL = ["CROWDSHIPPING_NETWORK", "COMBINE_DELIVERY_PICKUP_TOUR",
               "HYPERCONNECTED_NETWORK", "printKPI"]
PARAMS_STR = ["CS_BringerScore"]
PARAMS_NUM = ["CONSOLIDATED_MAXLOAD", "CS_WILLINGNESS", "PARCELS_DROPTIME_CAR",
              "PARCELS_DROPTIME_BIKE", "PARCELS_DROPTIME_PT", "VOT"]
PARAMS_LIST_STR = ["Gemeenten_studyarea", "Gemeenten_CS",
                   "hub_zones", "parcelLockers_zones"]
PARAMS_LIST_NUM = ["SCORE_ALPHAS", "SCORE_COSTS"]
PARAMS_JSON = ["HyperConect"]

logger = getLogger("parcelmarket.utils")


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
        for key in PARAMS_LIST_NUM:
            config_env[key] = [] if env[key] == '' else list(map(float, env[key].split(',')))
        for key in PARAMS_JSON:
            config_env[key] = {} if env[key] == '' else loads(env[key])
    except KeyError as exc:
        raise KeyError("Failed while parsing environment configuration") from exc
    except ValueError as exc:
        raise ValueError("Failed while parsing environment configuration") from exc

    return config_env


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


def get_traveltime(orig, dest, skim, n_zones, time_fac):
    """Obtain the travel time [h] for orig to a destination zone.

    :param orig: _description_
    :type orig: _type_
    :param dest: _description_
    :type dest: _type_
    :param skim: _description_
    :type skim: _type_
    :param n_zones: _description_
    :type n_zones: _type_
    :param time_fac: _description_
    :type time_fac: _type_
    :return: _description_
    :rtype: _type_
    """

    return skim[(orig-1)*n_zones + (dest-1)] * time_fac / 3600


def get_distance(orig, dest, skim, n_zones):
    """Obtain the distance [km] for orig to a destination zone.

    :param orig: _description_
    :type orig: _type_
    :param dest: _description_
    :type dest: _type_
    :param skim: _description_
    :type skim: _type_
    :param n_zones: _description_
    :type n_zones: _type_
    :return: _description_
    :rtype: _type_
    """

    return skim[(orig-1)*n_zones + (dest-1)] / 1000


def read_mtx(mtxfile):
    """Read a binary mtx-file (skimTijd and skimAfstand)

    :param mtxfile: _description_
    :type mtxfile: _type_
    :return: _description_
    :rtype: _type_
    """

    mtx_data = array.array('i')
    with open(mtxfile, 'rb') as fp_mtx:
        mtx_data.fromfile(fp_mtx, os.path.getsize(mtxfile) // mtx_data.itemsize)

    # The number of zones is in the first byte
    mtx_data = np.array(mtx_data, dtype=int)[1:]

    return mtx_data


def read_shape(shape_path, encoding='latin1', return_geometry=False):
    '''
    Read the shapefile with zones (using pyshp --> import shapefile as shp)
    '''
    # Load the shape
    sf_reader = shp.Reader(shape_path, encoding=encoding)
    records = sf_reader.records()
    if return_geometry:
        geometry = sf_reader.__geo_interface__
        geometry = geometry['features']
        geometry = [geometry[i]['geometry'] for i in range(len(geometry))]
    fields = sf_reader.fields
    sf_reader.close()

    # Get information on the fields in the DBF
    columns  = [x[0] for x in fields[1:]]
    col_types = [x[1:] for x in fields[1:]]
    n_records = len(records)

    # Put all the data records into a NumPy array (much faster than Pandas DataFrame)
    shape = np.zeros((n_records,len(columns)), dtype=object)
    for i in range(n_records):
        shape[i,:] = records[i][0:]

    # Then put this into a Pandas DataFrame with the right headers and data types
    shape = pd.DataFrame(shape, columns=columns)
    for i_c, column in enumerate(columns):
        if col_types[i_c][0] == 'C':
            shape[column] = shape[column].astype(str)
        else:
            shape.loc[pd.isna(shape[column]), column] = -99999
            if col_types[i_c][-1] > 0:
                shape[column] = shape[column].astype(float)
            else:
                shape[column] = shape[column].astype(int)

    if return_geometry:
        return (shape, geometry)

    return shape


def create_geojson(output_path, dataframe, origin_x, origin_y, destination_x, destination_y):
    """Creates GEO JSON file

    :param output_path: The output path to create the file
    :type output_path: str
    :param dataframe: The data
    :type dataframe: pd.Dataframe
    :param origin_x: X origin index
    :type origin_x: _type_
    :param origin_y: Y origin index
    :type origin_y: _type_
    :param destination_x: X destination index
    :type destination_x: _type_
    :param destination_y: Y destination index
    :type destination_y: _type_
    """
    a_x = np.array(dataframe[origin_x], dtype=str)
    a_y = np.array(dataframe[origin_y], dtype=str)
    b_x = np.array(dataframe[destination_x], dtype=str)
    b_y = np.array(dataframe[destination_y], dtype=str)
    n_trips = len(dataframe.index)

    with open(output_path, 'w') as geo_file:        # FIXME: no encoding
        geo_file.write('{\n' + '"type": "FeatureCollection",\n' + '"features": [\n')
        for i in range(n_trips-1):
            output_str = ""
            output_str = output_str + '{ "type": "Feature", "properties": '
            output_str = output_str + str(dataframe.loc[i, :].to_dict()).replace("'", '"')
            output_str = output_str + ', "geometry": { "type": "LineString", "coordinates": [ [ '
            output_str = output_str + a_x[i] + ', ' + a_y[i] + ' ], [ '
            output_str = output_str + b_x[i] + ', ' + b_y[i] + ' ] ] } },\n'
            geo_file.write(output_str)

        # Bij de laatste feature moet er geen komma aan het einde
        i += 1
        output_str = ""
        output_str = output_str + '{ "type": "Feature", "properties": '
        output_str = output_str + str(dataframe.loc[i, :].to_dict()).replace("'", '"')
        output_str = output_str + ', "geometry": { "type": "LineString", "coordinates": [ [ '
        output_str = output_str + a_x[i] + ', ' + a_y[i] + ' ], [ '
        output_str = output_str + b_x[i] + ', ' + b_y[i] + ' ] ] } }\n'
        geo_file.write(output_str)
        geo_file.write(']\n')
        geo_file.write('}')
