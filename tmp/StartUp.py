# -*- coding: utf-8 -*-
"""
Created on Wed Oct 27 08:56:07 2021

@author: rtapia
"""



from __functions__ import read_mtx, read_shape, create_geojson, get_traveltime, get_distance
import pandas as pd
import numpy as np
import networkx as nx
from itertools import islice, tee
import math
import sys, os
import time
import ast
import datetime as dt

class HiddenPrints: #
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout
#%%


varDict = {}
'''FOR ALL MODULES'''
cwd = os.getcwd().replace(os.sep, '/')
datapath = cwd.replace('Code', '')

#%% Define all variables
def generate_args(method):
    varDict = {}
    
    '''FOR ALL MODULES'''
    cwd = os.getcwd().replace(os.sep, '/')
    datapath = cwd.replace('Code', '')
    
    if method == 'from_file':   
        params_file = open(f'{datapath}Params.txt')
        for line in params_file:
            if len(line.split('=')) > 1:
                key, value = line.split('=')
                if len(value.split(':')) > 1:
                    value, dtype = value.split(':')
                    if len(dtype.split('#')) > 1: dtype, comment = dtype.split('#')
                    # Allow for spacebars around keys, values and dtypes
                    while key[0] == ' ' or key[0] == '\t': key = key[1:]
                    while key[-1] == ' ' or key[-1] == '\t': key = key[0:-1]
                    while value[0] == ' ' or value[0] == '\t': value = value[1:]
                    while value[-1] == ' ' or value[-1] == '\t': value = value[0:-1]
                    while dtype[0] == ' ' or dtype[0] == '\t': dtype = dtype[1:]
                    while dtype[-1] == ' ' or dtype[-1] == '\t': dtype = dtype[0:-1]
                    dtype = dtype.replace('\n',"")
                    # print(key, value, dtype)
                    if dtype == 'string': varDict[key] = str(value)
                    elif dtype == 'list': varDict[key] = ast.literal_eval(value)
                    elif dtype == 'int': varDict[key] = int(value)               
                    elif dtype == 'float': varDict[key] = float(value)               
                    elif dtype == 'bool': varDict[key] = eval(value)               
                    elif dtype == 'variable': varDict[key] = globals()[value]
                    elif dtype == 'eval': varDict[key] = eval(value)
            
    elif method == 'from_code':
        print('Generating args from code')
        varDict['RUN_DEMAND_MODULE']            = False
        varDict['CROWDSHIPPING_NETWORK']        = True
        varDict['COMBINE_DELIVERY_PICKUP_TOUR'] = True
        varDict['HYPERCONNECTED_NETWORK']       = True
        
        varDict['LABEL']                = 'C2C'
        varDict['DATAPATH']             = datapath
        varDict['INPUTFOLDER']          = f'{datapath}Input/Mass-GT/'
        varDict['OUTPUTFOLDER']         = f'{datapath}Output/Mass-GT/'
        varDict['PARAMFOLDER']	        = f'{datapath}Parameters/Mass-GT/'
        
        varDict['SKIMTIME']             = varDict['INPUTFOLDER'] + 'skimTijd_new_REF.mtx'
        varDict['SKIMDISTANCE']         = varDict['INPUTFOLDER'] + 'skimAfstand_new_REF.mtx'
        varDict['ZONES']                = varDict['INPUTFOLDER'] + 'Zones_v4.shp'
        varDict['SEGS']                 = varDict['INPUTFOLDER'] + 'SEGS2020.csv'
        varDict['PARCELNODES']          = varDict['INPUTFOLDER'] + 'parcelNodes_v2.shp'
        varDict['CEP_SHARES']           = varDict['INPUTFOLDER'] + 'CEPshares.csv'
        
        '''FOR PARCEL MARKET MODULE'''
        varDict['hub_zones']                  = [585]
        varDict['parcelLockers_zones']        = [585]
        varDict['Gemeenten_studyarea']  = [ 
                                            [ 'Delft', 'Midden_Delfland', 'Rijswijk','sGravenhage','Leidschendam_Voorburg',],
                                            # [ 'Rotterdam','Schiedam','Vlaardingen','Ridderkerk', 'Barendrecht',],
                                            
            
                                            # 'Albrandswaard',
                                            # #     'Barendrecht',#
                                            #     'Brielle',
                                            #     'Capelle aan den IJssel',
                                            # #     'Delft', #
                                            #     'Hellevoetsluis',
                                            #     'Krimpen aan den IJssel',
                                            #     'Lansingerland',
                                            # #     'Leidschendam_Voorburg',#
                                            #     'Maassluis',
                                            # #     'Midden_Delfland',#
                                            #     'Nissewaard',
                                            #     'Pijnacker_Nootdorp',
                                            # #     'Ridderkerk',#
                                            # #     'Rijswijk',#
                                            # #     'Rotterdam',#
                                            # #     'Schiedam',#
                                            # #     'Vlaardingen',#
                                            #     'Wassenaar',
                                            #     'Westland',
                                            #     'Westvoorne',
                                            #     'Zoetermeer',
                                            #     # 'sGravenhage'#
                                              ]
        # Hague
        varDict['Gemeenten_CS']         = ["sGravenhage", "Zoetermeer", "Midden_Delfland"]
        varDict['SCORE_ALPHAS']         = [0, 0, 0.1, 1]
        varDict['SCORE_COSTS']          = [0.2, .02, .02, 0,0] # tour_based, consolidated, hub, cs_trans, #interCEP_cost
        varDict['CONSOLIDATED_MAXLOAD'] = 500
        
        '''FOR PARCEL DEMAND MODULE'''
        # Changed parameters to C2X ACM post&pakketmonitor2020 20.8M parcels 
        varDict['PARCELS_PER_HH_C2C']   = 20.8 / 250 / 8.0 # M parcels / days / M HHs 
        varDict['PARCELS_PER_HH_B2C']   = 0.195
        varDict['PARCELS_PER_HH']       = varDict['PARCELS_PER_HH_C2C'] + varDict['PARCELS_PER_HH_B2C']
        varDict['PARCELS_PER_EMPL']     = 0
        varDict['Local2Local']          = 0.04
        varDict['CS_cust_willingness']  = 0.05 # Willingess to SEND a parcel by CS
          
        '''FOR PARCEL SCHEDULING MODULE'''
        varDict['PARCELS_MAXLOAD']      = 180
        varDict['PARCELS_DROPTIME']     = 120
        varDict['PARCELS_SUCCESS_B2C']  = 0.75
        varDict['PARCELS_SUCCESS_B2B']  = 0.95
        varDict['PARCELS_GROWTHFREIGHT']= 1.0
        varDict['CROWDSHIPPING']        = False #SCHED module has own CS integrated, this is not used here
        varDict['CRW_PARCELSHARE']      = 0.1
        varDict['CRW_MODEPARAMS']       = varDict['INPUTFOLDER'] + 'Params_UseCase_CrowdShipping.csv'
        
        '''FOR CROWDSHIPPING MATCHING MODULE'''
        varDict['CS_WILLINGNESS']       = 0.2
        varDict['VOT']                  = '9.00'
        varDict['PARCELS_DROPTIME_CAR'] = 120
        varDict['PARCELS_DROPTIME_BIKE']= 60 #and car passenger
        varDict['PARCELS_DROPTIME_PT']  = 0 #and walk
        varDict['TRIPSPATH']            = f'{datapath}Input/LYON/'
        varDict['CS_BringerScore']      = 'Min_Detour'   # Min_Detour or Surplus 
        varDict['CS_COMPENSATION']      = 'math.log( (dist_parcel_trip) + 2)'   # Min_Detour or Surplus 
        
        '''
        NetworkHyperconnect
        '''
        varDict['HyperConect']  =      {
        # "DHL": ['DPD', 'FedEx', 'GLS', 'PostNL', 'UPS'] ,
        # "DPD": ['DHL', 'FedEx', 'GLS', 'PostNL', 'UPS'] ,
        # "FedEx": ['DPD', 'DHL', 'GLS', 'PostNL', 'UPS'] ,
        # "GLS": ['DPD', 'FedEx', 'DHL', 'PostNL', 'UPS'] ,
        # "PostNL": ['DPD', 'FedEx', 'GLS', 'DHL', 'UPS'] ,
        # "UPS": ['DPD', 'FedEx', 'GLS', 'PostNL', 'DHL'] ,
        # }
    
       "DHL": [] ,
        "DPD": ['FedEx', 'GLS',  'UPS'] ,
        "FedEx": ['DPD',  'GLS',  'UPS'] ,
        "GLS": ['DPD', 'FedEx',  'UPS'] ,
        "PostNL": [] ,
        "UPS": ['DPD', 'FedEx', 'GLS'] ,
        }
    
        # "DHL": [] ,
        # "DPD": [ 'FedEx', 'GLS', 'PostNL', 'UPS'] ,
        # "FedEx": ['DPD', 'GLS', 'PostNL', 'UPS'] ,
        # "GLS": ['DPD', 'FedEx','PostNL', 'UPS'] ,
        # "PostNL": ['DPD', 'FedEx', 'GLS',  'UPS'] ,
        # "UPS": ['DPD', 'FedEx', 'GLS', 'PostNL',] ,
        # }

        # "DHL": [] ,
        # "DPD": [] ,
        # "FedEx": [] ,
        # "GLS": [] ,
        # "PostNL":[] ,
        # "UPS": [] ,
        # }
    
    
    args = ['', varDict]
    return args, varDict

method = 'from_code' #either from_file or from_code
args, varDict = generate_args(method)

TESTRUN = False # True to fasten further code TEST (runs with less parcels)
TestRunLen = 100










#%%


#%% Module 0: Load input data
'''
These variables will be used throughout the whole model
'''

Comienzo = dt.datetime.now()
print ("Comienzo: ",Comienzo)



zones = read_shape(varDict['ZONES'])
zones.index = zones['AREANR']
nZones = len(zones)

skims = {'time': {}, 'dist': {}, }
skims['time']['path'] = varDict['SKIMTIME']
skims['dist']['path'] = varDict['SKIMDISTANCE']
for skim in skims:
    skims[skim] = read_mtx(skims[skim]['path'])
    nSkimZones = int(len(skims[skim])**0.5)
    skims[skim] = skims[skim].reshape((nSkimZones, nSkimZones))
    if skim == 'time': skims[skim][6483] = skims[skim][:,6483] = 5000 # data deficiency
    for i in range(nSkimZones): #add traveltimes to internal zonal trips
        skims[skim][i,i] = 0.7 * np.min(skims[skim][i,skims[skim][i,:]>0])
skimTravTime = skims['time']; skimDist = skims['dist']
skimDist_flat = skimDist.flatten()
del skims, skim, i
    
zoneDict  = dict(np.transpose(np.vstack( (np.arange(1,nZones+1), zones['AREANR']) )))
zoneDict  = {int(a):int(b) for a,b in zoneDict.items()}
invZoneDict = dict((v, k) for k, v in zoneDict.items()) 

segs   = pd.read_csv(varDict['SEGS'])
segs.index = segs['zone']
segs = segs[segs['zone'].isin(zones['AREANR'])] #Take only segs into account for which zonal data is known as well

parcelNodesPath = varDict['PARCELNODES']
parcelNodes = read_shape(parcelNodesPath, returnGeometry=False)
parcelNodes.index   = parcelNodes['id'].astype(int)
parcelNodes         = parcelNodes.sort_index()    

for node in parcelNodes['id']:
    parcelNodes.loc[node,'SKIMNR'] = int(invZoneDict[parcelNodes.at[int(node),'AREANR']])
parcelNodes['SKIMNR'] = parcelNodes['SKIMNR'].astype(int)

cepList   = np.unique(parcelNodes['CEP'])
cepNodes = [np.where(parcelNodes['CEP']==str(cep))[0] for cep in cepList]

cepNodeDict = {}; cepZoneDict = {}; cepSkimDict = {}
for cep in cepList: 
    cepZoneDict[cep] = parcelNodes[parcelNodes['CEP'] == cep]['AREANR'].astype(int).tolist()
    cepSkimDict[cep] = parcelNodes[parcelNodes['CEP'] == cep]['SKIMNR'].astype(int).tolist()
for cepNo in range(len(cepList)):
    cepNodeDict[cepList[cepNo]] = cepNodes[cepNo]

KPIs = {}

#%%















