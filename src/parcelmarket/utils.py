# -*- coding: utf-8 -*-
"""
Created on Thu Oct 22 12:17:13 2020

@author: modelpc
"""
import pandas as pd
import numpy as np
import shapefile as shp
import array
import os.path

def get_traveltime(orig,dest,skim,nZones,timeFac):
    ''' Obtain the travel time [h] for orig to a destination zone. '''
    return skim[(orig-1)*nZones+(dest-1)] * timeFac / 3600

def get_distance(orig,dest,skim,nZones):
    ''' Obtain the distance [km] for orig to a destination zone. '''
    return skim[(orig-1)*nZones+(dest-1)] / 1000


def read_mtx(mtxfile):  
    '''
    Read a binary mtx-file (skimTijd and skimAfstand)
    '''
    mtxData = array.array('i')  # i for integer
    mtxData.fromfile(open(mtxfile, 'rb'), os.path.getsize(mtxfile) // mtxData.itemsize)
    
    # The number of zones is in the first byte
    mtxData = np.array(mtxData, dtype=int)[1:]
    
    return mtxData



def read_shape(shapePath, encoding='latin1', returnGeometry=False):
    '''
    Read the shapefile with zones (using pyshp --> import shapefile as shp)
    '''
    # Load the shape
    sf = shp.Reader(shapePath, encoding=encoding)
    records = sf.records()
    if returnGeometry:
        geometry = sf.__geo_interface__
        geometry = geometry['features']
        geometry = [geometry[i]['geometry'] for i in range(len(geometry))]
    fields = sf.fields
    sf.close()
    
    # Get information on the fields in the DBF
    columns  = [x[0] for x in fields[1:]]
    colTypes = [x[1:] for x in fields[1:]]
    nRecords = len(records)
    
    # Put all the data records into a NumPy array (much faster than Pandas DataFrame)
    shape = np.zeros((nRecords,len(columns)), dtype=object)
    for i in range(nRecords):
        shape[i,:] = records[i][0:]
    
    # Then put this into a Pandas DataFrame with the right headers and data types
    shape = pd.DataFrame(shape, columns=columns)
    for col in range(len(columns)):
        if colTypes[col][0] == 'C':
            shape[columns[col]] = shape[columns[col]].astype(str)
        else:
            shape.loc[pd.isna(shape[columns[col]]), columns[col]] = -99999
            if colTypes[col][-1] > 0:
                shape[columns[col]] = shape[columns[col]].astype(float)
            else:
                shape[columns[col]] = shape[columns[col]].astype(int)
    
    if returnGeometry:
        return (shape, geometry)
    else:
        return shape

def create_geojson(output_path, DataFrame, origin_x, origin_y, destination_x, destination_y)    :
    #----- GeoJSON ---
    # print('Writing GeoJSON...') 
    Ax = np.array(DataFrame[origin_x], dtype=str)
    Ay = np.array(DataFrame[origin_y], dtype=str)
    Bx = np.array(DataFrame[destination_x], dtype=str)
    By = np.array(DataFrame[destination_y], dtype=str)
    nTrips = len(DataFrame.index)
    
    with open(output_path, 'w') as geoFile:
        geoFile.write('{\n' + '"type": "FeatureCollection",\n' + '"features": [\n')
        for i in range(nTrips-1):
            outputStr = ""
            outputStr = outputStr + '{ "type": "Feature", "properties": '
            outputStr = outputStr + str(DataFrame.loc[i,:].to_dict()).replace("'",'"')
            outputStr = outputStr + ', "geometry": { "type": "LineString", "coordinates": [ [ '
            outputStr = outputStr + Ax[i] + ', ' + Ay[i] + ' ], [ '
            outputStr = outputStr + Bx[i] + ', ' + By[i] + ' ] ] } },\n'
            geoFile.write(outputStr)
                
        # Bij de laatste feature moet er geen komma aan het einde
        i += 1
        outputStr = ""
        outputStr = outputStr + '{ "type": "Feature", "properties": '
        outputStr = outputStr + str(DataFrame.loc[i,:].to_dict()).replace("'",'"')
        outputStr = outputStr + ', "geometry": { "type": "LineString", "coordinates": [ [ '
        outputStr = outputStr + Ax[i] + ', ' + Ay[i] + ' ], [ '
        outputStr = outputStr + Bx[i] + ', ' + By[i] + ' ] ] } }\n'
        geoFile.write(outputStr)
        geoFile.write(']\n')
        geoFile.write('}')