# Parcel Market

_Parcel Market model for the Living Lab of The Hague for the LEAD platform._

```
python3 Parcel_Market.py Test Input Output Params_ParcelMarket.txt Demand_parcels_fulfilment_test.csv skimTijd_new_REF.mtx skimAfstand_new_REF.mtx Zones_v4.shp SEGS2020.csv parcelNodes_v2.shp trips.csv

/mnt/c/Users/rtapia/OneDrive - Delft University of Technology/Transporte/Proyectos/LEAD project TUDelft/Work Packages/MassGT LEAD/Model Library Vers/Parcel_Market$

c='/mnt/c/Users/rtapia/OneDrive - Delft University of Technology/Transporte/Proyectos/LEAD project TUDelft/Work Packages/MassGT LEAD/Model Library Vers'
cd "$c"
```

## Installation

The `requirements.txt` and `Pipenv` files are provided for the setup of an environment where the module can be installed. The package includes a `setup.py` file and it can be therefore installed with a `pip install .` when we are at the same working directory as the `setup.py` file. For testing purposes, one can also install the package in editable mode `pip install -e .`.

After the install is completed, an executable `parcelmarket` will be available to the user.

## Usage

The executable's help message provides information on the parameters that are needed.

```
$ parcelkmarket -h
usage: parcelmarket [-h] [-v] [--flog] [-e ENV]

parcelmarket

Calculates market [...]
```

Furthermore, the following parameters must be provided as environment variables either from the environment itself or through a dotenv file that is specified with the `--env <path-to-dotenv>` optional command line argument. An example of the `.env` file and some values is presented below.

```
TEST
```
