# Parcel Market

_Parcel Market model for the Living Lab of The Hague for the LEAD platform._

## Installation

The `requirements.txt` and `Pipenv` files are provided for the setup of an environment where the module can be installed. The package includes a `setup.py` file and it can be therefore installed with a `pip install .` when we are at the same working directory as the `setup.py` file. For testing purposes, one can also install the package in editable mode `pip install -e .`.

After the install is completed, an executable will be available to the user.

Furthermore, a `Dockerfile` is provided so that the user can package the model. To build the image the following command must be issued from the project's root directory:

```
docker build -t parcel-market:latest .
```

## Usage

The executable's help message provides information on the parameters that are needed.

```
$ parcel-market --help
usage: parcel-market [-h] [-v] [--flog] [-e ENV] DEMANDPARCELS SKIMTIME SKIMDISTANCE ZONES SEGS PARCELNODES TRIPS OUTDIR

Parcel Market

Some additional information

positional arguments:
  DEMANDPARCELS      The path of the parcels demand file (csv)
  SKIMTIME           The path of the time skim matrix (mtx)
  SKIMDISTANCE       The path of the distance skim matrix (mtx)
  ZONES              The path of the area shape file (shp)
  SEGS               The path of the socioeconomics data file (csv)
  PARCELNODES        The path of the parcel nodes file (shp)
  TRIPS              The path of the trips file (csv)
  OUTDIR             The output directory

optional arguments:
  -h, --help         show this help message and exit
  -v, --verbosity    Increase output verbosity (default: 0)
  --flog             Stores logs to file (default: False)
  -e ENV, --env ENV  Defines the path of the environment file (default: None)
```

Furthermore, the following parameters must be provided as environment variables either from the environment itself or through a dotenv file that is specified with the `--env <path-to-dotenv>` optional command line argument. An example of the `.env` file and some values is presented below.

```
# string parameters
CS_BringerScore=Min_Detour  # Min_Detour or Surplus
CS_ALLOCATION=best2best

# boolean parameters
CROWDSHIPPING_NETWORK=True
HYPERCONNECTED_NETWORK=True

# numeric parameters
PARCELS_DROPTIME_CAR=120
PARCELS_DROPTIME_BIKE=60
PARCELS_DROPTIME_PT=0
VOT=9.00
PlatformComission=0.15
CS_Costs=0.0
TradCost=9.2
Car_CostKM=0.19
CarSpeed=30.0
WalkBikeSpeed=12.0
CarCO2=160.0
CS_MaxParcelDistance=10.0

# string list parameters
Gemeenten_studyarea=sGravenhage
# Gemeenten_studyarea=Delft,Midden_Delfland,Rijswijk,sGravenhage,Leidschendam_Voorburg
Gemeenten_CS=sGravenhage,Zoetermeer,Midden_Delfland
ParcelLockersfulfilment=Cycloon

# numeric list parameters
SCORE_ALPHAS=0,0,1,1
SCORE_COSTS=2,0.2,0.2,0,0,999999999990
CS_COMPENSATION=6,0,0,0 # Constant, Linear, Quad, Log (inside+1)
CS_Willingess2Send=0.05,-0.329 # Constant, Cost Coefficient
CS_BaseBringerWillingess =-1.4,0.1  # Constant, uniform error term
hub_zones=
parcelLockers_zones=17,21

# json
HyperConect={"DHL": ["Cycloon"], "DPD": ["Cycloon"], "FedEx": ["Cycloon"],  "GLS": ["Cycloon"], "PostNL": ["Cycloon"],  "UPS": ["Cycloon"], "Cycloon": []}
CS_BringerFilter={"age" : ["<35","35-55"] , "income" : ["low","average","aboveAverage"], "following_purpose" :["Home", "Business", "Leisure", "Other", "Groceries", "Services", "Social", "BringGet", "NonGroc", "Touring"],"Mode" : ["Car","Walking or Biking"]}
CS_BringerUtility={"ASC": 0.1, "Cost": -0.045, "Time": -0.0088}
```

### Examples

In the following examples, it is assumed that the user's terminal is at the project's root directory. Also that all the necessary input files are located in the `sample-data/input` directory and that the `sample-data/output` directory exists.

The user can then execute the model by running the executable.

```
parcel-market -vvv --env .env \
    sample-data/input/Demand_parcels_fulfilment_ParcelLocker_CID_CS.csv \
    sample-data/input/skimTijd_new_REF.mtx \
    sample-data/input/skimAfstand_new_REF.mtx \
    sample-data/input/Zones_v4.zip \
    sample-data/input/SEGS2020.csv \
    sample-data/input/parcelNodes_v2Cycloon.zip \
    sample-data/input/FullTrips_Albatross.csv \
    sample-data/output/
```

If the package installation has been omitted, the model can of course also be run with `python -m src.parcelmarket.__main__ <args>`.

Finally, the model can be executed with `docker run`:

```
docker run --rm \
  -v $PWD/sample-data:/data \
  --env-file .env \
  parcel-market:latest \
  /data/input/Demand_parcels_fulfilment_ParcelLocker_CID_CS.csv \
  /data/input/skimTijd_new_REF.mtx \
  /data/input/skimAfstand_new_REF.mtx \
  /data/input/Zones_v4.zip \
  /data/input/SEGS2020.csv \
  /data/input/parcelNodes_v2Cycloon.zip \
  /data/input/FullTrips_Albatross.csv \
  /data/output/
```
