"""ParcelGen utilities
"""
from logging import getLogger
import array
import os.path

import pandas as pd
import numpy as np
import shapefile as shp


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
