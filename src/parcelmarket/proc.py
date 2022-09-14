""" ParcelMarket processing module
"""

from logging import getLogger
from time import time
from os.path import join
from json import dump

import numpy as np
import pandas as pd
import networkx as nx

from .cs import cs_matching
from .utils import read_shape, read_mtx, k_shortest_paths, pairwise, calc_score


logger = getLogger("parcelgen.proc")


def run_model(cfg: dict) -> list:
    """_summary_

    :param cfg: The input configuration dictionary
    :type cfg: dict
    :return: A list containing status codes
    :rtype: list
    """

    start_time = time()

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

    # actually run module
    parcels = pd.read_csv(cfg['DEMANDPARCELS'])
    parcels.index = parcels['Parcel_ID']

    parcels_hubspoke = parcels [parcels['Fulfilment']=='Hubspoke']
    parcels_hubspoke = parcels_hubspoke.drop(
        ['L2L', "CS_eligible", "DepotNumber", "Fulfilment"],
        axis=1
    )

    parcels_hyperconnected = parcels[parcels['Fulfilment']=='Hyperconnected']
    parcels_hyperconnected= parcels_hyperconnected.drop(
        ['D_DepotNumber', 'D_DepotZone', 'Fulfilment', 'O_DepotNumber', 'O_DepotZone'],
        axis=1
    )

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
                        'type': 'individual'}
                    if attrs['length'] < 10000:
                        G.add_edge(f"{orig}_CS", f"{dest}_CS", **attrs)
            nx.set_node_attributes(G, {f"{orig}_CS":'node'}, 'node_type')
            attrs = {
                'length': 0,
                'travtime': 0,
                'network': 'crowdshipping',
                'type': 'access-egress'
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

    # HyperConnect
    HyperConect = cfg['HyperConect']

    if cfg['HYPERCONNECTED_NETWORK']:

        for cep in cepList[:]:
            for parcelNode in cepZoneDict[cep]:
                for other_cep in HyperConect[cep]:
                    # if cep == other_cep: continue
                    for other_node in cepZoneDict[other_cep]:
                        attrs = {
                        'length': skimDist[invZoneDict[parcelNode]-1,
                                           invZoneDict[other_node]-1],
                        'travtime': skimTravTime[invZoneDict[parcelNode]-1,
                                                 invZoneDict[other_node]-1],
                        'network': 'conventional',
                        'type': 'consolidated',
                        'CEP': cep}
                        G.add_edge(f"{parcelNode}_{cep}", f"{other_node}_{other_cep}", **attrs)

        if G.has_edge('3362_UPS', '4604_DPD'):
            print("Hyperconnected")
        else:
            print("Not hyperconnected yet")

    # Module 3: Network allocation
    logger.info('Perform network allocation...')
    ASC, A1, A2, A3 = cfg['SCORE_ALPHAS']
    tour_based_cost, consolidated_cost, hub_cost, cs_trans_cost ,interCEP_cost = cfg['SCORE_COSTS']

    parcels_hyperconnected['path'] = type('object')
    for index, parcel in parcels_hyperconnected.iterrows():
        orig = parcel['O_zone']
        dest = parcel['D_zone']

        k = 1
        allowed_cs_nodes = []
        if parcel['CS_eligible'] == True:
            allowed_cs_nodes = CS_transshipment_nodes + [f'{orig}_CS', f'{dest}_CS']

        globals() ['allowed_cs_nodes'] = allowed_cs_nodes

        # FIXME - TypeError: <lambda>() missing 7 required positional arguments:
        # # 'orig', 'dest', 'd', 'acsn', 'hn', 'p', and 'conf'
        shortest_paths = k_shortest_paths(
            G, orig, dest, k,
            weight = lambda g, u, v, orig, dest, d, acsn, hn, p, conf: calc_score(g, u, v, orig, dest, g[u][v], acsn, hn, p, conf)
        )
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
        parcels_hyperconnected.at[index, 'path'] = shortest_paths[0]
        parcels_hyperconnected.at[index, 'weightSum'] = weightSum

    # Module 3.5 Parcel trips breakdown
    logger.info('Parcels network breakdown...')
    cols = ['Parcel_ID', 'O_zone', 'D_zone', 'CEP', 'Network', 'Type']
    # initiate dataframe with above stated columns
    parcel_trips = pd.DataFrame(columns=cols)
    parcel_trips = parcel_trips.astype({'Parcel_ID': int,'O_zone': int, 'D_zone': int})
    for index, parcel in parcels_hyperconnected.iterrows():
        path = parcels_hyperconnected.at[index,'path']
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
                # CEP only applicable to conventional links
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
        parcel_trips_CS = parcel_trips[parcel_trips['Network'] == 'crowdshipping']
        parcel_trips_CS_unmatched_pickup = pd.DataFrame()
        parcel_trips_CS_unmatched_delivery = pd.DataFrame()
        if not parcel_trips_CS.empty:
            out = f"{cfg['OUTPUTFOLDER']}Parcels_CS_{cfg['LABEL']}.csv"
            # write those trips to csv (default location of parcel demand for scheduling module)
            parcel_trips_CS.to_csv(out, index=False)

            # load right module
            cs_matching(nSkimZones, skimTravTime, skimDist, zones, zoneDict, invZoneDict, cfg)
            # cs_matching(args) #run module
            # load module output to dataframe
            parcel_trips_CS = pd.read_csv(join([cfg["OUTDIR"], "Parcels_CS_matched.csv"]))

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
                    # add cs parce lto pick-up dataframe
                    parcel_trips_CS_unmatched_pickup = \
                        parcel_trips_CS_unmatched_pickup.append(parcel,sort=False)
                    # add original cep to parcel
                    parcel_trips_CS_unmatched_pickup.loc[index, 'CEP'] = cep
                    # change destination to closest depot
                    parcel_trips_CS_unmatched_pickup.loc[index, 'D_zone'] = \
                        cepZoneDict[cep][skimTravTime[invZoneDict[parcel['O_zone']]-1,
                                                      [x-1 for x in cepSkimDict[cep]]].argmin()
                        ]
                else: #for CS delivery parcels
                    # add cs parce lto pick-up dataframe
                    parcel_trips_CS_unmatched_delivery = \
                        parcel_trips_CS_unmatched_delivery.append(parcel,sort=False)
                    # add original cep to parcel
                    parcel_trips_CS_unmatched_delivery.loc[index, 'CEP'] = cep
                    # change origin to closest depot
                    parcel_trips_CS_unmatched_delivery.loc[index, 'O_zone'] = \
                        cepZoneDict[cep][skimTravTime[invZoneDict[parcel['D_zone']]-1,
                                                      [x-1 for x in cepSkimDict[cep]]].argmin()]


    # Module 4.2: Parcel assignment: CONVENTIONAL
    logger.info("Allocate parcel trips to conventional networks")
    error = 0
    parcel_trips_HS_delivery = \
        parcel_trips.drop_duplicates(subset = ["Parcel_ID"], keep='last') #pick the final part of the parcel trip
    # only take parcels which are conventional & tour-based
    parcel_trips_HS_delivery = \
        parcel_trips_HS_delivery[((parcel_trips_HS_delivery['Network'] == 'conventional') \
                                 & (parcel_trips_HS_delivery['Type'] == 'tour-based'))]
    if cfg['CROWDSHIPPING_NETWORK']:
        # add unmatched CS as well
        parcel_trips_HS_delivery = \
            parcel_trips_HS_delivery.append(parcel_trips_CS_unmatched_delivery,
                                            ignore_index=True, sort=False)

    # add depotnumer column
    parcel_trips_HS_delivery.insert(3, 'DepotNumber', np.nan)
    # loop over parcels
    for index, parcel in parcel_trips_HS_delivery.iterrows():
        try:
            # add depotnumer to each parcel
            parcel_trips_HS_delivery.at[index, 'DepotNumber'] = \
                parcelNodes[((parcelNodes['CEP'] == parcel['CEP']) \
                            & (parcelNodes['AREANR'] == parcel['O_zone']))]['id']
        except:
            # Get first node as an exception
            parcel_trips_HS_delivery.at[index, 'DepotNumber'] = \
                parcelNodes[((parcelNodes['CEP'] == parcel['CEP']))]['id'].iloc[0]
            error +=1
    # output these parcels to default location for scheduling
    parcel_trips_HS_delivery.to_csv(join([cfg["OUTDIR"], "ParcelDemand_HS_delivery.csv"]),
                                    index=False)

    # pick the first part of the parcel trip
    parcel_trips_HS_pickup = parcel_trips.drop_duplicates(subset = ["Parcel_ID"], keep='first')
    # only take parcels which are conventional & tour-based
    parcel_trips_HS_pickup = \
        parcel_trips_HS_pickup[((parcel_trips_HS_pickup['Network'] == 'conventional') \
                               & (parcel_trips_HS_pickup['Type'] == 'tour-based'))]

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
    parcel_trips_HS_pickup.insert(3, 'DepotNumber', np.nan)

    error2 = 0
    # loop over parcels
    for index, parcel in parcel_trips_HS_pickup.iterrows():
        try:
            # add depotnumer to each parcel
            parcel_trips_HS_pickup.at[index, 'DepotNumber'] = parcelNodes[
                ((parcelNodes['CEP'] == parcel['CEP']) \
                    & (parcelNodes['AREANR'] == parcel['D_zone']))
            ]['id']
        except:
            # add depotnumer to each parcel
            parcel_trips_HS_pickup.at[index, 'DepotNumber'] = parcelNodes[
                ((parcelNodes['CEP'] == parcel['CEP']) )
            ]['id'].iloc[0]
            error2 += 1

    # output these parcels to default location for scheduling
    parcel_trips_HS_pickup.to_csv(join([cfg["OUTDIR"], "ParcelDemand_HS_pickup.csv"]), index=False)
    parcel_trips.to_csv(join([cfg["OUTDIR"], "ParcelDemand_ParcelTrips.csv"]), index=False)

    # KPIs
    kpis = {}
    if cfg['CROWDSHIPPING_NETWORK']:
        kpis['crowdshipping_parcels'] = len(parcel_trips_CS)
        if kpis['crowdshipping_parcels'] > 0:
            kpis['crowdshipping_parcels_matched'] = int(parcel_trips_CS['traveller'].notna().sum())
            kpis['crowdshipping_match_percentage'] = round(
                (kpis['crowdshipping_parcels_matched'] / kpis['crowdshipping_parcels'])*100,
                1
            )
            kpis['crowdshipping_detour_sum'] = int(parcel_trips_CS['detour'].sum())
            kpis['crowdshipping_detour_avg'] = round(parcel_trips_CS['detour'].mean(), 2)
            kpis['crowdshipping_compensation'] = round(parcel_trips_CS['compensation'].mean(), 2)
    logger.info('KPIs:')
    for key, value in kpis.items():
        print(f'{key:<30s}: {value}')
    dump(kpis, join([cfg["OUTDIR"], "kpis.json"]))

    # Finalize
    totaltime = round(time() - start_time, 2)
    logger.info("Total runtime: %s seconds", totaltime)
