# Parcel Market

_Parcel Market model for the Living Lab of The Hague for the LEAD platform._

## Installation

The `requirements.txt` and `Pipenv` files are provided for the setup of an environment where the module can be installed. The package includes a `setup.py` file and it can be therefore installed with a `pip install .` when we are at the same working directory as the `setup.py` file. For testing purposes, one can also install the package in editable mode `pip install -e .`.

After the install is completed, an executable `parcel-market` will be available to the user.

Furthermore, a `Dockerfile` is provided so that the user can package the parcel market model. To build the image the following command must be issued from the project's root directory:

```
docker build -t parcel-market:latest .
```

## Usage

The executable's help message provides information on the parameters that are needed.

```
parcel-market --help                                                                                                                (base) 260ms  2022-09-13 11:53:41
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
# Min_Detour or Surplus
LABEL=default
CS_BringerScore=Min_Detour

# boolean parameters
CROWDSHIPPING_NETWORK=True
COMBINE_DELIVERY_PICKUP_TOUR=True
HYPERCONNECTED_NETWORK=FALSE
printKPI=True
# TESTRUN=False

# numeric parameters
CONSOLIDATED_MAXLOAD=500
CS_WILLINGNESS=0.2
PARCELS_DROPTIME_CAR=120
PARCELS_DROPTIME_BIKE=60
PARCELS_DROPTIME_PT=0
VOT=9.00

# string list parameters
Gemeenten_studyarea=sGravenhage
# Gemeenten_studyarea=Delft,Midden_Delfland,Rijswijk,sGravenhage,Leidschendam_Voorburg
Gemeenten_CS=sGravenhage,Zoetermeer,Midden_Delfland
hub_zones=
parcelLockers_zones=

# numeric list parameters
SCORE_ALPHAS=0,0,1,0
SCORE_COSTS=2,0.2,0.2,0,0

# json
HyperConect={"DHL": [] , "DPD": ["FedEx", "GLS",  "UPS"] , "FedEx": ["DPD",  "GLS",  "UPS"] ,  "GLS": ["DPD", "FedEx",  "UPS"] ,"PostNL": [] ,  "UPS": ["DPD", "FedEx", "GLS"] }

# string
# Min_Detour or Surplus
# CS_COMPENSATION=math.log( (dist_parcel_trip) + 2)
```

### Examples

In the following examples, it is assumed that the user's terminal is at the project's root directory. Also that all the necessary input files are located in the `sample-data/inputs` directory and that the `sample-data/outputs` directory exists.

The user can then execute the model by running the executable.

```
parcel-market -vvv --env .env \
    sample-data/input/Demand_parcels_fulfilment_test.csv \
    sample-data/input/skimTijd_new_REF.mtx \
    sample-data/input/skimAfstand_new_REF.mtx \
    sample-data/input/Zones_v4.zip \
    sample-data/input/SEGS2020.csv \
    sample-data/input/parcelNodes_v2.zip \
    sample-data/input/trips.csv \
    sample-data/output/
```

If the package installation has been omitted, the model can of course also be run with `python -m src.parcelmarket.__main__ <args>`.

Finally, the model can be executed with `docker run`:

```
docker run --rm \
  -v $PWD/sample-data/input:/data/input \
  -v $PWD/sample-data/output:/data/output \
  --env-file .env \
  parcel-market:latest \
  /data/input/Demand_parcels_fulfilment_test.csv \
  /data/input/skimTijd_new_REF.mtx \
  /data/input/skimAfstand_new_REF.mtx \
  /data/input/Zones_v4.zip \
  /data/input/SEGS2020.csv \
  /data/input/parcelNodes_v2.zip \
  /data/input/trips.csv \
  /data/output/
```
