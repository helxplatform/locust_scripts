import logging
import random
import re
import os
from pathlib import Path
from bs4 import BeautifulSoup

from locust import HttpUser, TaskSet, SequentialTaskSet, task, between

logger = logging.getLogger(name="LoadTestLogger")
c_handler = logging.StreamHandler()
c_format = logging.Formatter('%(levelname)s - %(asctime)s - %(funcName)s - %(thread)d - %(message)s')
c_handler.setFormatter(c_format)
logger.addHandler(c_handler)
logger.setLevel('DEBUG')

TEST_USERS_PATH = Path(__file__).parent.resolve(strict=True)

APPS = ["jupyter-education"]

USERS_CREDENTIALS = []

with open(f"{TEST_USERS_PATH}/users.txt", "r") as users:
    for user in users.readlines():
        username, password, email = user.split(",")
        USERS_CREDENTIALS.append((username, password))


class UserBehaviour(TaskSet):

    def __init__(self, parent):
        super().__init__(parent)
        self.current_user = ""
        self.session_id = ""
        self.csrf_token = ""
        self.app_ids = []

    def get_random_number(self, number):
        r_num = random.randint(0, number - 1)
        return r_num

    def on_start(self):
        resp = self.client.get("/apps", name="Get csrf token")
        if len(USERS_CREDENTIALS) > 0:
            r_num = self.get_random_number(len(USERS_CREDENTIALS))
            username, password = USERS_CREDENTIALS[r_num]
            self.current_user = username
        else:
            logger.debug("-- No new user available")
        self.csrf_token = resp.cookies['csrftoken']
        logger.debug(f"-- Got CSRFToken for user {username}.")
        with self.client.post(
                "/accounts/login/?next=/apps/",
                name="Login",
                data={"csrfmiddlewaretoken": self.csrf_token, "login": f"{username}", "password": f"{password}"},
                catch_response=True
        ) as resp:
            if "sessionid" in resp.cookies.keys():
                self.session_id = resp.cookies["sessionid"]
                logger.debug(f"-- Got SessionID for user {username}.")
            else:
                logger.debug(f"-- Login for user {username} failed")

    @task
    def launch_apps(self):
        r_num = self.get_random_number(len(APPS))
        app_sid = ""
        app_name = APPS[r_num]
        MAX_TRIES = os.environ.get("MAX_TRIES", 500)
        with self.client.get(f"/start/?app_id={app_name}&cpu=0.5&memory=2G&gpu=0",
                             name="Launch the app",
                             cookies={"sessionid": self.session_id},
                             catch_response=True) as resp:
            logger.debug(f"-- Successfully launched an instance by user {self.current_user}")
            sid_match = re.search("/[0-9,a-z,A-Z]{32}/", resp.text)
            if sid_match:
                sid = sid_match.group().split("/")[1]
                app_sid = sid
                self.app_ids.append(sid)
            else:
                logger.debug("-- Adding app to the list failed")
        for i in range(0, int(MAX_TRIES)):
            resp = self.client.get(f"/private/{app_name}/{self.current_user}/{app_sid}/",
                                   name="Check the status",
                                   cookies={"sessionid": self.session_id},
                                   )
            if resp.status_code != 200:
                continue
            else:
                logger.debug("-- App is receiving traffic")
                break

    @task
    def get_apps(self):
        with self.client.get("/apps", name="Get the apps", cookies={"sessionid": self.session_id},
                             catch_response=True) as resp:
            content = resp.content
            soup = BeautifulSoup(content, "html.parser")
            apps_table = soup.find("tbody")
            apps_list = apps_table.find_all("tr")
            if len(apps_list) > 0:
                for row in apps_table.find_all("tr"):
                    app_id = row.button['id']
                    if app_id not in self.app_ids:
                        self.app_ids.append(app_id)
                    # connect_url = row.a['href']
        logger.debug(f"-- User {self.current_user} has {len(self.app_ids)} active -- {self.app_ids}")

    @task(5)
    def delete_apps(self):
        if len(self.app_ids) > 0:
            r_num = self.get_random_number(len(self.app_ids))
            app_id = self.app_ids[r_num]
            with self.client.post(
                    "/list_pods/",
                    name="Delete the app",
                    headers={"X-CSRFToken": self.csrf_token},
                    cookies={"sessionid": self.session_id, "csrftoken": self.csrf_token},
                    data={"id": f"{app_id}", "action": "delete"},
                    catch_response=True) as resp:
                logger.debug(f"-- App with id {app_id} has been delete by user {self.current_user}")
                self.app_ids.remove(app_id)
        else:
            logger.debug(f"-- No currently active applications for user {self.current_user}.")

    def on_stop(self):
        self.client.cookies.clear()
        self.interrupt()


class WebUser(HttpUser):
    tasks = [UserBehaviour]
    wait_time = between(2, 5)
    host = os.environ.get("HOST_NAME")
