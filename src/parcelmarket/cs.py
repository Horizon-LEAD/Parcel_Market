"""CS module
"""

from logging import getLogger
from os.path import join

import numpy as np
import pandas as pd
from scipy import spatial
from .utils import get_traveltime, get_distance, get_compensation, read_mtx


logger = getLogger("parcelmarket.cs")


def generate_cs_supply(
    trips: pd.DataFrame, CS_willingness,
    zones, zoneDict: dict, invZoneDict: dict,
    nSkimZones, skimTime, skimDist,
    timeFac
) -> pd.DataFrame:
    """_summary_

    :param trips: _description_
    :type trips: _type_
    :param CS_willingness: _description_
    :type CS_willingness: _type_
    :param zones: _description_
    :type zones: _type_
    :param zoneDict: _description_
    :type zoneDict: dict
    :param invZoneDict: _description_
    :type invZoneDict: dict
    :param nSkimZones: _description_
    :type nSkimZones: _type_
    :param skimTime: _description_
    :type skimTime: _type_
    :param skimDist: _description_
    :type skimDist: _type_
    :param timeFac: _description_
    :type timeFac: _type_
    :return: _description_
    :rtype: pd.DataFrame
    """
    trips['CS_willing'] = np.random.uniform(0, 1, len(trips)) < CS_willingness
    trips['CS_eligible'] = (trips['CS_willing'])

    tripsCS = trips[(trips['CS_eligible'] == True)]
    tripsCS = tripsCS.drop(['CS_willing', 'CS_eligible'], axis=1)

    #transform the lyon data into The Hague data
    for i, column in enumerate(['origin_x', 'destination_x', 'origin_y', 'destination_y']):
        tripsCS[column] = (tripsCS[column] - min(tripsCS[column])) / (max(tripsCS[column]) - min(tripsCS[column]))
        if i < 2:
            tripsCS[column] = tripsCS[column] * (max(zones['X'])-min(zones['X'])) + min(zones['X'])
        if i > 1:
            tripsCS[column] = tripsCS[column] * (max(zones['Y'])-min(zones['Y'])) + min(zones['Y'])

    coordinates = [((zones.loc[zone, 'X'], zones.loc[zone, 'Y'])) for zone in zones.index]
    tree = spatial.KDTree(coordinates)

    tripsCS['O_zone'], tripsCS['D_zone'], tripsCS['travtime'], tripsCS['travdist'], tripsCS['municipality_orig'], tripsCS['municipality_dest'] = np.nan, np.nan, np.nan, np.nan, np.nan, np.nan
    trips_array = np.array(tripsCS)
    for traveller in trips_array:
        mode = traveller[10]
        traveller[15] = int(zoneDict[tree.query([(traveller[2], traveller[3])])[1][0]+1]) # orig
        traveller[16] = int(zoneDict[tree.query([(traveller[4], traveller[5])])[1][0]+1]) # dest
        traveller[17] = get_traveltime(invZoneDict[traveller[15]],
                                       invZoneDict[traveller[16]],
                                       skimTime[mode],
                                       nSkimZones,
                                       timeFac)
        traveller[18] = get_distance(invZoneDict[traveller[15]],
                                     invZoneDict[traveller[16]],
                                     skimDist,
                                     nSkimZones)
        traveller[19] = zones.loc[traveller[15], 'GEMEENTEN']
        traveller[20] = zones.loc[traveller[16], 'GEMEENTEN']

    tripsCS = pd.DataFrame(trips_array, columns=tripsCS.columns)

    return tripsCS


def cs_matching(zones, zoneDict, invZoneDict, cfg: dict) -> None:
    """_summary_

    :param skimTravTime: _description_
    :type skimTravTime: _type_
    :param skimDist: _description_
    :type skimDist: _type_
    :param zones: _description_
    :type zones: _type_
    :param zonesDict: _description_
    :type zonesDict: _type_
    """
    timeFac = 3600

    skims = { 'time': {}, 'dist': {} }
    skims['time']['path'] = cfg['SKIMTIME']
    skims['dist']['path'] = cfg['SKIMDISTANCE']
    for skim in skims:
        skims[skim] = read_mtx(skims[skim]['path'])
        nSkimZones = int(len(skims[skim])**0.5)
        skims[skim] = skims[skim].reshape((nSkimZones, nSkimZones))
        if skim == 'time':
            # data deficiency
            skims[skim][6483] = skims[skim][:, 6483] = 5000
        # add traveltimes to internal trips
        for i in range(nSkimZones):
            skims[skim][i, i] = 0.7 * np.min(skims[skim][i, skims[skim][i, :] > 0])
        skims[skim] = skims[skim].flatten()
    skimTravTime = skims['time']
    skimDist = skims['dist']

    skimTime = {}
    skimTime['car'] = skimTravTime
    skimTime['car_passenger'] = skimTravTime
    skimTime['walk'] = (skimDist / 1000 / 5 * 3600).astype(int)
    skimTime['bike'] = (skimDist / 1000 / 12 * 3600).astype(int)
    # https://doi.org/10.1038/s41598-020-61077-0
    # http://dx.doi.org/10.1016/j.jtrangeo.2013.06.011
    skimTime['pt'] = skimTravTime * 2

    trips = pd.read_csv(cfg["TRIPS"], sep = ';')

    tripsCS = generate_cs_supply(trips, cfg["CS_WILLINGNESS"],
                                 zones, zoneDict, invZoneDict,
                                 nSkimZones, skimTime, skimDist,
                                 timeFac)
    tripsCS['shipping'] = np.nan

    # DirCS_Parcels =  f"{varDict['OUTPUTFOLDER']}Parcels_CS_{varDict['LABEL']}.csv"
    DirCS_Parcels = join(cfg["OUTDIR"], "Parcels_CS.csv")
    parcels = pd.read_csv(DirCS_Parcels)
    parcels["traveller"], parcels["detour"], parcels["compensation"] = '', np.nan, np.nan

    for index, parcel in parcels.iterrows():
        parc_orig = parcel['O_zone']
        parc_dest = parcel['D_zone']
        parc_orig_muni = zones.loc[parc_orig, 'GEMEENTEN']
        parc_dest_muni = zones.loc[parc_dest, 'GEMEENTEN']
        # skimDist[(parc_orig-1),(parc_dest-1)] / 1000
        parc_dist = get_distance(parc_orig, parc_dest, skimDist, nSkimZones)
        compensation = get_compensation(parc_dist)

        Minimizing_dict = {}
        filtered_trips = tripsCS[((parc_dist / tripsCS['travdist'] < 1) &
                                  (tripsCS['shipping'].isnull()) &
                                  ((parc_orig_muni == tripsCS['municipality_orig']) | (parc_orig_muni == tripsCS['municipality_dest']) |
                                   (parc_dest_muni == tripsCS['municipality_orig']) | (parc_dest_muni == tripsCS['municipality_dest'])))]
        for i, traveller in filtered_trips.iterrows():
            # FIXME: if to be evaluated -> params in .env and new func to calc
            VoT = cfg['VOT']
            trav_orig = traveller['O_zone']
            trav_dest = traveller['D_zone']
            mode = traveller['mode']
            trip_time = traveller['travtime']
            trip_dist = traveller['travdist']
            if mode in ['car']:
                CS_pickup_time = cfg["PARCELS_DROPTIME_CAR"]
            if mode in ['bike', 'car_passenger']:
                CS_pickup_time = cfg["PARCELS_DROPTIME_BIKE"]
            if mode in ['walk', 'pt']:
                CS_pickup_time = cfg["PARCELS_DROPTIME_PT"]

            time_traveller_parcel = get_traveltime(invZoneDict[trav_orig],
                                                   invZoneDict[parc_orig],
                                                   skimTime[mode],
                                                   nSkimZones,
                                                   timeFac)
            time_parcel_trip = get_traveltime(invZoneDict[parc_orig],
                                              invZoneDict[parc_dest],
                                              skimTime[mode],
                                              nSkimZones,
                                              timeFac)
            time_customer_end = get_traveltime(invZoneDict[parc_dest],
                                               invZoneDict[trav_dest],
                                               skimTime[mode],
                                               nSkimZones,
                                               timeFac)
            CS_trip_time = (time_traveller_parcel + time_parcel_trip + time_customer_end)
            CS_detour_time = CS_trip_time - trip_time

            if ((CS_detour_time + CS_pickup_time * 2)/3600) == 0: CS_detour_time += 1 #prevents /0 eror
            compensation_time =  compensation / ((CS_detour_time + CS_pickup_time * 2)/3600)
            if compensation_time > VoT:
                dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimDist, nSkimZones)
                dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimDist, nSkimZones)
                dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimDist, nSkimZones)
                CS_trip_dist = (dist_traveller_parcel + dist_parcel_trip + dist_customer_end)
                # Is VOT in hours? Is CS_detour time in seconds?
                CS_surplus   = compensation + VoT * CS_detour_time / 3600
                # Is it bad practive to bring the varDict into the code?
                if cfg['CS_BringerScore'] == 'Surplus':
                    # The -1 is to minimize the surplus
                    CS_Min = (-1)* CS_surplus
                elif cfg['CS_BringerScore'] == 'Min_Detour':
                    CS_Min = round(CS_trip_dist - trip_dist, 5)

                Minimizing_dict[f"{traveller['person_id']}_{traveller['person_trip_id']}"] = CS_Min

        # The traveler that has the lowest detour gets the parcel
        if Minimizing_dict:
            traveller = min(Minimizing_dict, key=Minimizing_dict.get)
            parcels.loc[index, 'traveller'] = traveller
            parcels.loc[index, 'detour'] = Minimizing_dict[traveller]
            parcels.loc[index, 'compensation'] = compensation

            person, trip = traveller.split('_')
            person = int(person)
            trip = int(trip)
            # print(traveller)
            # Are we saving the trips CS?
            tripsCS.loc[((tripsCS['person_id'] == person) & \
                        (tripsCS['person_trip_id'] == trip)), 'shipping'] = \
                            parcels.loc[index, 'Parcel_ID']

    parcels.to_csv(join(cfg["OUTDIR"], "Parcels_CS_matched.csv"), index=False)

    return
