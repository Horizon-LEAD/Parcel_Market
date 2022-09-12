# -*- coding: utf-8 -*-
"""
Created on Wed Oct 27 09:00:25 2021

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



from  StartUp import *

class HiddenPrints: #
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout
#%%


# varDict = {}
# '''FOR ALL MODULES'''
# cwd = os.getcwd().replace(os.sep, '/')
# datapath = cwd.replace('Code', '')



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
    
    parcels_hyperconnected = pd.read_csv(f"{varDict['DATAPATH']}Output/Demand_parcels_hyperconnected.csv"); parcels_hyperconnected.index = parcels_hyperconnected['Parcel_ID']
    parcels_hubspoke = pd.read_csv(f"{varDict['DATAPATH']}Output/Demand_parcels_hubspoke.csv"); parcels_hubspoke.index = parcels_hubspoke['Parcel_ID']
    parcels = pd.read_csv(f"{varDict['DATAPATH']}Output/Demand_parcels.csv");    parcels.index = parcels['Parcel_ID']

    
    
    
    
    
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
    
    
    
    ASC, A1, A2, A3 = varDict['SCORE_ALPHAS']
    tour_based_cost, consolidated_cost, hub_cost, cs_trans_cost ,interCEP_cost= varDict['SCORE_COSTS']
    
    globals() ['varDict'] = varDict         # Temporary solution when it's needed to run within a function
    globals() ['HyperConect'] = HyperConect
    globals() ['hub_nodes'] = hub_nodes
    # globals() ['allowed_cs_nodes'] = allowed_cs_nodes
    # globals() ['allowed_cs_nodes'] = allowed_cs_nodes





    if TESTRUN: parcels_hyperconnected = parcels_hyperconnected[:TestRunLen] #for testrun, state TESTRUN = True (end of module 0)
    
    parcels_hyperconnected['path'] = type('object')
    for index, parcel in parcels_hyperconnected.iterrows():
        orig = parcel['O_zone']
        dest = parcel['D_zone']
        globals() ['orig'] = orig         # Temporary solution when it's needed to run within a function
        globals() ['dest'] = dest
        globals() ['G'] = G
        globals() ['parcel'] = parcel



        if parcel['CS_eligible'] == True:
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
    
    #%% Module 3.5 Parcel trips breakdown
    print('Parcels network breakdown...')
    '''
    Break down the parcel trip into it's different trips
    This enables a distinction between networks as well as different types (individual, tour-based, consolidated)
    '''
    cols = ['Parcel_ID', 'O_zone', 'D_zone', 'CEP', 'Network', 'Type']
    parcel_trips = pd.DataFrame(columns=cols) #initiate dataframe with above stated columns
    parcel_trips = parcel_trips.astype({'Parcel_ID': int,'O_zone': int, 'D_zone': int})
    for index, parcel in parcels_hyperconnected.iterrows():
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
            parcel_trips_CS.to_csv(f"{varDict['DATAPATH']}Output/Parcels_CS.csv", index=False) #write those trips to csv (default location of parcel demand for scheduling module)
            
            from LEAD_module_CS import actually_run_module #load right module
            actually_run_module(args) #run module
            parcel_trips_CS = pd.read_csv(f"{varDict['DATAPATH']}Output/Parcels_CS_matched.csv") #load module output to dataframe
            
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
    print("Allocate conventional parcels (MASS-GT Parcel Scheduling module)...")
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
    parcel_trips_HS_delivery.to_csv(f"{varDict['OUTPUTFOLDER']}ParcelDemand_HS_delivery.csv", index=False) #output these parcels to default location for scheduling
    
    
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
    parcel_trips_HS_pickup.to_csv(f"{varDict['OUTPUTFOLDER']}ParcelDemand_HS_pickup.csv", index=False) #output these parcels to default location for scheduling
    
    parcel_trips.to_csv(f"{varDict['OUTPUTFOLDER']}ParcelDemand_ParcelTrips.csv", index=False)

    
    
    #%% OUTPUTS
    
    
    
    """
    
    The outputs are
    
    
    
    """

    return ()














