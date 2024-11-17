
# TRI4PLADS (FOCAPD SI)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://github.com/jodhernandezbe/tri4plads/actions/workflows/publish.yml/badge.svg)](https://github.com/jodhernandezbe/tri4plads/actions/workflows/publish.yml)
[![DOI](https://zenodo.org/badge/879061880.svg)](https://doi.org/10.5281/zenodo.14031589)

![Project Logo](https://github.com/jodhernandezbe/tri4plads/blob/master/assets/logo.png)

## Overview

This repository contains the code to generate discrete distribution based on TRI data, as part of the FOCAPD 2024 Special Issue invitation.

## Project tree

```
.
├── ancillary
│   ├── cd_is_to_naics.csv
│   ├── tri_file_1a_columns.txt
│   ├── tri_file_1b_columns.txt
│   ├── tri_file_3a_columns.txt
│   └── tri_file_3c_columns.txt
├── conf
│   └── main.yaml
├── tests
├── data
│   ├── processed
│   │   └── tri_eol_additives.sqlite
│   └── raw
│       ├── US_1a_2022.txt
│       ├── US_1b_2022.txt
│       ├── US_3a_2022.txt
│       └── US_3c_2022.txt
└──  src
    ├── __init__.py
    ├── data_processing
    │   ├── __init__.py
    │   ├── create_sqlite_db.py
    │   ├── data_models.py
    │   ├── frs_api_queries.py
    │   ├── base.py
    │   ├── main.py
    │   ├── naics_api_queries.py
    │   └── cdr
    │   │   ├── __init__.py
    │   │   ├── cleaner.py
    │   │   ├── load.py
    │   │   └── orchestator.py
    │   └── tri
    │       ├── __init__.py
    │       ├── load
    │       │   ├── __init__.py
    │       │   └── load.py
    │       ├── orchestator.py
    │       ├── transform
    │       │   ├── __init__.py
    │       │   ├── base.py
    │       │   ├── file_1a.py
    │       │   ├── file_1b.py
    │       │   ├── file_3a.py
    │       │   └── file_3c.py
    │       └── utils.py
    └── generate_analysis
        ├── __init__.py
        ├── main.py
        ├── db_queries.py
        └── interactive_cli.py
```

## Entity relational diagram (ERD)

![Project Logo](https://github.com/jodhernandezbe/tri4plads/blob/master/data/processed/erd_tri_eol_additives.png)

## Requirements

1. Python >=3.12, <3.13
2. Poetry

## Poetry

### New Dependencies

When adding or updating dependencies, run `poetry add` or `poetry update` and commit the changes.

### pull

When pulling the latest changes, run the following command to ensure that your local environment matches the project's dependencies.

```
poetry install
```

### Run Commands

To execute commands inside the project's environment, use `run` as follows:

```
poetry run python src/main.py
```

Additionally, you can activate the virtual environment by running the following command:

```
poetry shell
```

## Pre-commit

### Changes

If there is any change in `.pre-commit-config.yaml`, the following command has to be run:

```
poetry run pre-commit autoupdate
```

### Pull

Each time you pull changes, run the following command to ensure your local environment is up-to-date:

```
poetry run pre-commit install
```

### Manually Run Hooks

To manually run all pre-commit hooks on all files in the repository, use the following command:

```
poetry run pre-commit run --all-files
```

Note: this is not required when you commit changes.

If you are running the above command or committing your changes, and one or more hooks like black or isort fail, stage their modifications to the git staging area by running `git add`. After that, you can run `commit` again.

## Installing pyright language server for IDE typecheck highlighting

Detailed instructions: [pyright](https://microsoft.github.io/pyright/#/installation)

[Pycharm](https://github.com/InSyncWithFoo/pyright-langserver-for-pycharm)

VSCode: search for `Pylance` on marketplace

Add path to executable to plugin:

```shell
which pyright-langserver
```

Insert that path to plugin config in your IDE as path to executable

## Documentation Style

The project follows the Google style to document the code. The pre-commit hooks are configured to check this style.

## Data Source and Processing

### Census Bureau Data:

Get your API key in: [link](https://api.census.gov/data/key_signup.html)

Once you get your API key, include a ```.env``` file in the project root with the following:

```
CENSUS_DATA_API_KEY=<YOUR-CENSUS-DATA-API-KEY>
```

Replace ```<YOUR-CENSUS-DATA-API-KEY>``` with your actual API key.

For more information regarding the API data: [link](https://www.census.gov/data/developers/guidance/api-user-guide.Example_API_Queries.html)


### U.S. EPA's Envirofacts

API documentation: [link](https://www.epa.gov/enviro/envirofacts-data-service-api-v1)

### Running the Data Processing Pipeline

This repository includes a data processing pipeline for handling TRI (Toxics Release Inventory) data, specifically focusing on plastic additives. The pipeline can be executed by specifying the year of data you want to process.

### Running the Script

To run the data processing pipeline, navigate to the repository's main directory and execute the following command, replacing ```<year>``` with the desired year (e.g., 2022) and  ```<bool>``` with True/False:

```
python src/data_processing/main.py --year <year> --is_drop_nan_percentage <bool>
```

See the help menu:

```
python src/data_processing/main.py --help
```

### Changes to the database

If you generate changes to the database schema, create migrations by running:

```
alembic revision --autogenerate -m "<description-string>"
```

Then apply the migrations by running:

```
alembic upgrade head
```

## Data Use

### Installation

If you only want to use the data and take advantage of the existing code, you can install the ```tri4plads```:

```
pip install tri4plads
```

Ensure you have Python >=3.12, <3.13.

### Example

## TODO

### TRI data retrieval

The TRI data is static and not dynamic. Due to file size and scalability feel free to automatize this process.
Suggestions:

1. Implement TRI data retrieval from EPA's Envirofacts API.
2. Implement the web scrapping strategy like in [EoL4Chem](https://github.com/jodhernandezbe/EoL4Chem) repository.

Feel free to modularize more the project tree for scalability and mantainability.

### SQL database engine

If you will modify the db engine (e.g., PostgreSQL) or name, feel free to include this information in the config file instead of hard coding it since it would be less error prone.

Feel free to use asyncronous queries to reduce the processing time.

### Testing

Feel free to use unit or integration testing for QA. As suggestion, include it as a hook in the pre-commit file. Only smoke testing was used in the development of this project and there is not coverage yet.

### Data orchestator

Feel free to use a data orchestator like Airflow or Prefect. This would be more important if you try to increase the data volume.

## Note

The project structure follows a modular approach to facilitate the expansion and mantainability. In addition, it follows a single responsability principle and separation of concern. Keep this principle as part of good practices and clean code.

## PyPI

The project was released as a Python packaged in [PyPI](https://pypi.org/project/focapd/).

## Disclaimer

The views expressed in this article are those of the authors and do not necessarily represent the views or policies of the U.S. Environmental Protection Agency. Any mention of trade names, products, or services does not imply an endorsement by the U.S. Government or the U.S. Environmental Protection Agency. The U.S. Environmental Protection Agency does not endorse any commercial products, service, or enterprises.
