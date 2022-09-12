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

### Examples

