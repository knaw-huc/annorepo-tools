# Annorepo-tools 

This contains some simple command-line tools for communicating with annorepo.

## Installation

First create a python virtual environment, then do:

```
$ pip install annorepo-tools
```

Or clone this repository and do:

```
$ pip install .
```

## Usage

```
$ upload-web-annotations -h
usage: upload-web-annotations [-h] -a annorepo_base_url -c container_id [-l container_label] [-k api_key] [-o] [input ...]

Upload a list of web annotations to an annorepo server in the given container (which will be created if it does not already exist)

positional arguments:
  input                 The json file containing the list of annotations, or a directory containing these json files (default: None)

options:
  -h, --help            show this help message and exit
  -a, --annorepo-base-url annorepo_base_url
                        The base URL of the AnnoRepo server to upload the annotations to. (default: None)
  -c, --container-id container_id
                        The id of the container the annotations should be added to. (will be created if it does not already exist) (default: None)
  -l, --container-label container_label
                        The label to give the container, if it needs to be created. (default: None)
  -k, --api-key api_key
                        The api-key to get access to the annorepo api (default: None)
  -o, --overwrite-existing-container
                        Add this argument to clear the container with the given container-id if one exists already. (default: False)
```
