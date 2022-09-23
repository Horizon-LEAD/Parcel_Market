"""Utilities
"""

from logging import getLogger
import array
import os.path
import math
from json import loads
from itertools import islice, tee

import pandas as pd
import numpy as np
import shapefile as shp
import networkx as nx

logger = getLogger("parcelmarket.utils")


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


def k_shortest_paths(G, source, target, k, weight=None):
    """_summary_

    :param G: _description_
    :type G: _type_
    :param source: _description_
    :type source: _type_
    :param target: _description_
    :type target: _type_
    :param k: _description_
    :type k: _type_
    :param weight: _description_, defaults to None
    :type weight: _type_, optional
    :return: _description_
    :rtype: _type_
    """
    return list(islice(nx.shortest_simple_paths(G, source, target, weight=weight), k))


def pairwise(iterable):
    """_summary_

    :param iterable: _description_
    :type iterable: _type_
    :return: _description_
    :rtype: _type_
    """
    a, b = tee(iterable)
    next(b, None)

    return zip(a, b)


def get_compensation(dist_parcel_trip):
    return math.log( (dist_parcel_trip) + 2)


def calc_score(
    G, u, v, orig, dest,
    d,
    allowed_cs_nodes, hub_nodes,
    parcel,
    cfg: dict
):
    """_summary_

    :param u: _description_
    :type u: _type_
    :param v: _description_
    :type v: _type_
    :param d: _description_
    :type d: dict
    :return: _description_
    :rtype: _type_
    """
    X1_travtime = d['travtime'] / 3600      # Time in hours
    X2_length = d['length'] / 1000          # Distance in km

    ASC, A1, A2, A3 = cfg['SCORE_ALPHAS']
    tour_based_cost, consolidated_cost, hub_cost, cs_trans_cost, interCEP_cost = cfg['SCORE_COSTS']

    if d['network'] == 'conventional' and d['type'] in['consolidated']:
        X2_length = X2_length/50

    if u == orig or v == dest:
        # access and agress links to the network have score of 0
        return 0

    # other zones than orig/dest can not be used
    if G.nodes[u]['node_type'] == 'zone' and u not in {orig, dest}:
        return 99999

    if d['type'] == 'access-egress':
        return 0

    # CS network except for certain nodes can not be used
    if d['network'] == 'crowdshipping' and u not in allowed_cs_nodes:
        return 99999

    if not cfg['HYPERCONNECTED_NETWORK']:
        # Other conventional carriers can not be used
        if d['network'] == 'conventional' and d['CEP'] != parcel['CEP']:
            return 99999
    else:
        if (d['network'] == 'conventional'
            and d['CEP'] != parcel['CEP']
            and d['CEP'] not in cfg["HyperConect"][parcel['CEP']]):
            # only hub nodes may be used (no hub network at CEP depots), one directional only
            return 99999
        else: X3_cost = interCEP_cost

    # only hub nodes may be used (no hub network at CEP depots)
    if d['network'] == 'conventional' and d['type'] == 'hub' and v not in hub_nodes:
        return 99999
    if d['network'] == 'conventional' and d['type'] in['tour-based']:
        X3_cost = tour_based_cost
    if d['network'] == 'conventional' and d['type'] in['consolidated']:
        X3_cost = consolidated_cost
    if d['network'] == 'conventional' and d['type'] in['hub']:
        X3_cost = hub_cost

    if d['network'] == 'crowdshipping':
        X3_cost = get_compensation(X2_length)

    if d['network'] == 'transshipment' and d['type'] == 'CS':
        X3_cost = cs_trans_cost
    if d['network'] == 'transshipment' and d['type'] == 'hub':
        X3_cost = hub_cost

    score = ASC + A1*X1_travtime + A2 * X2_length + A3*X3_cost

    return score
