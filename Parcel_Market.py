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
import json






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
datapath = cwd.replace('Code', '')# + "/Parcel_Market"



#%% Define all variables
def generate_args(method):
    varDict = {}
   
    '''FOR ALL MODULES'''
    cwd = os.getcwd().replace(os.sep, '/')
    datapath = cwd.replace('Code', '')
    
    if method == 'from_file':   
            
        if sys.argv[0] == '':
            params_file = open(f'{datapath}/Input/Params_ParcelMarket.txt')
            
            # This are the defaults, might need to change for console run!!!
            varDict['LABEL'	]			= 'Test'				
            varDict['DATAPATH']			= datapath							
            varDict['INPUTFOLDER']		= f'{datapath}'+'/'+ 'Input' +'/' 				
            varDict['OUTPUTFOLDER']		= f'{datapath}'+'/'+ 'Output' +'/'			
            
            varDict['Parcels']              = varDict['INPUTFOLDER'] + 'Demand_parcels_fulfilment_test.csv'     

            varDict['SKIMTIME'] 		= varDict['INPUTFOLDER'] + 'skimTijd_new_REF.mtx' #'skimTijd_new_REF.mtx' 		
            varDict['SKIMDISTANCE']		= varDict['INPUTFOLDER'] + 'skimAfstand_new_REF.mtx' #'skimAfstand_new_REF.mtx'	
            varDict['ZONES']			= varDict['INPUTFOLDER'] + 'Zones_v4.shp' #'Zones_v4.shp'				
            varDict['SEGS']				= varDict['INPUTFOLDER'] + 'SEGS2020.csv' #'SEGS2020.csv'				
            varDict['PARCELNODES']		= varDict['INPUTFOLDER'] + 'parcelNodes_v2.shp'				
            varDict['Pax_Trips']        = varDict['INPUTFOLDER'] + 'trips_Hague_Albatross.csv'	# trips.csv		            # varDict['LABEL'	]			= sys.argv[1]				
            # varDict['DATAPATH']			= datapath							
            # varDict['INPUTFOLDER']		= f'{datapath}'+ sys.argv[2] +'/' 				
            # varDict['OUTPUTFOLDER']		= f'{datapath}'+ sys.argv[3] +'/'			
            
            # varDict['SKIMTIME'] 		= varDict['INPUTFOLDER'] +'skimTijd_new_REF.mtx' 		
            # varDict['SKIMDISTANCE']		= varDict['INPUTFOLDER'] + 'skimAfstand_new_REF.mtx'	
            # varDict['ZONES']			= varDict['INPUTFOLDER'] + 'Zones_v4.shp'				
            # varDict['SEGS']				= varDict['INPUTFOLDER'] + 'SEGS2020.csv'				
            # varDict['PARCELNODES']		= varDict['INPUTFOLDER'] + 'parcelNodes_v2.shp'				
            # varDict['Pax_Trips']        = varDict['INPUTFOLDER'] +'trips.csv'       
            
            
            
            
        else:  # This is the part for line cod execution
            locationparam = f'{datapath}'+'/' + sys.argv[2] +'/' + sys.argv[4]
            params_file = open(locationparam)
            varDict['LABEL'	]			= sys.argv[1]				
            varDict['DATAPATH']			= datapath							
            varDict['INPUTFOLDER']		= f'{datapath}'+'/'+ sys.argv[2] +'/' 				
            varDict['OUTPUTFOLDER']		= f'{datapath}'+'/'+ sys.argv[3] +'/'			
            
            varDict['Parcels']              = varDict['INPUTFOLDER'] + sys.argv[5]     

            varDict['SKIMTIME'] 		= varDict['INPUTFOLDER'] + sys.argv[6] #'skimTijd_new_REF.mtx' 		
            varDict['SKIMDISTANCE']		= varDict['INPUTFOLDER'] + sys.argv[7] #'skimAfstand_new_REF.mtx'	
            varDict['ZONES']			= varDict['INPUTFOLDER'] + sys.argv[8] #'Zones_v4.shp'				
            varDict['SEGS']				= varDict['INPUTFOLDER'] + sys.argv[9] #'SEGS2020.csv'				
            varDict['PARCELNODES']		= varDict['INPUTFOLDER'] + sys.argv[10] #'parcelNodes_v2.shp'				
            varDict['Pax_Trips']        = varDict['INPUTFOLDER'] + sys.argv[11]	# trips.csv		
            # So it shuts up the warnings (remove when running in spyder)
            pd.options.mode.chained_assignment = None
       





        for line in params_file:
            if len(line.split('=')) > 1:
                key, value = line.split('=')
                if len(value.split(';')) > 1:
                    # print(value)
                    value, dtype = value.split(';')
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
        # varDict['RUN_DEMAND_MODULE']            = False
        varDict['CROWDSHIPPING_NETWORK']        = True
        varDict['COMBINE_DELIVERY_PICKUP_TOUR'] = True
        varDict['HYPERCONNECTED_NETWORK']       = True
        
        varDict['LABEL']                = 'C2C'
        varDict['DATAPATH']             = datapath + '/'
        varDict['INPUTFOLDER']          = varDict['DATAPATH']+'Input/'
        varDict['OUTPUTFOLDER']         = varDict['DATAPATH']+'Output/'
        # varDict['PARAMFOLDER']	        = f'{datapath}Parameters/Mass-GT/'
        
        varDict['Parcels']              = varDict['INPUTFOLDER'] + 'Demand_parcels_fulfilmenttest.csv'        
        varDict['SKIMTIME']             = varDict['INPUTFOLDER'] + 'skimTijd_new_REF.mtx'
        varDict['SKIMDISTANCE']         = varDict['INPUTFOLDER'] + 'skimAfstand_new_REF.mtx'
        varDict['ZONES']                = varDict['INPUTFOLDER'] + 'Zones_v4.shp'
        varDict['SEGS']                 = varDict['INPUTFOLDER'] + 'SEGS2020.csv'
        varDict['PARCELNODES']          = varDict['INPUTFOLDER'] + 'parcelNodes_v2.shp'
        varDict['CEP_SHARES']           = varDict['INPUTFOLDER'] + 'CEPshares.csv'
        varDict['Pax_Trips']            = varDict['INPUTFOLDER'] + 'trips.csv'
        
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
        # varDict['PARCELS_PER_HH_C2C']   = 20.8 / 250 / 8.0 # M parcels / days / M HHs 
        # varDict['PARCELS_PER_HH_B2C']   = 0.195
        # varDict['PARCELS_PER_HH']       = varDict['PARCELS_PER_HH_C2C'] + varDict['PARCELS_PER_HH_B2C']
        # varDict['PARCELS_PER_EMPL']     = 0
        # varDict['Local2Local']          = 0.04
        # varDict['CS_cust_willingness']  = 0.05 # Willingess to SEND a parcel by CS
          
        '''FOR PARCEL SCHEDULING MODULE'''
        # varDict['PARCELS_MAXLOAD']      = 180
        # varDict['PARCELS_DROPTIME']     = 120
        # varDict['PARCELS_SUCCESS_B2C']  = 0.75
        # varDict['PARCELS_SUCCESS_B2B']  = 0.95
        # varDict['PARCELS_GROWTHFREIGHT']= 1.0
        # varDict['CROWDSHIPPING']        = False #SCHED module has own CS integrated, this is not used here
        # varDict['CRW_PARCELSHARE']      = 0.1
        # varDict['CRW_MODEPARAMS']       = varDict['INPUTFOLDER'] + 'Params_UseCase_CrowdShipping.csv'
        
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
Comienzo = dt.datetime.now()
print ("Comienzo: ",Comienzo)    

method = 'from_file' #either from_file or from_code
args, varDict = generate_args(method)

TESTRUN = varDict['TESTRUN']    # True to fasten further code TEST (runs with less parcels)
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

'''
Model Starts

'''





#%%
def k_shortest_paths(G, source, target, k, weight=None):
    return list(islice(nx.shortest_simple_paths(G, source, target, weight=weight), k))


def pairwise(iterable):
    a, b = tee(iterable); next(b, None); return zip(a, b)
    
    
def get_compensation(dist_parcel_trip):
    compensation = eval(varDict['CS_COMPENSATION'])
    return compensation


def calc_score(u, v, d): #from, to, attributes (dict)
    X1_travtime = d['travtime']/3600 # Time in hours
    X2_length = d['length']/1000     # Distance in km
    
    ASC, A1, A2, A3 = varDict['SCORE_ALPHAS']
    tour_based_cost, consolidated_cost, hub_cost, cs_trans_cost ,interCEP_cost= varDict['SCORE_COSTS']
    
    if d['network'] == 'conventional' and d['type'] in['consolidated']: X2_length = X2_length/50
    
    
    if u == orig or v == dest: return 0 # access and agress links to the network have score of 0
    if G.nodes[u]['node_type'] == 'zone' and u not in {orig, dest}: return 99999 #other zones than orig/dest can not be used
    if d['type'] == 'access-egress': return 0
    if d['network'] == 'crowdshipping' and u not in allowed_cs_nodes: return 99999 #CS network except for certain nodes can not be used 

    if not varDict['HYPERCONNECTED_NETWORK']: 
        if d['network'] == 'conventional' and d['CEP'] != parcel['CEP']: return 99999 #Other conventional carriers can not be used
    else:
        if d['network'] == 'conventional' and d['CEP'] != parcel['CEP'] and d['CEP'] not in HyperConect[parcel['CEP']]: return 99999 #only hub nodes may be used (no hub network at CEP depots), one directional only   
        else: X3_cost = interCEP_cost
    
            
    
    if d['network'] == 'conventional' and d['type'] == 'hub' and v not in hub_nodes: return 99999 #only hub nodes may be used (no hub network at CEP depots)
    if d['network'] == 'conventional' and d['type'] in['tour-based']: X3_cost = tour_based_cost
    if d['network'] == 'conventional' and d['type'] in['consolidated']: X3_cost = consolidated_cost
    if d['network'] == 'conventional' and d['type'] in['hub']: X3_cost = hub_cost
    
    if d['network'] == 'crowdshipping': X3_cost = get_compensation(X2_length)
    
    if d['network'] == 'transshipment' and d['type'] == 'CS': X3_cost = cs_trans_cost
    if d['network'] == 'transshipment' and d['type'] == 'hub': X3_cost = hub_cost
    
    score = ASC + A1*X1_travtime + A2 * X2_length + A3*X3_cost 
    return score

#%%   Module 2: Network creation

def actually_run_module(args):
    root    = args[0]
    varDict = args[1]
    
    
    # Read files from other modules
    
    # parcels_hyperconnected = pd.read_csv(f"{varDict['INPUTFOLDER']}Demand_parcels_hyperconnected.csv"); parcels_hyperconnected.index = parcels_hyperconnected['Parcel_ID']
    # parcels_hubspoke = pd.read_csv(f"{varDict['DATAPATH']}Input/Demand_parcels_hubspoke.csv"); parcels_hubspoke.index = parcels_hubspoke['Parcel_ID']
    # parcels = pd.read_csv(f"{varDict['DATAPATH']}Input/Demand_parcels.csv");    parcels.index = parcels['Parcel_ID']

    parcels = pd.read_csv(varDict['Parcels']);    parcels.index = parcels['Parcel_ID']

    parcels_hubspoke = parcels [parcels['Fulfilment']=='Hubspoke']
    
    parcels_hubspoke= parcels_hubspoke.drop(['L2L',"CS_eligible","DepotNumber","Fulfilment"], axis=1) 
    
    
    parcels_hyperconnected = parcels [parcels['Fulfilment']=='Hyperconnected']
    parcels_hyperconnected= parcels_hyperconnected.drop(['D_DepotNumber', 'D_DepotZone', 'Fulfilment','O_DepotNumber', 'O_DepotZone'], axis=1) 

    
    
    print("Create network...")
    
    '''
    The hyperconnected network is createdusing NetworkX. Each courier/network has its own layer in the graph.
    Layers are connected to the zones using access-egress links. Transshipment could take place at depots or hub_zones.
    Following attributes are assigned and used later for network allocation according to cost function
    Nodes have one attribute:
        node_type: zone, node, parcelNode, hub
    Links have 5 attributes:
        lenth
        travtime
        network: conventional, crowdshipping, transshipment
        type: access-egress, tour-based, consolidated, individual (in case of CS), hub, CS
        CEP: conventional carriers (only when network == conventional)
    '''
    
    G = nx.Graph() #initiate NetworkX graph
    [G.add_node(zoneID, **{'node_type':'zone'}) for zoneID in zones['AREANR']] #add all zones to network
    
    ''' Conventional carrier networks following hub-spoke structure '''
    for cep in cepList[:]:
        for zoneID in zones['AREANR'][:]: #connect each zone to closest parcelnode
            G.add_node(f"{zoneID}_{cep}", **{'node_type':'node'})
            parcelNode = cepZoneDict[cep][skimTravTime[invZoneDict[zoneID]-1,cepSkimDict[cep]].argmin()]
            attrs = {
                'length': skimDist[invZoneDict[zoneID]-1,invZoneDict[parcelNode]-1],
                'travtime': skimTravTime[invZoneDict[zoneID]-1,invZoneDict[parcelNode]-1],
                'network': 'conventional',
                'type': 'tour-based',
                'CEP': cep}
            G.add_edge(f"{zoneID}_{cep}", f"{parcelNode}_{cep}", **attrs)
            attrs = {'length': 0,'travtime': 0, 'network': 'conventional', 'type': 'access-egress', 'CEP': cep}
            G.add_edge(zoneID, f"{zoneID}_{cep}", **attrs)
        for parcelNode in cepZoneDict[cep]: #connect parcelnodes from one carrier to eachother
            nx.set_node_attributes(G, {f"{parcelNode}_{cep}":'parcelNode'}, 'node_type')
            for other_node in cepZoneDict[cep]:
                if parcelNode == other_node: continue
                attrs = {
                    'length': skimDist[invZoneDict[parcelNode]-1,invZoneDict[other_node]-1],
                    'travtime': skimTravTime[invZoneDict[parcelNode]-1,invZoneDict[other_node]-1],
                    'network': 'conventional',
                    'type': 'consolidated',
                    'CEP': cep}
                G.add_edge(f"{parcelNode}_{cep}", f"{other_node}_{cep}", **attrs)
    
    ''' Crowdshipping network, fully connected graph '''
    if varDict['CROWDSHIPPING_NETWORK']:
        Gemeenten = varDict['Gemeenten_CS'] #select municipalities where CS could be done
        for orig in zones['AREANR'][zones['GEMEENTEN'].isin(Gemeenten)]:
            for dest in zones['AREANR'][zones['GEMEENTEN'].isin(Gemeenten)]:
                if orig < dest: #this is an undirected graph; only one direction should be included
                    attrs = {
                        'length': skimDist[invZoneDict[orig]-1,invZoneDict[dest]-1],
                        'travtime': skimTravTime[invZoneDict[orig]-1,invZoneDict[dest]-1],
                        'network': 'crowdshipping',
                        'type': 'individual'}
                    if attrs['length'] < 10000:
                        G.add_edge(f"{orig}_CS", f"{dest}_CS", **attrs)
            nx.set_node_attributes(G, {f"{orig}_CS":'node'}, 'node_type')
            attrs = {'length': 0,'travtime': 0, 'network': 'crowdshipping', 'type': 'access-egress'}
            G.add_edge(orig, f"{orig}_CS", **attrs)
    
    '''Transshipment links'''
    #Conventional - Crowdshipping
    CS_transshipment_nodes = []
    if varDict['CROWDSHIPPING_NETWORK']:    
        for cep in cepList[:]:
            for parcelNode in cepZoneDict[cep]:
                attrs = {'length': 0,'travtime': 0, 'network': 'transshipment', 'type': 'CS'}
                if f'{parcelNode}_CS' in G:
                    G.add_edge(f"{parcelNode}_{cep}", f"{parcelNode}_CS", **attrs)
                    CS_transshipment_nodes.append(f"{parcelNode}_CS")
                
    for cep in cepList[:]:
        for parcelNode in cepZoneDict[cep]: 
            attrs = {'length': 0,'travtime': 0, 'network': 'transshipment', 'type': 'CS'}
            if f'{parcelNode}_CS' in G:
                G.add_edge(f"{parcelNode}_{cep}", f"{parcelNode}_CS", **attrs)
                CS_transshipment_nodes.append(f"{parcelNode}_CS")
                    
    '''Logistical hubs'''
    for hub_zone in varDict['hub_zones']:
        G.add_node(f"{hub_zone}_hub", **{'node_type':'hub'})
        for cep in cepList:
            closest = cepZoneDict[cep][skimTravTime[invZoneDict[hub_zone]-1,[x-1 for x in cepSkimDict[cep]]].argmin()]
            attrs = {'length': 0,'travtime': 0, 'network': 'conventional', 'type': 'hub', 'CEP': cep}
            G.add_edge(f"{hub_zone}_hub", f"{closest}_{cep}", **attrs)
        if varDict['CROWDSHIPPING_NETWORK']:
            for orig in zones['AREANR'][zones['GEMEENTEN'].isin(Gemeenten)]:
                attrs = {
                    'length': skimDist[invZoneDict[hub_zone]-1,invZoneDict[orig]-1],
                    'travtime': skimTravTime[invZoneDict[hub_zone]-1,invZoneDict[orig]-1],
                    'network': 'crowdshipping',
                    'type': 'individual'}
                G.add_edge(f"{hub_zone}_hub", f"{orig}_CS", **attrs)
            CS_transshipment_nodes.append(f"{hub_zone}_hub")
    hub_nodes = [str(s) + '_hub' for s in varDict['hub_zones']] 
    
    
    
    '''Parcel Lockers'''
    #for locker in varDict['parcelLockers_zones']:
    #    G.add_node(f"{hub_zone}_locker", **{'node_type':'locker'})
    #    for cep in cepList:
    #        closest = cepZoneDict[cep][skimTravTime[invZoneDict[hub_zone]-1,[x-1 for x in cepSkimDict[cep]]].argmin()]
    #        attrs = {'length': 0,'travtime': 0, 'network': 'conventional', 'type': 'hub', 'CEP': cep}
    #        G.add_edge(f"{hub_zone}_hub", f"{closest}_{cep}", **attrs)
    #    for orig in zones['AREANR'][zones['GEMEENTEN'].isin(Gemeenten)]:
    #        attrs = {
    #            'length': skimDist[invZoneDict[hub_zone]-1,invZoneDict[orig]-1],
    #            'travtime': skimTravTime[invZoneDict[hub_zone]-1,invZoneDict[orig]-1],
    #            'network': 'crowdshipping',
    #            'type': 'individual'}
    #        G.add_edge(f"{hub_zone}_hub", f"{orig}_CS", **attrs)
    #    CS_transshipment_nodes.append(f"{hub_zone}_hub")
    #hub_nodes = [str(s) + '_hub' for s in varDict['hub_zones']] 
    
    
    '''Hyperconnect'''
    
    HyperConect = varDict['HyperConect']
    
    
    if varDict['HYPERCONNECTED_NETWORK']:
    
        for cep in cepList[:]:
            for parcelNode in cepZoneDict[cep]:
                for other_cep in HyperConect[cep]:
                    # if cep == other_cep: continue
                    for other_node in cepZoneDict[other_cep]:
                        attrs = {
                        'length': skimDist[invZoneDict[parcelNode]-1,invZoneDict[other_node]-1],
                        'travtime': skimTravTime[invZoneDict[parcelNode]-1,invZoneDict[other_node]-1],
                        'network': 'conventional',
                        'type': 'consolidated',
                        'CEP': cep}
                        G.add_edge(f"{parcelNode}_{cep}", f"{other_node}_{other_cep}", **attrs)
            
        if G.has_edge('3362_UPS', '4604_DPD'): print("Hyperconnected")
        else:  print("Not hyperconnected yet")
        
    
    #%% Module 3: Network allocation
    print('Perform network allocation...')
    
    '''
    Each parcel is allocated to some route over the network. This could be a single layer, or combination of them
    The allocation is based on a shortest path algorithm using a score function. 
    The score is now based on travtime, length and cost, but could be extended to 
        network attibutes (reliability, time windows) and parcel attributes (weight, size, ...)
    All is fed into a score function to determine the best x (1 or more) routes.
        If only 1 best route is chosen, this is more like a all-or-nothing assignment. 
        With more best routes, these could be fed into a logit model to pick the chosen route
    '''
    
    
    # print(varDict['SCORE_COSTS'])
    ASC, A1, A2, A3 = varDict['SCORE_ALPHAS']
    tour_based_cost, consolidated_cost, hub_cost, cs_trans_cost ,interCEP_cost= varDict['SCORE_COSTS']
    
    globals() ['varDict'] = varDict         # Temporary solution when it's needed to run within a function
    globals() ['HyperConect'] = HyperConect
    globals() ['hub_nodes'] = hub_nodes
    # globals() ['allowed_cs_nodes'] = allowed_cs_nodes
    # globals() ['allowed_cs_nodes'] = allowed_cs_nodes





    if TESTRUN: parcels_hyperconnected = parcels_hyperconnected[:TestRunLen] #for testrun, state TESTRUN = True (end of module 0)
    
    parcels_hyperconnected['path'] = type('object')
    
    # i = 0
    
    for index, parcel in parcels_hyperconnected.iterrows():
        # i+=1
        orig = parcel['O_zone']
        dest = parcel['D_zone']
        globals() ['orig'] = orig         # Temporary solution when it's needed to run within a function
        globals() ['dest'] = dest
        globals() ['G'] = G
        globals() ['parcel'] = parcel



        if parcel['CS_eligible'] == True:   # This is too slow!!!!!!!! TODO: improve
            k = 1; allowed_cs_nodes = CS_transshipment_nodes + [f'{orig}_CS', f'{dest}_CS']
        else:
            k = 1; allowed_cs_nodes = []
        globals() ['allowed_cs_nodes'] = allowed_cs_nodes

        shortest_paths = k_shortest_paths(G, orig, dest, k, weight = lambda u, v, d: calc_score(u, v, d=G[u][v]))
        for path in shortest_paths:
            weightSum = 0
            for pair in pairwise(path):
                weightSum += calc_score(pair[0], pair[1], G.get_edge_data(pair[0],pair[1]))
        parcels_hyperconnected.at[index,'path'] = shortest_paths[0]
        parcels_hyperconnected.at[index,'weightSum'] = weightSum
        # print(i,"  from  ", len(parcels_hyperconnected))




    
    #%% Module 3.5 Parcel trips breakdown
    print('Parcels network breakdown...')
    '''
    Break down the parcel trip into it's different trips
    This enables a distinction between networks as well as different types (individual, tour-based, consolidated)
    '''
    cols = ['Parcel_ID', 'O_zone', 'D_zone', 'CEP', 'Network', 'Type']
    parcel_trips = pd.DataFrame(columns=cols) #initiate dataframe with above stated columns
    parcel_trips = parcel_trips.astype({'Parcel_ID': int,'O_zone': int, 'D_zone': int})
    # i=0
    for index, parcel in parcels_hyperconnected.iterrows():
        # i+=1
        path = parcels_hyperconnected.at[index,'path']
        path = path[1:-1] #remove the first and last node from path (these are the access/egress links)
        for pair in pairwise(path):
            orig = int(pair[0].split("_")[0]) #remove network from node name (only keep zone number)
            dest = int(pair[1].split("_")[0])
            network = G[pair[0]][pair[1]]['network']
            edge_type = G[pair[0]][pair[1]]['type']
            cep = ''
            if network == 'conventional': cep = G[pair[0]][pair[1]]['CEP'] #CEP only applicable to conventional links
            parcel_trips = parcel_trips.append(pd.DataFrame([[parcel['Parcel_ID'], orig, dest, cep, network, edge_type]], columns=cols), ignore_index=True) #add trip to dataframe
        # print(i,"  from  ", len(parcels_hyperconnected))
    
    #%% Module 4.1: Parcel assignment: CROWDSHIPPING
    print("Allocate crowdshipping parcels...")
    '''
    Allocate the crowdshipping parcels using the CS matching module
    Furthermore, unmatched parcels (of which no driver could be found) are seperated to be allocated in the conventional network
    '''

    if varDict['CROWDSHIPPING_NETWORK']:
        parcel_trips_CS = parcel_trips[parcel_trips['Network'] == 'crowdshipping'] #select only trips using crowdshipping
        parcel_trips_CS_unmatched_pickup, parcel_trips_CS_unmatched_delivery = pd.DataFrame(), pd.DataFrame()
        if not parcel_trips_CS.empty:
            out = f"{varDict['OUTPUTFOLDER']}Parcels_CS_{varDict['LABEL']}.csv"
            parcel_trips_CS.to_csv(out, index=False) # write those trips to csv (default location of parcel demand for scheduling module)
            
            
            
            from LEAD_module_CS import actually_run_module #load right module
            actually_run_module(args) #run module
            parcel_trips_CS = pd.read_csv(f"{varDict['OUTPUTFOLDER']}Parcels_CS_matched_{varDict['LABEL']}.csv") #load module output to dataframe
            
            # TODO 
            # TO DO
            # See what happens when there are no unmatched
            parcel_trips_CS_unmatched = parcel_trips_CS.drop(parcel_trips_CS[parcel_trips_CS['traveller'].notna()].index) #get unmatched parcels
            parcel_trips_CS_unmatched.loc[:,'Network'] = 'conventional' #will be shiped conventionally 
            parcel_trips_CS_unmatched.loc[:,'Type'] = 'tour-based' #will be tour-based
            parcel_trips_CS_unmatched = parcel_trips_CS_unmatched.drop(['traveller', 'detour', 'compensation'], axis=1) #drop unnessecary columns
            
            #most CS occurs at delivery, some are for pickup. These will be filered out here:
            parcel_trips_CS_unmatched_pickup = pd.DataFrame(columns = parcel_trips_CS_unmatched.columns) 
            parcel_trips_CS_unmatched_delivery = pd.DataFrame(columns = parcel_trips_CS_unmatched.columns) 
            for index, parcel in parcel_trips_CS_unmatched.iterrows():
                cep = parcels.loc[parcel['Parcel_ID'], 'CEP']
                if parcel['D_zone'] != parcels.loc[parcel['Parcel_ID'], 'D_zone']: #it is pickup if the CS destination is not the final destination
                    parcel_trips_CS_unmatched_pickup = parcel_trips_CS_unmatched_pickup.append(parcel,sort=False) #add cs parce lto pick-up dataframe
                    parcel_trips_CS_unmatched_pickup.loc[index, 'CEP'] = cep #add original cep to parcel
                    parcel_trips_CS_unmatched_pickup.loc[index, 'D_zone'] = cepZoneDict[cep][skimTravTime[invZoneDict[parcel['O_zone']]-1,[x-1 for x in cepSkimDict[cep]]].argmin()] #change destination to closest depot
                else: #for CS delivery parcels
                    parcel_trips_CS_unmatched_delivery = parcel_trips_CS_unmatched_delivery.append(parcel,sort=False) #add cs parce lto pick-up dataframe
                    parcel_trips_CS_unmatched_delivery.loc[index, 'CEP'] = cep #add original cep to parcel
                    parcel_trips_CS_unmatched_delivery.loc[index, 'O_zone'] = cepZoneDict[cep][skimTravTime[invZoneDict[parcel['D_zone']]-1,[x-1 for x in cepSkimDict[cep]]].argmin()] #change origin to closest depot
        
    #%% Module 4.2: Parcel assignment: CONVENTIONAL
    print("Allocate parcel trips to conventional networks")
    '''
    Allocate the conventional parcels using the MASS-GT Parcel Scheduling module
    For this, the conventional parcels are splitted into delivery and pickup trips
    '''
    error = 0
    parcel_trips_HS_delivery = parcel_trips.drop_duplicates(subset = ["Parcel_ID"], keep='last') #pick the final part of the parcel trip
    parcel_trips_HS_delivery = parcel_trips_HS_delivery[((parcel_trips_HS_delivery['Network'] == 'conventional') & (parcel_trips_HS_delivery['Type'] == 'tour-based'))] #only take parcels which are conventional & tour-based
    if varDict['CROWDSHIPPING_NETWORK']: parcel_trips_HS_delivery = parcel_trips_HS_delivery.append(parcel_trips_CS_unmatched_delivery, ignore_index=True,sort=False) #add unmatched CS as well
    
    parcel_trips_HS_delivery.insert(3, 'DepotNumber', np.nan) #add depotnumer column
    for index, parcel in parcel_trips_HS_delivery.iterrows(): #loop over parcels
        try:
            parcel_trips_HS_delivery.at[index, 'DepotNumber'] = parcelNodes[((parcelNodes['CEP'] == parcel['CEP']) & (parcelNodes['AREANR'] == parcel['O_zone']))]['id'] #add depotnumer to each parcel
        except:
            parcel_trips_HS_delivery.at[index, 'DepotNumber'] = parcelNodes[((parcelNodes['CEP'] == parcel['CEP']))]['id'].iloc[0] # Get first node as an exception
            error +=1
    out = f"{varDict['OUTPUTFOLDER']}ParcelDemand_HS_delivery_{varDict['LABEL']}.csv"
    parcel_trips_HS_delivery.to_csv( out, index=False) #output these parcels to default location for scheduling
    
   
    
    
    parcel_trips_HS_pickup = parcel_trips.drop_duplicates(subset = ["Parcel_ID"], keep='first') #pick the first part of the parcel trip
    parcel_trips_HS_pickup = parcel_trips_HS_pickup[((parcel_trips_HS_pickup['Network'] == 'conventional') & (parcel_trips_HS_pickup['Type'] == 'tour-based'))] #only take parcels which are conventional & tour-based
    
    
    
    
    Gemeenten = varDict['Gemeenten_studyarea']
    
    if len(Gemeenten) > 1:  # If there are more than 1 gemente in the list
        parcel_trips_HS_pickupIter = pd.DataFrame(columns = parcel_trips_HS_pickup.columns)
    
        for Geemente in Gemeenten:
            if type (Geemente) != list: # If there the cities are NOT connected (that is every geemente is separated from the next)
            
            
                ParcelTemp = parcel_trips_HS_pickup[parcel_trips_HS_pickup['O_zone'].isin(zones['AREANR'][zones['GEMEENTEN']==Geemente])] #only take parcels picked-up in the study area
    
    
                parcel_trips_HS_pickupIter = parcel_trips_HS_pickupIter.append(ParcelTemp)
            else:
                ParcelTemp = parcel_trips_HS_pickup[parcel_trips_HS_pickup['O_zone'].isin(zones['AREANR'][zones['GEMEENTEN'].isin(Geemente)])]
    
                parcel_trips_HS_pickupIter = parcel_trips_HS_pickupIter.append(ParcelTemp)
            
        parcel_trips_HS_pickup = parcel_trips_HS_pickupIter
      
    else:    # print(len(ParceltobeL2L))
        if type (Gemeenten[0]) == list:
            Geemente = Gemeenten [0]
        else:
            Geemente = Gemeenten
        parcel_trips_HS_pickup = parcel_trips_HS_pickup[parcel_trips_HS_pickup['O_zone'].isin(zones['AREANR'][zones['GEMEENTEN'].isin(Geemente)])] #only take parcels picked-up in the study area
    
    
    
    
    
    if varDict['CROWDSHIPPING_NETWORK']: parcel_trips_HS_pickup = parcel_trips_HS_pickup.append(parcel_trips_CS_unmatched_pickup, ignore_index=True,sort=False) #add unmatched CS as well
    
    parcel_trips_HS_pickup.insert(3, 'DepotNumber', np.nan) #add depotnumer column
    
    error2 = 0
    for index, parcel in parcel_trips_HS_pickup.iterrows(): #loop over parcels
        try:
            parcel_trips_HS_pickup.at[index, 'DepotNumber'] = parcelNodes[((parcelNodes['CEP'] == parcel['CEP']) & (parcelNodes['AREANR'] == parcel['D_zone']))]['id'] #add depotnumer to each parcel
        except:
            parcel_trips_HS_pickup.at[index, 'DepotNumber'] = parcelNodes[((parcelNodes['CEP'] == parcel['CEP']) )]['id'].iloc[0] #add depotnumer to each parcel
            error2 += 1
    
    out = f"{varDict['OUTPUTFOLDER']}ParcelDemand_HS_pickup_{varDict['LABEL']}.csv"
    parcel_trips_HS_pickup.to_csv(out, index=False) #output these parcels to default location for scheduling
    
    
    out = f"{varDict['OUTPUTFOLDER']}ParcelDemand_ParcelTrips_{varDict['LABEL']}.csv"
    parcel_trips.to_csv(out, index=False)
    
    
    
    
    
    
    

    
    #%% OUTPUTS
    
    
    
    
    
    """
    
    The outputs are
    
    
    
    """
    
    
    
    
    if varDict['CROWDSHIPPING_NETWORK']: 
        KPIs['crowdshipping_parcels'] = len(parcel_trips_CS)
        if KPIs['crowdshipping_parcels'] > 0:
            KPIs['crowdshipping_parcels_matched'] = parcel_trips_CS['trip'].notna().sum()
            KPIs['crowdshipping_match_percentage'] = round((KPIs['crowdshipping_parcels_matched']/KPIs['crowdshipping_parcels'])*100,1)
            KPIs['crowdshipping_detour_sum'] = int(parcel_trips_CS['detour'].sum())
            KPIs['crowdshipping_detour_avg'] = round(parcel_trips_CS['detour'].mean(),2)
            KPIs['crowdshipping_compensation'] = round(parcel_trips_CS['compensation'].mean(),2)

    KPIfile = varDict['OUTPUTFOLDER'] + 'KPI_' + varDict['LABEL']+'.json'
    
    # Write KPIs as Json
    
    
    # For some reason, json doesn't like np.int or floats
    for index, key in enumerate(KPIs):
        # print(key)
        if type(KPIs[key]) == 'dict':
            for i,k in enumerate (key):
                print(k)
                if type(key[k]) == 'dict':
                    for j,l in enumerate(k):
                        try:
                            val = k[l].item() 
                            k[l] = val
                            key[k] = k
                        except:
                            a=1
                else:
                    try:
                        val = key[k].item() 
                        key[k] = val
                        KPIs[key] = key
                    except:
                        a=1
        else:
            try:
                val = KPIs[key].item()  
                KPIs[key] = val
            except:
                a=1
   
    
    f = open(KPIfile, "w")
    json.dump(KPIs, f,indent = 2)
    f.close()
    
    
    KPI_Json = json.dumps(KPIs, indent = 2) 
    if varDict['printKPI'] :
        print(KPI_Json)


    return ()







actually_run_module(args)



End = dt.datetime.now()
print ("duration: ",End - Comienzo)    




