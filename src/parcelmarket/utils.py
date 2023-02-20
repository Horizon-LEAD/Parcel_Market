# -*- coding: utf-8 -*-
"""
Created on Wed Dec  7 08:44:04 2022

@author: rtapia
"""
"""Utilities
"""
import array
import math
from logging import getLogger
from os.path import getsize, dirname
from itertools import islice, tee
from posixpath import splitext
from zipfile import ZipFile

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
        mtx_data.fromfile(fp_mtx, getsize(mtxfile) // mtx_data.itemsize)

    # The number of zones is in the first byte
    mtx_data = np.array(mtx_data, dtype=int)[1:]

    return mtx_data


def read_shape(fpath, encoding='latin1', return_geometry=False):
    '''
    Read the shapefile with zones (using pyshp --> import shapefile as shp)
    '''
    # Load the shape
    with ZipFile(fpath) as z:
        z.extractall(path=dirname(fpath))

    shape_path = splitext(fpath)[0] + '.shp'
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


def get_compensation(dist_parcel_trip,cfg):
    
    """
    
    """
    Coeff = cfg["CS_COMPENSATION"]
    Comp = Coeff[0] + Coeff[1] * dist_parcel_trip + Coeff[2] * dist_parcel_trip^2 + math.log( (Coeff[3] * dist_parcel_trip) + 1)
    
    return Comp

def get_WillingnessToSend(cfg,Cost,TradCost,deterministic=0):
    
    """
    
    """
    Coeff = cfg["CS_Willingess2Send"]
    Will = Coeff[0] + Coeff[1]  * (Cost-TradCost)
    if deterministic == 0:
         Will += np.log(-np.log(np.random.uniform())) - np.log(-np.log(np.random.uniform()))
    
    return Will

def get_BaseWillforBring(cfg, unique_id):
    
    """
    
    """
    Coeff = cfg["CS_BaseBringerWillingess"]
    Will = Coeff[0] + Coeff[1] *  np.random.normal(0,1) 	
    Prob = 1/(1+np.exp(-Will))
    return Prob

def generate_Utility (UtilityFunct, variables,deterministic=0):  # TODO: How to add the variables from the columns
    '''
    UtilityFunct : Dictionary
    '''
     
    try:
         Utility =UtilityFunct["ASC"]
    except:
         Utility = 0
     
    for key,val in variables.items():
             # exec(key + '=val')
             Utility+=val * UtilityFunct[str(key)]
         
    if deterministic == 0:
         Utility += np.log(-np.log(np.random.uniform()))
     
     
    return Utility 
 

def BringerProb2Bring(Cost,Time,cfg):
    
    """
    
    """
    Coeff = cfg["CS_BringerUtility"]
    Util = Coeff[0] + Coeff[1] *  Cost + Coeff[2] *  Time
    Prob = 1/(1+np.exp(-Util))
    return Prob


def getMax (matrix,cols,rows,othermatrix =np.nan, remove =1):  # If I do the first line and column as the trip ID or parcel ID, then I can remove the lines! If not, add a key that you remove as well when you remvoe the line!
    # Remove = 1 is that removes the line --> each person takes only 1 parcel per trip!!    
    maximum = np.amax(matrix)
    position = np.where(matrix == maximum)
    # valueinothermatrix = othermatrix[position][0]

    pair = {rows.iloc[position[0][0]][0]:cols.iloc[position[1][0]][0]}  # This is the result!
    valueinothermatrix = {rows.iloc[position[0][0]][0]:othermatrix[position][0]}

    matrix = np.delete(matrix,position[1][0],1) # Delete parcel (column) from list
    othermatrix = np.delete(othermatrix,position[1][0],1) # Delete parcel (column) from list
    cols = cols.drop(cols.index[position[1][0]]).reset_index(drop=True)

    if remove ==1 : # Delete row
        matrix = np.delete(matrix,position[0][0],0) # Delete parcel (column) from list
        othermatrix= np.delete(othermatrix,position[0][0],0) # Delete parcel (column) from list
        rows= rows.drop(rows.index[position[0][0]]).reset_index(drop=True)
    else: # Put zeros
        matrix[position[0],:] = np.zeros(( len(matrix[position[0],:][0] )))    
    
    return pair, maximum, matrix,othermatrix,valueinothermatrix, cols,rows


# TODO Check this!
# def generate_Utility (UtilityFunct, variables,deterministic=0):  # TODO: How to add the variables from the columns
 
 
#      for key,val in variables.items():
#              exec(key + '=val')
         
#      Utility = eval(UtilityFunct)
     
#      if deterministic == 0:
#          Utility += np.log(-np.log(np.random.uniform()))
     
     
#      return Utility 

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
    tour_based_cost, consolidated_cost, hub_cost, cs_trans_cost, interCEP_cost,interCEP_pickup = cfg['SCORE_COSTS']
    X3_costPup=0
    X3_cost =0
    if d['network'] == 'conventional' and d['type'] in['consolidated']:
        X2_length = X2_length/50

    if u==orig and d['network'] == 'locker':
        return 999991

    if v==dest and d['CEP'] != 'locker' and parcel["PL"] !=0:
        return 999992
    
    if not cfg['HYPERCONNECTED_NETWORK']:
        if u == orig or v == dest: return 0 # access and agress links to the network have score of 0
        
    # other zones than orig/dest can not be used
    if G.nodes[u]['node_type'] == 'zone' and u not in {orig, dest}:
        return 999993



    # CS network except for certain nodes can not be used
    if d['network'] == 'crowdshipping' and u not in allowed_cs_nodes:
        return 999994

    if not cfg['HYPERCONNECTED_NETWORK']:
        # Other conventional carriers can not be used
        if d['network'] == 'conventional' and d['CEP'] != parcel['CEP']:
            return 999995
    else:
        if (d['network'] == 'conventional'
            and d['CEP'] != parcel['CEP']
            and d['CEP'] not in cfg["HyperConect"][parcel['CEP']]):
            # only hub nodes may be used (no hub network at CEP depots), one directional only
            return 999996
        else: X3_cost = interCEP_cost

    if d['network'] != 'crowdshipping':
        if d['type']== 'access-egress' and parcel['CEP']!=d['CEP'] and u == orig: #for parcel locker, to enforce that the original CEP picks it up.
              
            X3_costPup = interCEP_pickup
            
    # only hub nodes may be used (no hub network at CEP depots)
    if d['network'] == 'conventional' and d['type'] == 'hub' and v not in hub_nodes:
        return 999997
    if d['network'] == 'conventional' and d['type'] in['tour-based']:
        X3_cost = tour_based_cost
    if d['network'] == 'conventional' and d['type'] in['consolidated']:
        X3_cost = consolidated_cost
    if d['network'] == 'conventional' and d['type'] in['hub']:
        X3_cost = hub_cost

    if d['network'] == 'crowdshipping':
        X3_cost = get_compensation(X2_length,cfg)

    if d['network'] == 'transshipment' and d['type'] == 'CS':
        X3_cost = cs_trans_cost
    if d['network'] == 'transshipment' and d['type'] == 'hub':
        X3_cost = hub_cost

    score = ASC + A1*X1_travtime + A2 * X2_length + A3*(X3_cost +X3_costPup)
    return score
