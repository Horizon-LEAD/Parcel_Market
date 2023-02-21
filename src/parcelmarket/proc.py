""" ParcelMarket processing module
"""

from logging import getLogger
from time import time
from os.path import join
from json import dump, dumps

import numpy as np
import pandas as pd
import networkx as nx

from .cs import cs_matching
from .utils import read_shape, read_mtx, k_shortest_paths, pairwise, calc_score


logger = getLogger("parcelmarket.proc")


def run_model(cfg: dict) -> list:
    """_summary_

    :param cfg: The input configuration dictionary
    :type cfg: dict
    :return: A list containing status codes
    :rtype: list
    """

    start_time = time()
    pd.options.mode.chained_assignment = None # This can be removed, it prints less stuff here
    # if a seed is provided, use it
    if cfg.get('Seed', None):
        np.random.seed(int(cfg['Seed']))

    zones = read_shape(cfg['ZONES'])
    zones.index = zones['AREANR']
    nZones = len(zones)

    skims = {'time': {}, 'dist': {}, }
    skims['time']['path'] = cfg['SKIMTIME']
    skims['dist']['path'] = cfg['SKIMDISTANCE']
    for skim in skims:
        skims[skim] = read_mtx(skims[skim]['path'])
        nSkimZones = int(len(skims[skim])**0.5)
        skims[skim] = skims[skim].reshape((nSkimZones, nSkimZones))
        if skim == 'time':
            skims[skim][6483] = skims[skim][:, 6483] = 5000 # data deficiency
        for i in range(nSkimZones): #add traveltimes to internal zonal trips
            skims[skim][i, i] = 0.7 * np.min(skims[skim][i, skims[skim][i, :] > 0])
    skimTravTime = skims['time']
    skimDist = skims['dist']
    # skimDist_flat = skimDist.flatten()
    # del skims, skim, i

    zoneDict = dict(np.transpose(np.vstack( (np.arange(1, nZones+1), zones['AREANR']) )))
    zoneDict = {int(a): int(b) for a, b in zoneDict.items()}
    invZoneDict = dict((v, k) for k, v in zoneDict.items())

    segs = pd.read_csv(cfg['SEGS'])
    segs.index = segs['zone']
    # Take only segs into account for which zonal data is known as well
    segs = segs[segs['zone'].isin(zones['AREANR'])]

    parcelNodesPath = cfg['PARCELNODES']
    parcelNodes = read_shape(parcelNodesPath, return_geometry=False)
    parcelNodes.index = parcelNodes['id'].astype(int)
    parcelNodes = parcelNodes.sort_index()

    for node in parcelNodes['id']:
        parcelNodes.loc[node,'SKIMNR'] = int(invZoneDict[parcelNodes.at[int(node), 'AREANR']])
    parcelNodes['SKIMNR'] = parcelNodes['SKIMNR'].astype(int)

    cepList = np.unique(parcelNodes['CEP'])
    cepNodes = [np.where(parcelNodes['CEP'] == str(cep))[0] for cep in cepList]

    cepNodeDict, cepZoneDict, cepSkimDict = {}, {}, {}
    for cep in cepList:
        cepZoneDict[cep] = parcelNodes[parcelNodes['CEP']==cep]['AREANR'].astype(int).tolist()
        cepSkimDict[cep] = parcelNodes[parcelNodes['CEP']==cep]['SKIMNR'].astype(int).tolist()
    for cepNo in range(len(cepList)):
        cepNodeDict[cepList[cepNo]] = cepNodes[cepNo]
    
    logger.debug('CEP List     : %s', cepList)
    logger.debug('CEP Zone Dict: %s', cepZoneDict)

    # actually run module
    parcels = pd.read_csv(cfg['DEMANDPARCELS'])
    parcels.index = parcels['Parcel_ID']

    parcels_hubspoke = parcels [parcels['Fulfilment']=='Hubspoke']
    parcels_hubspoke = parcels_hubspoke.drop(
        ['L2L',"CS_eligible",'Fulfilment', 'PL'],
        axis=1
    )

    parcels_hyperconnected = parcels[parcels['Fulfilment']=='Hyperconnected']


    # Module 2: Network creation
    logger.info("creating network")
    G = nx.Graph() #initiate NetworkX graph
    # add all zones to network
    for zoneID in zones['AREANR']:
        G.add_node(zoneID, **{'node_type':'zone'})

    # Conventional carrier networks following hub-spoke structure
    for cep in cepList[:]:
        # connect each zone to closest parcelnode
        for zoneID in zones['AREANR'][:]:
            G.add_node(f"{zoneID}_{cep}", **{'node_type':'node'})
            parcelNode = cepZoneDict[cep][
                skimTravTime[invZoneDict[zoneID]-1, cepSkimDict[cep]].argmin()
            ]
            attrs = {
                'length': skimDist[invZoneDict[zoneID]-1, invZoneDict[parcelNode]-1],
                'travtime': skimTravTime[invZoneDict[zoneID]-1, invZoneDict[parcelNode]-1],
                'network': 'conventional',
                'type': 'tour-based',
                'CEP': cep
            }
            G.add_edge(f"{zoneID}_{cep}", f"{parcelNode}_{cep}", **attrs)
            attrs = {
                'length': 0,
                'travtime': 0,
                'network': 'conventional',
                'type': 'access-egress',
                'CEP': cep
            }
            G.add_edge(zoneID, f"{zoneID}_{cep}", **attrs)

        # connect parcelnodes from one carrier to each other
        for parcelNode in cepZoneDict[cep]:
            nx.set_node_attributes(G, {f"{parcelNode}_{cep}": 'parcelNode'}, 'node_type')
            for other_node in cepZoneDict[cep]:
                if parcelNode == other_node:
                    continue
                attrs = {
                    'length': skimDist[invZoneDict[parcelNode]-1, invZoneDict[other_node]-1],
                    'travtime': skimTravTime[invZoneDict[parcelNode]-1, invZoneDict[other_node]-1],
                    'network': 'conventional',
                    'type': 'consolidated',
                    'CEP': cep
                }
                G.add_edge(f"{parcelNode}_{cep}", f"{other_node}_{cep}", **attrs)

    # Crowdshipping network, fully connected graph
    if cfg['CROWDSHIPPING_NETWORK']:
        Gemeenten = cfg['Gemeenten_CS'] #select municipalities where CS could be done
        for orig in zones['AREANR'][zones['GEMEENTEN'].isin(Gemeenten)]:
            for dest in zones['AREANR'][zones['GEMEENTEN'].isin(Gemeenten)]:
                if orig < dest: #this is an undirected graph; only one direction should be included
                    attrs = {
                        'length': skimDist[invZoneDict[orig]-1,invZoneDict[dest]-1],
                        'travtime': skimTravTime[invZoneDict[orig]-1,invZoneDict[dest]-1],
                        'network': 'crowdshipping',
                        'type': 'individual',
                        'CEP':  'crowdshipping'}
                    if attrs['length'] <  (cfg['CS_MaxParcelDistance']*1000):
                        G.add_edge(f"{orig}_CS", f"{dest}_CS", **attrs)
            nx.set_node_attributes(G, {f"{orig}_CS":'node'}, 'node_type')
            attrs = {
                'length': 0,
                'travtime': 0,
                'network': 'crowdshipping',
                'type': 'access-egress',
                'CEP':  'crowdshipping'
            }
            G.add_edge(orig, f"{orig}_CS", **attrs)

    # Transshipment links
    # Conventional - Crowdshipping
    CS_transshipment_nodes = []
    if cfg['CROWDSHIPPING_NETWORK']:
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

    # Logistical hubs
    for hub_zone in cfg['hub_zones']:
        G.add_node(f"{hub_zone}_hub", **{'node_type':'hub'})
        for cep in cepList:
            closest = cepZoneDict[cep][skimTravTime[
                invZoneDict[hub_zone]-1, [x-1 for x in cepSkimDict[cep]]].argmin()
            ]
            attrs = {
                'length': 0,
                'travtime': 0,
                'network': 'conventional',
                'type': 'hub',
                'CEP': cep
            }
            G.add_edge(f"{hub_zone}_hub", f"{closest}_{cep}", **attrs)
        if cfg['CROWDSHIPPING_NETWORK']:
            for orig in zones['AREANR'][zones['GEMEENTEN'].isin(Gemeenten)]:
                attrs = {
                    'length': skimDist[invZoneDict[hub_zone]-1,invZoneDict[orig]-1],
                    'travtime': skimTravTime[invZoneDict[hub_zone]-1,invZoneDict[orig]-1],
                    'network': 'crowdshipping',
                    'type': 'individual'}
                G.add_edge(f"{hub_zone}_hub", f"{orig}_CS", **attrs)
            CS_transshipment_nodes.append(f"{hub_zone}_hub")
    hub_nodes = [str(s) + '_hub' for s in cfg['hub_zones']]

    # Parcel lockers
    PLFulfilment = cfg['ParcelLockersfulfilment']
    if len(cfg['parcelLockers_zones']) != 0:  #this part runs only if there are available PL
        locker_zones=cfg['parcelLockers_zones']
        for locker in locker_zones:
            locker = int(locker)
            # defining a node for each PL (ex. 566_locker)
            G.add_node(f"{locker}_locker", **{'node_type':'locker'})
            attrs = {'length': 0,'travtime': 0, 'network': 'locker', 'type': 'access-egress',
                     'CEP': "locker"}
            G.add_edge( f"{locker}_locker",locker, **attrs)

            for cep in PLFulfilment:
                # defining closest depot for every CEP. 
                # In this system the only CEP is Cycloon, 
                # for the final delivery to the Parcel Locker
                # closest = cepZoneDict[cep][skimTravTime[invZoneDict[locker]-1, 
                #                                         [x-1 for x in cepSkimDict[cep]]].argmin()]
                try:
                    closest = cepZoneDict[cep][skimTravTime[invZoneDict[locker]-1, 
                                                            cepSkimDict[cep]].argmin()]
                except KeyError as exc:
                    logger.warning(
                        '[KeyError] PLFulfilment CEP not in cepZoneDict: %s', exc
                    )
                    continue

                # nx.set_node_attributes(G, {f"{locker}_{cep}":'parcelLocker'}, 'node_type')
                
                # Travel time is right now car based but for bicycle can change
                attrs = {
                    'length': skimDist[invZoneDict[locker]-1,invZoneDict[closest]-1],
                    'travtime': skimTravTime[invZoneDict[locker]-1,invZoneDict[closest]-1],
                    'network': 'locker',
                    'type': 'tour-based',
                    'CEP': cep}
                G.add_edge(f"{locker}_locker", f"{closest}_{cep}", **attrs)

    # HyperConnect
    HyperConect = cfg['HyperConect']

    if cfg['HYPERCONNECTED_NETWORK']:
        logger.info('Hyperconnected')
        for cep in cepList[:]:
            for parcelNode in cepZoneDict[cep]:
                for other_cep in HyperConect[cep]:
                    # if cep == other_cep: continue
                    if other_cep not in cepNodeDict:
                        continue
                    for other_node in cepZoneDict[other_cep]:
                        attrs = {
                            'length': skimDist[invZoneDict[parcelNode]-1,
                                               invZoneDict[other_node]-1],
                            'travtime': skimTravTime[invZoneDict[parcelNode]-1,
                                                     invZoneDict[other_node]-1],
                            'network': 'conventional',
                            'type': 'consolidated',
                            'CEP': cep
                        }
                        G.add_edge(f"{parcelNode}_{cep}", f"{other_node}_{other_cep}", **attrs)

    # Module 3: Network allocation
    logger.info('Perform network allocation...')
    # ASC, A1, A2, A3 = cfg['SCORE_ALPHAS']
    # tour_based_cost, consolidated_cost, \
    #   hub_cost, cs_trans_cost ,interCEP_cost = cfg['SCORE_COSTS']

    '''
    This part I couldn't make it work with this version, just with the bad practice one.
    The previous version with the globals and the old function.

    '''


    if cfg['CROWDSHIPPING_NETWORK']:
        parcels_hyperconnected_NotCS = parcels_hyperconnected [parcels_hyperconnected['CS_eligible']==False]
    else:
        parcels_hyperconnected_NotCS = parcels_hyperconnected


    parcels_hyperconnected_NotCS['path'] = type('object')


    parcels_hyperconnected['path'] = type('object')
    for index, parcel in parcels_hyperconnected_NotCS.iterrows():
        orig = parcel['O_zone']
        dest = parcel['D_zone']

        k = 1
        allowed_cs_nodes = []
        if parcel['CS_eligible'] == True:
            allowed_cs_nodes = CS_transshipment_nodes + [f'{orig}_CS', f'{dest}_CS']



        shortest_paths = k_shortest_paths(
            G, orig, dest, k,
            weight = lambda u, v, d: calc_score(G, u, v, orig, dest, G[u][v],
                                                allowed_cs_nodes, hub_nodes,
                                                parcel, cfg)
        )
        # print(f"SHORTEST PATHS: {shortest_paths}")

        for path in shortest_paths:
            weightSum = 0
            for pair in pairwise(path):
                weightSum += calc_score(
                    G, pair[0], pair[1], orig, dest,
                    G.get_edge_data(pair[0], pair[1]),
                    allowed_cs_nodes, hub_nodes,
                    parcel,
                    cfg
                )
        parcels_hyperconnected_NotCS.at[index, 'path'] = shortest_paths[0]
        parcels_hyperconnected_NotCS.at[index, 'weightSum'] = weightSum

    # Module 3.5 Parcel trips breakdown
    logger.info('Parcels network breakdown...')
    cols = ['Parcel_ID', 'O_zone', 'D_zone', 'CEP', 'Network', 'Type']
    # initiate dataframe with above stated columns
    parcel_trips = pd.DataFrame(columns=cols)
    parcel_trips = parcel_trips.astype({'Parcel_ID': int,'O_zone': int, 'D_zone': int})
    for index, parcel in parcels_hyperconnected_NotCS.iterrows():
        path = parcel['path']
        # remove the first and last node from path (these are the access/egress links)
        path = path[1:-1]
        for pair in pairwise(path):
            # remove network from node name (only keep zone number)
            orig = int(pair[0].split("_")[0])
            dest = int(pair[1].split("_")[0])
            network = G[pair[0]][pair[1]]['network']
            edge_type = G[pair[0]][pair[1]]['type']
            cep = ''
            if network == 'conventional':
                #CEP only applicable to conventional links
                cep = G[pair[0]][pair[1]]['CEP']
            elif network == 'locker':
                cep = G[pair[0]][pair[1]]['CEP']
            # add trip to dataframe
            parcel_trips = parcel_trips.append(
                pd.DataFrame([[parcel['Parcel_ID'], orig, dest, cep, network, edge_type]],
                             columns=cols),
                ignore_index=True,
            )

    # Module 4.1: Parcel assignment: CROWDSHIPPING
    logger.info("Allocate crowdshipping parcels...")
    if cfg['CROWDSHIPPING_NETWORK']:
        # select only trips using crowdshipping
        parcel_trips_CS = parcels_hyperconnected [parcels_hyperconnected['CS_eligible']==True]
        parcel_trips_CS = parcel_trips_CS.append (parcel_trips[parcel_trips['Network'] == 'crowdshipping'])
        parcel_trips_CS_unmatched_delivery = pd.DataFrame()
        if not parcel_trips_CS.empty:
            # write those trips to csv (default location of parcel demand for scheduling module)
            parcel_trips_CS.to_csv(join(cfg["OUTDIR"], "Parcels_CS.csv"), index=False)

            # load right module
            cs_matching(zones, zoneDict, invZoneDict, cfg)
            # cs_matching(args) #run module
            # load module output to dataframe
            parcel_trips_CS = pd.read_csv(join(cfg["OUTDIR"], "Parcels_CS_matched.csv"))

            # TODO Make sure that this is the style of the output of the CS module
            Trips_CS  = pd.read_csv(join(cfg["OUTDIR"], "TripsCS.csv"))

            # See what happens when there are no unmatched
            # get unmatched parcels
            parcel_trips_CS_unmatched = parcel_trips_CS.drop(
                parcel_trips_CS[parcel_trips_CS['traveller'].notna()].index
            )
            # will be shiped conventionally
            parcel_trips_CS_unmatched.loc[:,'Network'] = 'conventional'
            # will be tour-based
            parcel_trips_CS_unmatched.loc[:,'Type'] = 'tour-based'
            # drop unnessecary columns
            parcel_trips_CS_unmatched = parcel_trips_CS_unmatched.drop(
                ['traveller', 'detour', 'compensation'], axis=1
            )

            #most CS occurs at delivery, some are for pickup. These will be filered out here:
            parcel_trips_CS_unmatched_pickup = \
                pd.DataFrame(columns = parcel_trips_CS_unmatched.columns)
            parcel_trips_CS_unmatched_delivery = \
                pd.DataFrame(columns = parcel_trips_CS_unmatched.columns)
            for index, parcel in parcel_trips_CS_unmatched.iterrows():
                cep = parcels.loc[parcel['Parcel_ID'], 'CEP']
                # it is pickup if the CS destination is not the final destination
                if parcel['D_zone'] != parcels.loc[parcel['Parcel_ID'], 'D_zone']:
                    # add cs parcel to pick-up dataframe
                    parcel_trips_CS_unmatched_pickup = \
                        parcel_trips_CS_unmatched_pickup.append(parcel,sort=False)
                    # add original cep to parcel
                    parcel_trips_CS_unmatched_pickup.loc[index, 'CEP'] = cep
                    # change destination to closest depot
                    minDist=10000000000
                    DZONE = 0
                    for depot in cepZoneDict[cep]:
                        if minDist > skimTravTime[(invZoneDict[parcel['D_zone']]-1),(invZoneDict[depot]-1)]:
                            minDist = skimTravTime[(invZoneDict[parcel['D_zone']]-1),(invZoneDict[depot]-1)]
                            DZONE = depot
                    parcel_trips_CS_unmatched_pickup.loc[index, 'D_zone'] = DZONE
                    ## Alternative method
                    # parcel_trips_CS_unmatched_pickup.loc[index, 'D_zone'] = \
                    #     cepZoneDict[cep][skimTravTime[invZoneDict[parcel['O_zone']]-1,
                    #                                   [x-1 for x in cepSkimDict[cep]]].argmin()
                    #     ]
                else: #for CS delivery parcels
                    # add cs parcel to pick-up dataframe
                    parcel_trips_CS_unmatched_delivery = \
                        parcel_trips_CS_unmatched_delivery.append(parcel,sort=False)
                    # add original cep to parcel
                    parcel_trips_CS_unmatched_delivery.loc[index, 'CEP'] = cep
                    # change origin to closest depot
                    minDist=10000000000
                    OZONE = 0
                    for depot in cepZoneDict[cep]:
                        if minDist > skimTravTime[(invZoneDict[parcel['D_zone']]-1),(invZoneDict[depot]-1)]:
                            minDist = skimTravTime[(invZoneDict[parcel['D_zone']]-1),(invZoneDict[depot]-1)]
                            OZONE = depot
                    parcel_trips_CS_unmatched_delivery.loc[index, 'O_zone'] = OZONE
                    ## Alternative method
                    # parcel_trips_CS_unmatched_delivery.loc[index, 'O_zone'] = \
                    #     cepZoneDict[cep][skimTravTime[invZoneDict[parcel['D_zone']]-1,
                    #                                   [x-1 for x in cepSkimDict[cep]]].argmin()]


    # Module 4.2: Parcel assignment: CONVENTIONAL
    logger.info("Allocate parcel trips to conventional networks")
    error = 0
    parcel_trips_HS_delivery = \
        parcel_trips.drop_duplicates(subset = ["Parcel_ID"], keep='last') #pick the final part of the parcel trip
    # only take parcels which are conventional or locker & tour-based
    parcel_trips_HS_delivery = \
        parcel_trips_HS_delivery[((parcel_trips_HS_delivery['Network'] == 'conventional') |\
                                  (parcel_trips_HS_delivery['Network'] == 'locker')) & \
                                 (parcel_trips_HS_delivery['Type'] == 'tour-based')]
    if cfg['CROWDSHIPPING_NETWORK']:
        # add unmatched CS as well
        parcel_trips_HS_delivery = \
            parcel_trips_HS_delivery.append(parcel_trips_CS_unmatched_delivery,
                                            ignore_index=True, sort=False)

    # add depotnumer column --> Done above
    # loop over parcels
    for index, parcel in parcel_trips_HS_delivery.iterrows():
        try:
            # add depotnumer to each parcel
            parcel_trips_HS_delivery.at[index, 'DepotNumber'] = \
                parcelNodes[((parcelNodes['CEP'] == parcel['CEP']) \
                            & (parcelNodes['AREANR'] == parcel['O_zone']))]['id']
        # FIXME: just KeyError ?  Rodrigo: Don't remember which error is actually
        except Exception:
            # Get first node as an exception
            parcel_trips_HS_delivery.at[index, 'DepotNumber'] = \
                parcelNodes[((parcelNodes['CEP'] == parcel['CEP']))]['id'].iloc[0]
            error +=1
    # output these parcels to default location for scheduling
    parcel_trips_HS_delivery.to_csv(join(cfg["OUTDIR"], "ParcelDemand_HS_delivery.csv"),
                                    index=False)

    # pick the first part of the parcel trip
    parcel_trips_HS_pickup = parcel_trips.drop_duplicates(subset = ["Parcel_ID"], keep='first')
    # only take parcels which are conventional or locker & tour-based

    parcel_trips_HS_pickup = \
        parcel_trips_HS_pickup[((parcel_trips_HS_pickup['Network'] == 'conventional') | \
                                (parcel_trips_HS_pickup['Network'] == 'locker')) & \
                               (parcel_trips_HS_pickup['Type'] == 'tour-based')]
    Gemeenten = cfg['Gemeenten_studyarea']

    if len(Gemeenten) > 1:
        parcel_trips_HS_pickupIter = pd.DataFrame(columns = parcel_trips_HS_pickup.columns)

        for Geemente in Gemeenten:
            # If the cities are NOT connected - that is every geemente is separated from the next
            if type (Geemente) != list:
                # only take parcels picked-up in the study area
                ParcelTemp = parcel_trips_HS_pickup[
                    parcel_trips_HS_pickup['O_zone'].isin(
                        zones['AREANR'][zones['GEMEENTEN']==Geemente]
                    )
                ]
                parcel_trips_HS_pickupIter = parcel_trips_HS_pickupIter.append(ParcelTemp)
            else:
                ParcelTemp = parcel_trips_HS_pickup[
                    parcel_trips_HS_pickup['O_zone'].isin(
                        zones['AREANR'][zones['GEMEENTEN'].isin(Geemente)]
                    )
                ]
                parcel_trips_HS_pickupIter = parcel_trips_HS_pickupIter.append(ParcelTemp)

        parcel_trips_HS_pickup = parcel_trips_HS_pickupIter
    else:
        if type (Gemeenten[0]) == list:
            Geemente = Gemeenten[0]
        else:
            Geemente = Gemeenten
        # only take parcels picked-up in the study area
        parcel_trips_HS_pickup = parcel_trips_HS_pickup[
            parcel_trips_HS_pickup['O_zone'].isin(
                zones['AREANR'][zones['GEMEENTEN'].isin(Geemente)]
            )
        ]

    if cfg['CROWDSHIPPING_NETWORK']:
        # add unmatched CS as well
        parcel_trips_HS_pickup = parcel_trips_HS_pickup.append(parcel_trips_CS_unmatched_pickup,
                                                               ignore_index=True, sort=False)

    # add depotnumer column
    # add depotnumer column --> Done above

    error2 = 0
    # loop over parcels
    for index, parcel in parcel_trips_HS_pickup.iterrows():
        try:
            # add depotnumer to each parcel
            parcel_trips_HS_pickup.at[index, 'DepotNumber'] = parcelNodes[
                ((parcelNodes['CEP'] == parcel['CEP']) \
                    & (parcelNodes['AREANR'] == parcel['D_zone']))
            ]['id']
        # FIXME: just KeyError ?
        except Exception:
            # add depotnumer to each parcel
            parcel_trips_HS_pickup.at[index, 'DepotNumber'] = parcelNodes[
                ((parcelNodes['CEP'] == parcel['CEP']) )
            ]['id'].iloc[0]
            error2 += 1

    # output these parcels to default location for scheduling
    parcel_trips_HS_pickup.to_csv(join(cfg["OUTDIR"], "ParcelDemand_HS_pickup.csv"), index=False)
    parcel_trips.to_csv(join(cfg["OUTDIR"], "ParcelDemand_ParcelTrips.csv"), index=False)

    # KPIs
    kpis = {}
    kpis['Local2Local']  =int( parcels['L2L'].sum())
    kpis['Local2Local_Percentage']  = round(100*parcels['L2L'].sum()/ len(parcels),2)

    for cep in cepList: # initiate vars in dict
        kpis['L2L_' + str(cep)] = 0



    for index,parcel in parcel_trips_HS_pickup.iterrows(): # For some reason the pick up is closer to the actual L2L values (minus CS)
        parcelCEP = parcel['CEP']
        kpis['L2L_' + parcelCEP] += 1


    if cfg['CROWDSHIPPING_NETWORK']:
    #     kpis['crowdshipping_parcels'] = len(parcel_trips_CS)
    #     if kpis['crowdshipping_parcels'] > 0:
    #         kpis['crowdshipping_parcels_matched'] = int(parcel_trips_CS['traveller'].notna().sum())
    #         kpis['crowdshipping_match_percentage'] = round(
    #             (kpis['crowdshipping_parcels_matched'] / kpis['crowdshipping_parcels'])*100,
    #             1
    #         )
    #         kpis['crowdshipping_detour_sum'] = int(parcel_trips_CS['detour'].sum())
    #         kpis['crowdshipping_detour_avg'] = round(parcel_trips_CS['detour'].mean(), 2)
    #         kpis['crowdshipping_compensation'] = round(parcel_trips_CS['compensation'].mean(), 2)
        if  len(parcel_trips_CS) > 0:
            WalkBikekm = 0.00001 # To avoid division by 0
            Carkm   = 0.000001
            CarCompensation =0.0000001
            WalkBikeCompensation =0.00001
            CarCount =0
            WalkBikeCount=0

            for index, parcel in parcel_trips_CS.iterrows():
                if parcel["Mode"] in (['Car','Car as Passenger']):
                    Carkm += parcel["detour"]
                    CarCompensation  += parcel["compensation"]
                    CarCount+=1
                elif parcel["Mode"]in(["Walking or Biking"]):
                    WalkBikekm += parcel["detour"]
                    WalkBikeCompensation   += parcel["compensation"]
                    WalkBikeCount  +=1

            kpis['Crowdshipping'] = {
                'parcels_eligibleforCS' : len(parcel_trips_CS),
                'parcels_ChooseCS':len(parcel_trips_CS[parcel_trips_CS['CS_deliveryChoice']]),
                'parcels_DidntChooseCS':len(parcel_trips_CS)-len(parcel_trips_CS[parcel_trips_CS['CS_deliveryChoice']]),
                'PoolOfTrips':len(Trips_CS),
                'PoolOfTravellers':len(set(Trips_CS['person_id'])),
                'parcels_matched' : int(parcel_trips_CS['trip'].notna().sum()),
                'match_percentage': round((parcel_trips_CS['trip'].notna().sum()/len(parcel_trips_CS[parcel_trips_CS['CS_deliveryChoice']]))*100,1),
                'detour_sum': int(parcel_trips_CS['detour'].sum()),
                'detour_avg': round(parcel_trips_CS['detour'].mean(),2),
                'compensation_avg': round(parcel_trips_CS['compensation'].mean(),2),
                'PlatformComission' : round(parcel_trips_CS[parcel_trips_CS['trip'].notna()]['CS_comission'].sum(),2),
                # 'PlatformComission_avg' : round(parcel_trips_CS['CS_comission'].sum()/(KPIs['Crowdshipping']["parcels_matched"] ),2),
                'car': {
                      'detour':round(Carkm,2),
                      'extraTime':round(Carkm /  cfg['CarSpeed'],2),
                      'Compensation':round(CarCompensation,2),
                      'CompPerHour':round(CarCompensation / (round(Carkm /  cfg['CarSpeed'],2)+0.0001),2 ),
                      'Count':int(CarCount),
                      'Share':round ( 100*CarCount / (CarCount+WalkBikeCount),2),
                      'detour_av':round (Carkm /(CarCount+1),2),
                    },
                'bikeWalk': {
                       'detour':round(WalkBikekm,2),
                       'extraTime':round(WalkBikekm / cfg['WalkBikeSpeed'] ,2),
                       'Compensation':round(WalkBikeCompensation,2),
                       'CompPerHour':round(WalkBikeCompensation / (round(WalkBikekm / cfg['WalkBikeSpeed'] ,2) +0.0001),2),
                       'Count':int(WalkBikeCount),
                       'Share':round(100*WalkBikeCount / (CarCount+WalkBikeCount),2),
                       'tour_av':round(WalkBikekm /(WalkBikeCount+1),2),
                    },

                'crowdshipping_ExtraCO2':round(Carkm * cfg['CarCO2'],2 )
                }

        else:
            kpis['Crowdshipping'] = {
                'parcels' :0
                }





    logger.info("KPIs:\n%s", dumps(kpis, indent = 2))
    with open(join(cfg["OUTDIR"], "kpis.json"), "w", encoding="utf-8") as fp:
        dump(kpis, fp, indent=4)

    # Finalize
    totaltime = round(time() - start_time, 2)
    logger.info("Total runtime: %s seconds", totaltime)