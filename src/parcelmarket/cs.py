# -*- coding: utf-8 -*-
"""
Created on Wed Dec  7 08:25:29 2022

@author: rtapia
"""
"""CS module
"""

from logging import getLogger
from os.path import join

import numpy as np
import pandas as pd
from scipy import spatial
from .utils import (get_traveltime, get_distance, get_compensation, read_mtx,
                    get_BaseWillforBring, generate_Utility, get_WillingnessToSend, getMax)


logger = getLogger("parcelmarket.cs")


def generate_cs_supply(
    trips: pd.DataFrame, cfg: dict,
    zones, zoneDict: dict, invZoneDict: dict,
    nSkimZones, skimTime, skimDist,
    timeFac
) -> pd.DataFrame:
    """_summary_

    :param trips: _description_
    :type trips: pd.DataFrame
    :param cfg: _description_
    :type cfg: dict
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

    for filt, filt_values in cfg["CS_BringerFilter"].items():
        try:
            trips = trips.loc[trips[filt].isin(filt_values)]
        except KeyError as exc:
            logger.warning('[KeyError] filter not in trips: %s', exc)
    logger.debug("filtered trips shape: %s", str(trips.shape))

    # Willingness a priori. This is the willingness to be surbscribed in the platform
    trips['CS_willing'] = np.random.uniform(0, 1, len(trips)) < trips['unique_id'].apply(lambda x: get_BaseWillforBring(cfg,x))
    trips['CS_eligible'] = (trips['CS_willing'])

    tripsCS = trips[(trips['CS_eligible'] == True)]
    tripsCS = tripsCS.drop(['CS_willing', 'CS_eligible'], axis=1)

    coordinates = [((zones.loc[zone, 'X'], zones.loc[zone, 'Y'])) for zone in zones.index]
    tree = spatial.KDTree(coordinates)

    tripsCS['O_zone'], tripsCS['D_zone'], tripsCS['travtime'], tripsCS['travdist'], tripsCS['municipality_orig'], tripsCS['municipality_dest'] , tripsCS['BaseUtility']= np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan
    trips_array = np.array(tripsCS)
    for traveller in trips_array:
        mode = traveller[21]
        traveller[22] = int(zoneDict[tree.query([(traveller[17], traveller[18])])[1][0]+1]) #orig
        traveller[23] = int(zoneDict[tree.query([(traveller[19], traveller[20])])[1][0]+1]) #dest
        traveller[25] = get_distance(invZoneDict[traveller[22]], invZoneDict[traveller[23]], skimDist, nSkimZones) # in km!
        if mode == 'Car':
            traveller[24] = get_traveltime(invZoneDict[traveller[22]], invZoneDict[traveller[23]], skimTime['car'], nSkimZones, timeFac) # in hours
            traveller[24] = traveller[24] * 60 # in minutes now!

            cost          = traveller[25] * (cfg ['Car_CostKM'])
            traveller[28] = generate_Utility (cfg["CS_BringerUtility"],{'Cost': cost,'Time':traveller[24]})

        elif mode == 'Car as Passenger':
            traveller[24] = get_traveltime(invZoneDict[traveller[22]], invZoneDict[traveller[23]], skimTime['car_passenger'], nSkimZones, timeFac) # in hours
            traveller[24] = traveller[24] * 60 # in minutes now!
            cost   = traveller[25] * (cfg ['Car_CostKM'])
            traveller[28] = generate_Utility (cfg,{'Cost': cost,'Time':traveller[24]})

        elif mode == 'Walking or Biking':
            traveller[24] = 60 * traveller[25] / cfg['WalkBikeSpeed']  # CHANGE FOR CORRECT BIKE SPEED (AND CORRECT UNITS)
            cost = 0
            traveller[28] = generate_Utility (cfg["CS_BringerUtility"],{'Cost': cost,'Time':traveller[24]})
        elif mode == 'walk':
            traveller[24] =  60 *traveller[25] / 1  # CHANGE FOR CORRECT walk SPEED (AND CORRECT UNITS)
            cost  = 0
            traveller[28] = generate_Utility (cfg["CS_BringerUtility"],{'Cost': cost,'Time':traveller[24]})

        else:
            traveller[19] = np.nan
        traveller[26] = zones.loc[traveller[22], 'GEMEENTEN']
        traveller[27] = zones.loc[traveller[23], 'GEMEENTEN']

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
    timeFac = 1

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
    if len(trips.columns) == 1:
        trips = pd.read_csv(cfg["TRIPS"], sep = ',')

    tripsCS = generate_cs_supply(trips, cfg,
                                 zones, zoneDict, invZoneDict,
                                 nSkimZones, skimTime, skimDist,
                                 timeFac)
    tripsCS['shipping'] = np.nan

    # DirCS_Parcels =  f"{varDict['OUTPUTFOLDER']}Parcels_CS_{varDict['LABEL']}.csv"
    DirCS_Parcels = join(cfg["OUTDIR"], "Parcels_CS.csv")
    parcels = pd.read_csv(DirCS_Parcels)
    parcels["traveller"],parcels["trip"], parcels["detour"], parcels["compensation"] = '', np.nan, np.nan,0

    parcels['parceldistance'] = parcels.apply(lambda x: get_distance(x.O_zone,x.D_zone, skimDist, nSkimZones), axis=1)
    parcels['compensation'] = parcels.apply(lambda x: get_compensation(x.parceldistance,cfg), axis=1)
    parcels['cost'] = parcels['compensation'] * (1+ cfg['PlatformComission']+ cfg['CS_Costs'])
    parcels['CS_comission'] = parcels['cost'] *  cfg['PlatformComission']
    parcels['CS_deliveryChoice'] = parcels.apply(lambda x: get_WillingnessToSend(cfg, x.cost,cfg['TradCost']), axis=1)
    parcels['CS_deliveryChoice'] = parcels['CS_deliveryChoice'] > 0   # I already simulated the gumbell distribution, so the utility is the actual choice!!!!!!!
    droptime_car = cfg['PARCELS_DROPTIME_CAR']
    droptime_pt = cfg['PARCELS_DROPTIME_PT']
    droptime_bike = cfg['PARCELS_DROPTIME_BIKE']

    logger.debug('Parcels to be matched: %s', len(parcels))


    if cfg['CS_ALLOCATION'] == 'MinimumDistance':  # This is the old approach

        for index, parcel in parcels.iterrows():
            parc_orig = parcel['O_zone']
            parc_dest = parcel['D_zone']
            parc_orig_muni = zones.loc[parc_orig, 'GEMEENTEN']
            parc_dest_muni = zones.loc[parc_dest, 'GEMEENTEN']
            parc_dist = get_distance(parc_orig, parc_dest, skimDist, nSkimZones)   # skimDist[(parc_orig-1),(parc_dest-1)] / 1000
            # compensation = get_compensation(parc_dist)
            # parcel['compensation'] = compensation
            compensation = parcel['compensation']
            Minimizing_dict = {}
            filtered_trips = tripsCS[((parc_dist / tripsCS['travdist'] < 1) &
                                      (tripsCS['shipping'].isnull()) &
                                      ((parc_orig_muni == tripsCS['municipality_orig']) | (parc_orig_muni == tripsCS['municipality_dest']) |
                                       (parc_dest_muni == tripsCS['municipality_orig']) | (parc_dest_muni == tripsCS['municipality_dest'])))]
            for i, traveller in filtered_trips.iterrows():
                VoT =  (cfg['VOT'])  # In case I will do the VoT function of the traveller sociodems/purpose, etc
                trav_orig = traveller['O_zone']
                trav_dest = traveller['D_zone']
                mode = traveller['Mode']
                trip_time = traveller['travtime']
                trip_dist = traveller['travdist']
                if mode in ['car','Car']:
                    CS_pickup_time = droptime_car
                    mode = 'car'
                    CS_pickup_time = droptime_car
                    time_traveller_parcel   = get_traveltime(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime['car'], nSkimZones, timeFac) # These are car/can TTs!!
                    time_parcel_trip        = get_traveltime(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime['car'], nSkimZones, timeFac) # These are car/can TTs!!
                    time_customer_end       = get_traveltime(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime['car'], nSkimZones, timeFac) # These are car/can TTs!!
                    time_traveller_parcelT   = 60 * time_traveller_parcel # Result in minutes (if timefact = 1)
                    time_parcel_tripT        = 60 * time_parcel_trip   # Result in minutes (if timefact = 1)
                    time_customer_endT      = 60 * time_customer_end # Result in minutes (if timefact = 1)


                    # dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime[mode], nSkimZones) # These are car/can TTs!!
                    # dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime[mode], nSkimZones) # These are car/can TTs!!
                    # dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime[mode], nSkimZones) # These are car/can TTs!!
                    dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimDist, nSkimZones) # These are car/can TTs!!
                    dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimDist, nSkimZones) # These are car/can TTs!!
                    dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimDist, nSkimZones) # These are car/can TTs!!
                    time_traveller_parcel   = 60 * dist_traveller_parcel  /  cfg['CarSpeed']
                    time_parcel_trip        = 60 * dist_parcel_trip       /  cfg['CarSpeed'] # Result in minutes (if timefact = 1)
                    time_customer_end       = 60 * dist_customer_end     /   cfg['CarSpeed'] # Result in minutes (if timefact = 1)

                    time_traveller_parcel = max(time_traveller_parcelT,time_traveller_parcel)
                    time_parcel_trip= max(time_parcel_tripT,time_parcel_trip)
                    time_customer_end= max(time_customer_endT,time_customer_end)
                if mode in ['bike', 'car_passenger','Walking or Biking']:
                    CS_pickup_time = droptime_bike
                    dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimDist, nSkimZones) # These are car/can TTs!!
                    dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimDist, nSkimZones) # These are car/can TTs!!
                    dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimDist, nSkimZones) # These are car/can TTs!!
                    time_traveller_parcel   = 60 * dist_traveller_parcel  /  cfg['WalkBikeSpeed']  # Result in minutes (if timefact = 1)
                    time_parcel_trip        = 60 * dist_parcel_trip       /  cfg['WalkBikeSpeed'] # Result in minutes (if timefact = 1)
                    time_customer_end       = 60 * dist_customer_end     /   cfg['WalkBikeSpeed'] # Result in minutes (if timefact = 1)
                if mode in ['walk', 'pt']:
                    CS_pickup_time = droptime_pt

                # time_traveller_parcel   = get_traveltime(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime[mode], nSkimZones, timeFac)
                # time_parcel_trip        = get_traveltime(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime[mode], nSkimZones, timeFac)
                # time_customer_end       = get_traveltime(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime[mode], nSkimZones, timeFac)
                CS_trip_time = (time_traveller_parcel + time_parcel_trip + time_customer_end)
                CS_detour_time = CS_trip_time - trip_time

                if ((CS_detour_time + CS_pickup_time * 2)/3600) == 0: CS_detour_time += 1 #prevents /0 eror
                compensation_time =  compensation / ((CS_detour_time + CS_pickup_time * 2)/3600)
                if compensation_time > VoT:
                    dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimDist, nSkimZones)
                    dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimDist, nSkimZones)
                    dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimDist, nSkimZones)
                    CS_trip_dist = (dist_traveller_parcel + dist_parcel_trip + dist_customer_end)
                    CS_surplus   = compensation + VoT * CS_detour_time/3600 # Is VOT in hours? Is CS_detour time in seconds?
                    if cfg ['CS_BringerScore'] == 'Surplus':    # Is it bad practive to bring the varDict into the code?
                        CS_Min = (-1)* CS_surplus  # The -1 is to minimize the surplus
                    elif cfg ['CS_BringerScore'] == 'Min_Detour':
                        CS_Min = round(CS_trip_dist - trip_dist, 5)
                    elif cfg ['CS_BringerScore'] == 'Min_Time':
                        CS_Min = round(((CS_detour_time + CS_pickup_time * 2)/3600) - trip_time, 5)
                    Minimizing_dict[f"{traveller['person_id']}_{traveller['person_trip_id']}"] = CS_Min

            if Minimizing_dict:  # The traveler that has the lowest detour gets the parcel
                traveller = min(Minimizing_dict, key=Minimizing_dict.get)
                parcels.loc[index, 'traveller'] = traveller
                parcels.loc[index, 'detour'] = Minimizing_dict[traveller]
                parcels.loc[index, 'compensation'] = compensation
                parcels.loc[index, 'Mode'] = filtered_trips.loc[filtered_trips["unique_id"]==traveller,'Mode'].iloc[0]
                parcels.loc[index, 'unique_id'] = traveller


    elif cfg['CS_ALLOCATION'] == 'best2best':
        Surpluses = np.zeros((len(tripsCS),len(parcels)))
        Detours   = np.zeros((len(tripsCS),len(parcels)))
        # Detours   = np.zeros((len(tripsCS),len(parcels)))

        # comp = []
        logger.info("Starting Utility evaluation")
        for index, parcel in parcels.iterrows():
            parc_orig = parcel['O_zone']
            parc_dest = parcel['D_zone']
            parc_orig_muni = zones.loc[parc_orig, 'GEMEENTEN']
            parc_dest_muni = zones.loc[parc_dest, 'GEMEENTEN']
            parc_dist = get_distance(parc_orig, parc_dest, skimDist, nSkimZones)   # skimDist[(parc_orig-1),(parc_dest-1)] / 1000
            # compensation = get_compensation(parc_dist)
            # comp.append(compensation)
            # parcels.iloc[index]['compensation'] = compensation

            compensation = parcel['compensation']
            # This is a preventive filter to have less suitable trips. Nimber does this by doing a "fat line" of routes.
            filtered_trips = tripsCS[((parc_dist / tripsCS['travdist'] < 1) & # Parcel dist has to be lower than the actual trip, why?? TODO
                                      (tripsCS['shipping'].isnull()) &
                                      ((parc_orig_muni == tripsCS['municipality_orig']) | (parc_orig_muni == tripsCS['municipality_dest']) |
                                        (parc_dest_muni == tripsCS['municipality_orig']) | (parc_dest_muni == tripsCS['municipality_dest'])))]

            if parcel['CS_deliveryChoice']:

                for i, traveller in filtered_trips.iterrows():
                    # print(traveller['PossibleParcels'] )
                    # VoT = eval (varDict['VOT'])  # In case I will do the VoT function of the traveller sociodems/purpose, etc
                    trav_orig = traveller['O_zone']
                    trav_dest = traveller['D_zone']
                    mode = traveller['Mode']
                    trip_time = traveller['travtime']
                    trip_dist = traveller['travdist']
                    if mode in ['Car']:
                        CS_pickup_time = droptime_car
                        time_traveller_parcel   = get_traveltime(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime['car'], nSkimZones, timeFac) # These are car/can TTs!!
                        time_parcel_trip        = get_traveltime(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime['car'], nSkimZones, timeFac) # These are car/can TTs!!
                        time_customer_end       = get_traveltime(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime['car'], nSkimZones, timeFac) # These are car/can TTs!!
                        # if timeFac == 1:
                        time_traveller_parcelT   = 60 * time_traveller_parcel # Result in minutes (if timefact = 1)
                        time_parcel_tripT        = 60 * time_parcel_trip   # Result in minutes (if timefact = 1)
                        time_customer_endT       = 60 * time_customer_end # Result in minutes (if timefact = 1)


                        dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimDist, nSkimZones) # These are car/can TTs!!
                        dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimDist, nSkimZones) # These are car/can TTs!!
                        dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimDist, nSkimZones) # These are car/can TTs!!
                        time_traveller_parcel   = 60 * dist_traveller_parcel  /  cfg['CarSpeed']
                        time_parcel_trip        = 60 * dist_parcel_trip       /  cfg['CarSpeed'] # Result in minutes (if timefact = 1)
                        time_customer_end       = 60 * dist_customer_end     /   cfg['CarSpeed']
                        time_traveller_parcel = max(time_traveller_parcelT,time_traveller_parcel)
                        time_parcel_trip= max(time_parcel_tripT,time_parcel_trip)
                        time_customer_end= max(time_customer_endT,time_customer_end)
                        CS_TravelCost           = (cfg ['Car_CostKM'])
                    if mode in ['Walking or Biking', 'Car as Passenger']: CS_pickup_time = droptime_bike
                    if mode in ['Walking or Biking']:
                        # dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime[mode], nSkimZones) # These are car/can TTs!!
                        # dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime[mode], nSkimZones) # These are car/can TTs!!
                        # dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime[mode], nSkimZones) # These are car/can TTs!!
                        dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimDist, nSkimZones) # These are car/can TTs!!
                        dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimDist, nSkimZones) # These are car/can TTs!!
                        dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimDist, nSkimZones) # These are car/can TTs!!
                        time_traveller_parcel   = 60 * dist_traveller_parcel  /  cfg['WalkBikeSpeed']  # Result in minutes (if timefact = 1)
                        time_parcel_trip        = 60 * dist_parcel_trip       /  cfg['WalkBikeSpeed'] # Result in minutes (if timefact = 1)
                        time_customer_end       = 60 * dist_customer_end     / cfg['WalkBikeSpeed'] # Result in minutes (if timefact = 1)

                        # Change this to make sure I don't have negative time detours! (sometimes it happens that they have less travel distances)

                        time_traveller_parcelT  = 60* get_traveltime(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime['car'], nSkimZones, timeFac) * cfg['CarSpeed']/cfg['WalkBikeSpeed']
                        time_parcel_tripT       = 60*get_traveltime(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime['car'], nSkimZones, timeFac) * cfg['CarSpeed']/cfg['WalkBikeSpeed']
                        time_customer_endT      = 60*get_traveltime(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime['car'], nSkimZones, timeFac)* cfg['CarSpeed']/cfg['WalkBikeSpeed']
                        time_traveller_parcel = max(time_traveller_parcelT,time_traveller_parcel)
                        time_parcel_trip= max(time_parcel_tripT,time_parcel_trip)
                        time_customer_end= max(time_customer_endT,time_customer_end)

                        CS_TravelCost           = 0
                    if mode in ['walk', 'pt']: CS_pickup_time = droptime_pt
                    if mode in ['walk']:
                        # dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime[mode], nSkimZones) # These are car/can TTs!!
                        # dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime[mode], nSkimZones) # These are car/can TTs!!
                        # dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime[mode], nSkimZones) # These are car/can TTs!!
                        dist_traveller_parcel   = get_distance(invZoneDict[trav_orig], invZoneDict[parc_orig], skimDist, nSkimZones) # These are car/can TTs!!
                        dist_parcel_trip        = get_distance(invZoneDict[parc_orig], invZoneDict[parc_dest], skimDist, nSkimZones) # These are car/can TTs!!
                        dist_customer_end       = get_distance(invZoneDict[parc_dest], invZoneDict[trav_dest], skimDist, nSkimZones) # These are car/can TTs!!
                        time_traveller_parcel   =  60 *dist_traveller_parcel  / 1  # CHANGE FOR CORRECT walk SPEED (AND CORRECT UNITS)
                        time_parcel_trip        =  60 *dist_parcel_trip       / 1  # CHANGE FOR CORRECT walk SPEED (AND CORRECT UNITS)
                        time_customer_end       =  60 *dist_customer_end     / 1  # CHANGE FOR CORRECT walk SPEED (AND CORRECT UNITS)
                        CS_TravelCost           = 0



                    CS_trip_dist = (dist_traveller_parcel + dist_parcel_trip + dist_customer_end)
                    CS_trip_time = (time_traveller_parcel + time_parcel_trip + time_customer_end)
                    CS_detour_time = CS_trip_time + 2 * CS_pickup_time - trip_time
                    CS_detour_dist = CS_trip_dist - trip_dist

                    NetCompensation = compensation - CS_detour_dist * CS_TravelCost # Is this better approx? Do people compare just the compensation with the time or the pocket compensation??

                    if ((CS_detour_time + CS_pickup_time * 2)) == 0: CS_detour_time += 1 #prevents /0 eror
                    compensation_time =  NetCompensation / ((CS_detour_time + CS_pickup_time * 2)/3600)

                    Util_PickUp = generate_Utility (cfg["CS_BringerUtility"],{'Cost': CS_TravelCost*CS_trip_dist-compensation,'Time':CS_trip_time}) #+80# This is a provisional number so there aren't that many parcels that are eligible until we find the correct equation
                    TravUtil = generate_Utility (cfg["CS_BringerUtility"],{'Cost': (CS_TravelCost*traveller['travdist']),'Time':traveller['travtime']})
                    Surplus   = Util_PickUp-TravUtil
                    Detour    = CS_trip_dist - traveller['travdist']

                    #TO make sure no neg distances or times:
                    if traveller['travtime'] >=   CS_trip_time    :  # Disqualify people that save time
                        Surplus = 0
                    if Detour<0:  # Disqualify people that save distance
                        Surplus = 0
                    if Surplus>0:

                        Surpluses[i,index] = Surplus
                        Detours  [i,index] = Detour

            # print("parcel ", index, " from ", len(parcels))

        lableTrav = tripsCS[['unique_id']].reset_index(drop=True)
        lableParcels = parcels[['Parcel_ID']].reset_index(drop=True)

        Surplus = Surpluses

        value = 1
        matches ={}
        distances = {}
        # if cfg['CS_UtilDiscount'] == 'SecondBest':
        #     discountParam = 'SecondBestDiscount'
        # elif  cfg['CS_UtilDiscount'] == 'none':
        #     discountParam = 'none'
        matrix = Surplus
        rows = lableTrav
        cols = lableParcels
        logger.info("Starting matching")
        # print('get max')
        logger.debug('Surpluses[%s]: %s', str(Surpluses.shape), Surpluses)
        while value != 0:
            position,value,Surplus,Detours,detour,lableParcels,lableTrav = getMax(
                Surplus, lableParcels, lableTrav, Detours, remove = 1
            )
            if value !=0:
                matches.update(position)
                distances.update(detour)
            # print(position)
            # print(value)
        matches_trips = matches
        matches_parcels =  {v: k for k, v in matches.items()}



        parcels['trip'] = parcels['Parcel_ID'].map(matches_parcels)
        parcels['detour'] = parcels['trip'].map(distances)
        # parcels['compensation'] = comp

        tripsMode = trips[["unique_id","Mode"]]
        #Get the mode and add it to the parcel



        parcels['trip'] =parcels['trip'].astype(str)
        tripsMode['unique_id'] = tripsMode['unique_id'].astype(str)

        parcels =  pd.merge(parcels,tripsMode,left_on='trip', right_on='unique_id')

        parcels[parcels ['CS_deliveryChoice']==False] ['trip'] = 'NaN'

        UnmatchedParcels = parcels.drop(parcels[parcels['trip'].notna()].index)
        MatchedParcels  =parcels.drop(parcels[parcels['trip'].isna()].index)


        parcels['traveller'] = parcels['trip'].apply(lambda x: x[0:-2])

        MatchedParcels['traveller'] = MatchedParcels['trip'].apply(lambda x: x[0:-2])
        UnmatchedParcels['traveller'] = UnmatchedParcels['trip']


        parcels = MatchedParcels.append(UnmatchedParcels)

        #### THE CROWDSHIPPING TRIP DATAFRAME HAS NOT BEEN UPDATED WITH THE NEW TRIPS!!!!!!

        # person, trip = traveller.split('_')
        # person = int(person); trip = int(trip)
        # # print(traveller)
        # tripsCS.loc[((tripsCS['person_id'] == person) & (tripsCS['person_trip_id'] == trip)), 'shipping'] = parcels.loc[index, 'Parcel_ID'] # Are we saving the trips CS?

    parcels.to_csv(join(cfg["OUTDIR"], "Parcels_CS_matched.csv"), index=False)
    tripsCS.to_csv(join(cfg["OUTDIR"],  "TripsCS.csv"), index=False)

    return None
