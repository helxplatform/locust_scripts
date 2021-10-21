# Appstore Locust Scripts

This folder contains scripts for running [Locust](https://locust.io/) load tests against the Helx Appstore.

## Pre-requisites

- Python 3.9
- Create python virtual environment: `python -m venv venv`
- Install requirements: `source venv/bin/activate && pip install -r requirements.txt`

## Preparing Appstore

- Generate a users.txt file of users to be added to appstore's database:

      python create_test_users.py <number of users>

- Create a Kubernetes Secret on the cluster using users.txt:

      kubectl create secret generic test-users-secret --from-file=users.txt

- Deploy Helx using the helm chart with the following extra values:


      django:
        ALLOW_DJANGO_LOGIN: "true"
        CREATE_TEST_USERS: "true"
        CREATE_TEST_VOLUME: "true"
        TEST_USERS_PATH: "/tmp"
        TEST_USERS_SECRET: "test-users-secret"
      loadTest: true

- Wait about 1 minute per 100 users for the users to be added to the database.

## Running locust

- Set the following environment variables,

      export MAX_TRIES=<some number>
      export HOST_NAME=https://<some helx instance>
      export MAX_INSTANCES=<some number>
      export NOTEBOOKS_COUNT=<some number>

- Copy the users.txt to the current directory

      locust -f ./load_test.py

Web UI is available on http://127.0.0.1:8089/extend.
Set the User spawning rate, and the Hatch rate. The Launch Times tab shows the time taken from Launch to App receiving traffic.
