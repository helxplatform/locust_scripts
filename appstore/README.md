# Preparing Appstore

- Create a secrets file on the cluster using the users.txt.
- Deploy Helx using the helm chart.
  Following chart values are necessary
  
```
  django:
    ALLOW_DJANGO_LOGIN: "true"
    CREATE_TEST_USERS: "true"
    CREATE_TEST_VOLUME: "true"
    TEST_USERS_PATH: "/tmp"
    TEST_USERS_SECRET: "test-users-secret"
  loadTest: true
```
  
# Preparing Locust

## Pre-requisites

- python 3.9
- Create python virtual environment
- Install requirements
  
## Running locust

- Set the following environment variables,
```
export MAX_TRIES=<some number>
export HOST=<host name to test>
```

- Copy the users.txt to the current directory
```
locust -f ./load_test.py
```