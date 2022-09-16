# -*- coding: utf-8 -*-
"""
Created on Mon Aug 16 11:02:37 2021
@author: beren
"""

from __functions__ import read_mtx, read_shape, get_traveltime, get_distance
import pandas as pd
import numpy as np
from scipy import spatial
import math
import os

def actually_run_module(args):
    # -------------------- Define datapaths -----------------------------------

    root    = args[0]
    varDict = args[1]

    if root != '':
        root.progressBar['value'] = 0

    # Define folders relative to current datapath
    datapath        = varDict['DATAPATH']
    VoT             = varDict['VOT']
    droptime_car    = varDict['PARCELS_DROPTIME_CAR']
    droptime_bike   = varDict['PARCELS_DROPTIME_BIKE']
    droptime_pt     = varDict['PARCELS_DROPTIME_PT']
    CS_willingness  = varDict['CS_WILLINGNESS']
    Pax_Trips      = varDict['Pax_Trips']





    skims = {'time': {}, 'dist': {}, }
    skims['time']['path'] = varDict['SKIMTIME']
    skims['dist']['path'] = varDict['SKIMDISTANCE']
    for skim in skims:
        skims[skim] = read_mtx(skims[skim]['path'])
        nSkimZones = int(len(skims[skim])**0.5)
        skims[skim] = skims[skim].reshape((nSkimZones, nSkimZones))
        if skim == 'time': skims[skim][6483] = skims[skim][:,6483] = 5000 # data deficiency
        for i in range(nSkimZones): #add traveltimes to internal trips
            skims[skim][i,i] = 0.7 * np.min(skims[skim][i,skims[skim][i,:]>0])
        skims[skim] = skims[skim].flatten()
    skimTravTime = skims['time']; skimDist = skims['dist']
    del skims, skim, i
    timeFac = 3600

    skimTime = {}
    skimTime['car'] = skimTravTime
    skimTime['car_passenger'] = skimTravTime
    skimTime['walk'] = (skimDist / 1000 / 5 * 3600).astype(int)
    skimTime['bike'] = (skimDist / 1000 / 12 * 3600).astype(int)
    skimTime['pt'] = skimTravTime * 2 #https://doi.org/10.1038/s41598-020-61077-0, http://dx.doi.org/10.1016/j.jtrangeo.2013.06.011

    zones = read_shape(varDict['ZONES'])
    zones.index = zones['AREANR']
    nZones = len(zones)

    zoneDict  = dict(np.transpose(np.vstack( (np.arange(1,nZones+1), zones['AREANR']) )))
    zoneDict  = {int(a):int(b) for a,b in zoneDict.items()}
    invZoneDict = dict((v, k) for k, v in zoneDict.items())

    #%% Generate bringers supply
    def generate_CS_supply(trips, CS_willingness): # CS_willingness is the willingness to be a bringer
        trips['CS_willing'] = np.random.uniform(0,1,len(trips)) < CS_willingness
        trips['CS_eligible'] = (trips['CS_willing'])

        tripsCS = trips[(trips['CS_eligible'] == True)]
        tripsCS = tripsCS.drop(['CS_willing', 'CS_eligible' ],axis=1)

        #transform the lyon data into The Hague data
        for i, column in enumerate(['origin_x', 'destination_x', 'origin_y', 'destination_y']):
            tripsCS[column] = (tripsCS[column]-min(tripsCS[column])) / (max(tripsCS[column]) - min(tripsCS[column]))
            if i < 2: tripsCS[column] = tripsCS[column] * (max(zones['X'])-min(zones['X'])) + min(zones['X'])
            if i > 1: tripsCS[column] = tripsCS[column] * (max(zones['Y'])-min(zones['Y'])) + min(zones['Y'])

        coordinates = [((zones.loc[zone, 'X'], zones.loc[zone, 'Y'])) for zone in zones.index]
        tree = spatial.KDTree(coordinates)

        tripsCS['O_zone'], tripsCS['D_zone'], tripsCS['travtime'], tripsCS['travdist'], tripsCS['municipality_orig'], tripsCS['municipality_dest'] = np.nan, np.nan, np.nan, np.nan, np.nan, np.nan
        trips_array = np.array(tripsCS)
        for traveller in trips_array:
            mode = traveller[10]
            traveller[15] = int(zoneDict[tree.query([(traveller[2], traveller[3])])[1][0]+1]) #orig
            traveller[16] = int(zoneDict[tree.query([(traveller[4], traveller[5])])[1][0]+1]) #dest
            traveller[17] = get_traveltime(invZoneDict[traveller[15]], invZoneDict[traveller[16]], skimTime[mode], nSkimZones, timeFac)
            traveller[18] = get_distance(invZoneDict[traveller[15]], invZoneDict[traveller[16]], skimDist, nSkimZones)
            traveller[19] = zones.loc[traveller[15], 'GEMEENTEN']
            traveller[20] = zones.loc[traveller[16], 'GEMEENTEN']
        tripsCS = pd.DataFrame(trips_array, columns=tripsCS.columns)
        return tripsCS


    # TO DO Has to change this for the HAGUE trips
    trips = pd.read_csv(Pax_Trips, sep = ';', )
    global tripsCS
    tripsCS = generate_CS_supply(trips, CS_willingness)
    tripsCS['shipping'] = np.nan
    # print('test')

    DirCS_Parcels = f"{varDict['OUTPUTFOLDER']}Parcels_CS_{varDict['LABEL']}.csv"
    parcels = pd.read_csv(DirCS_Parcels)
    parcels["traveller"], parcels["detour"], parcels["compensation"] = '', np.nan, np.nan

    #%% Matching of parcels and travellers
    def get_compensation(dist_parcel_trip): # This could potentially have more vars!
        #compensation = math.log( (dist_parcel_trip) + 2)
        compensation = eval(varDict['CS_COMPENSATION'])
        return compensation

    for index, parcel in parcels.iterrows():
        parc_orig = parcel['O_zone']
        parc_dest = parcel['D_zone']
        parc_orig_muni = zones.loc[parc_orig, 'GEMEENTEN']
        parc_dest_muni = zones.loc[parc_dest, 'GEMEENTEN']
        parc_dist = get_distance(parc_orig, parc_dest, skimDist, nSkimZones)   # skimDist[(parc_orig-1),(parc_dest-1)] / 1000
        compensation = get_compensation(parc_dist)

        Minimizing_dict = {}
        filtered_trips = tripsCS[((parc_dist / tripsCS['travdist'] < 1) &
                                  (tripsCS['shipping'].isnull()) &
                                  ((parc_orig_muni == tripsCS['municipality_orig']) | (parc_orig_muni == tripsCS['municipality_dest']) |
                                   (parc_dest_muni == tripsCS['municipality_orig']) | (parc_dest_muni == tripsCS['municipality_dest'])))]
        for i, traveller in filtered_trips.iterrows():
            VoT = eval (varDict['VOT'])  # In case I will do the VoT function of the traveller sociodems/purpose, etc
            trav_orig = traveller['O_zone']
            trav_dest = traveller['D_zone']
            mode = traveller['mode']
            trip_time = traveller['travtime']
            trip_dist = traveller['travdist']
            if mode in ['car']: CS_pickup_time = droptime_car
            if mode in ['bike', 'car_passenger']: CS_pickup_time = droptime_bike
            if mode in ['walk', 'pt']: CS_pickup_time = droptime_pt

            time_traveller_parcel   = get_traveltime(invZoneDict[trav_orig], invZoneDict[parc_orig], skimTime[mode], nSkimZones, timeFac)
            time_parcel_trip        = get_traveltime(invZoneDict[parc_orig], invZoneDict[parc_dest], skimTime[mode], nSkimZones, timeFac)
            time_customer_end       = get_traveltime(invZoneDict[parc_dest], invZoneDict[trav_dest], skimTime[mode], nSkimZones, timeFac)
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
                if varDict ['CS_BringerScore'] == 'Surplus':    # Is it bad practive to bring the varDict into the code?
                    CS_Min = (-1)* CS_surplus  # The -1 is to minimize the surplus
                elif varDict ['CS_BringerScore'] == 'Min_Detour':
                    CS_Min = round(CS_trip_dist - trip_dist, 5)

                Minimizing_dict[f"{traveller['person_id']}_{traveller['person_trip_id']}"] = CS_Min

        if Minimizing_dict:  # The traveler that has the lowest detour gets the parcel
            traveller = min(Minimizing_dict, key=Minimizing_dict.get)
            parcels.loc[index, 'traveller'] = traveller
            parcels.loc[index, 'detour'] = Minimizing_dict[traveller]
            parcels.loc[index, 'compensation'] = compensation

            person, trip = traveller.split('_')
            person = int(person); trip = int(trip)
            # print(traveller)
            tripsCS.loc[((tripsCS['person_id'] == person) & (tripsCS['person_trip_id'] == trip)), 'shipping'] = parcels.loc[index, 'Parcel_ID'] # Are we saving the trips CS?

    parcels.to_csv(f"{varDict['OUTPUTFOLDER']}Parcels_CS_matched_{varDict['LABEL']}.csv", index=False)

#%% Run module on itself
if __name__ == '__main__':
    cwd = os.getcwd()
    datapath = cwd.replace('Code', '')

    def generate_args():
        varDict = {}
        '''FOR ALL MODULES'''
        varDict['LABEL']                = 'REF'
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

        '''FOR CROWDSHIPPING MATCHING MODULE'''
        varDict['CS_WILLINGNESS']       = 0.2
        varDict['VOT']                  = 9.00
        varDict['PARCELS_DROPTIME_CAR'] = 120
        varDict['PARCELS_DROPTIME_BIKE']= 60 #and car passenger
        varDict['PARCELS_DROPTIME_PT']  = 0 #and walk
        varDict['TRIPSPATH']            = f'{datapath}Drive Lyon/'

        args = ['', varDict]
        return args, varDict

    args, varDict = generate_args()
    actually_run_module(args)