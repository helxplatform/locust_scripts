import logging
import random
import re
import os
import json
from pathlib import Path
from time import time

from locust import events
from locust import HttpUser, TaskSet, task, between

from flask import Blueprint, render_template, jsonify, make_response

logger = logging.getLogger(name="LoadTestLogger")
c_handler = logging.StreamHandler()
c_format = logging.Formatter('%(levelname)s - %(asctime)s - %(funcName)s - %(thread)d - %(message)s')
c_handler.setFormatter(c_format)
logger.addHandler(c_handler)
logger.setLevel('DEBUG')

test_users_path = Path(__file__).parent.resolve(strict=True)

apps = ["jupyter-education"]
jupyter_apps = ["jupyter-education", "jupyter-ds"]
users_credentials = []

active_instances_count = 0
max_instances = os.environ.get("MAX_INSTANCES", 500)
instances_live = 0

host_under_test = os.environ.get("HOST_NAME")
host_name = host_under_test.split("/")[2]

with open(f"{test_users_path}/users.txt", "r") as users:
    for user in users.readlines():
        username, password, email = user.split(",")
        users_credentials.append((username, password))


class UserBehaviour(TaskSet):
    launch_secs = 0

    def __init__(self, parent):
        super().__init__(parent)
        self.current_user = ""
        self.session_id = ""
        self.csrf_token = ""
        self.x_srf_token = ""
        self.app_ids = []

    def get_random_number(self, number):
        r_num = random.randint(0, number - 1)
        return r_num

    def on_start(self):
        resp = self.client.get("/apps", name="Get csrf token")
        if len(users_credentials) > 0:
            r_num = self.get_random_number(len(users_credentials))
            u_name, pw = users_credentials[r_num]
            self.current_user = u_name
        else:
            logger.debug("-- No new user available")
        self.csrf_token = resp.cookies['csrftoken']
        with self.client.post(
                "/accounts/login/?next=/apps/",
                name="Login",
                data={"csrfmiddlewaretoken": self.csrf_token, "login": f"{u_name}", "password": f"{pw}"},
                catch_response=True
        ) as resp:
            if "sessionid" in resp.cookies.keys():
                self.session_id = resp.cookies["sessionid"]
            else:
                logger.debug(f"-- Login for user {username} failed")

    @task
    def launch_apps(self):
        global max_instances
        global active_instances_count
        global instances_live

        r_num = self.get_random_number(len(apps))
        app_sid = None
        app_name = apps[r_num]

        max_tries = os.environ.get("MAX_TRIES", 500)

        no_of_notebooks = int(os.environ.get("NOTEBOOKS_COUNT", 30))

        if active_instances_count < int(max_instances):
            with self.client.post(f"/api/v1/instances/",
                                  name="Launch the app",
                                  headers={"X-CSRFToken": self.csrf_token},
                                  cookies={"sessionid": self.session_id, "csrftoken": self.csrf_token},
                                  catch_response=True,
                                  data={"app_id": f"{app_name}", "cpus": 0.5, "gpus": None, "memory": "2G"}) as resp:
                logger.debug(f"-- Successfully launched an instance by user {self.current_user} -- No of ACTIVE instances {instances_live}")
                sid_match = re.search("/[0-9,a-z,A-Z]{32}/", resp.text)
                if sid_match:
                    sid = sid_match.group().split("/")[1]
                    app_sid = sid
                    self.app_ids.append(f"{sid}")
                    logger.debug(f"-- App with app sid {sid} added to the list for user {self.current_user}")
                else:
                    logger.debug("-- Adding app to the list failed")

            for i in range(0, int(max_tries)):
                with self.client.get(f"/private/{app_name}/{self.current_user}/{app_sid}/",
                                       name=f"Check the status of instance {app_sid} launched by user {self.current_user}",
                                       cookies={"sessionid": self.session_id},
                                       context={"app_sid": app_sid, "current_user": self.current_user}
                                       ) as resp:
                    if resp.status_code != 200:
                        logger.debug(f"In app status")
                        continue
                    else:
                        logger.debug(f"-- App is receiving traffic")
                        cookies = resp.cookies._cookies
                        if cookies:
                            xsrf_cookie_object = cookies[host_name]['/']['_xsrf']
                            x_srf_token = xsrf_cookie_object.value
                            self.x_srf_token = x_srf_token
                        break

            if app_name in jupyter_apps:
                for i in range(0, no_of_notebooks + 1):
                    with self.client.post(f"/private/{app_name}/{self.current_user}/{app_sid}/api/contents/work",
                                          name=f"Creating notebooks for instance {app_sid}",
                                          cookies={"sessionid": self.session_id, "csrftoken": self.csrf_token},
                                          headers={"X-CSRFToken": self.x_srf_token},
                                          catch_response=True) as resp:
                        if resp.status_code == 201:
                            logger.debug(f"Created test notebook {i} on instance {app_sid}")
                            continue
                        else:
                            logger.debug(f"test notebook {i} creation on instance {app_sid} failed.")

            if app_name in jupyter_apps:
                for i in range(0, no_of_notebooks + 1):
                    if i == 0:
                        notebook = "untitled"
                    else:
                        notebook = f"untitled{i}"
                    with self.client.patch(f"/private/{app_name}/{self.current_user}/{app_sid}/api/contents/work/{notebook}",
                                          json={"path": f"work/{app_sid}-{self.current_user}-{i}.ipynb"},
                                          name=f"Renaming notebooks for instance {app_sid}",
                                          cookies={"sessionid": self.session_id, "csrftoken": self.csrf_token},
                                          headers={"X-CSRFToken": self.x_srf_token},
                                          catch_response=True) as resp:
                        if resp.status_code == 201:
                            logger.debug(f"Renaming test notebook {i} on instance {app_sid}")
                            continue
                        else:
                            logger.debug(f"test notebook {i} renaming on instance {app_sid} failed.")
        else:
            logger.debug(f"Successfully launched all the instances. LIVE COUNT {instances_live}")

    @task
    def get_apps(self):
        with self.client.get("/api/v1/instances/",
                             name="Get the apps",
                             headers={"X-CSRFToken": self.csrf_token},
                             cookies={"sessionid": self.session_id, "csrftoken": self.csrf_token},
                             catch_response=True) as resp:
            apps_list = json.loads(resp.text)
            if len(apps_list) > 0:
                for app in apps_list:
                    logger.debug(f"-- App {app}")
                    app_id = app["sid"]
                    self.app_ids.append(f"{app_id}")
        logger.debug(f"-- User {self.current_user} has {len(self.app_ids)} active -- {self.app_ids}")

    @task(5)
    def delete_apps(self):
        if len(self.app_ids) > 0:
            r_num = self.get_random_number(len(self.app_ids))
            app_id = self.app_ids[r_num]
            with self.client.delete(
                    f"/api/v1/instances/{app_id}/",
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
    wait_time = between(0, 0.1)
    host = host_under_test


launch_times = {}
extend = Blueprint(
    "extend",
    "extend_web_ui",
    static_folder=f"{test_users_path}/static/",
    static_url_path="/extend/static/",
    template_folder=f"{test_users_path}/templates/",
)


@events.init.add_listener
def on_locust_init(environment, **kwargs):

    if environment.web_ui:
        @extend.route("/launch-times")
        def total_content_length():
            report = {"stats": []}
            if launch_times:
                stats_tmp = []

                for username, instances in launch_times.items():
                    for instance, launch_time in instances.items():

                        stats_tmp.append(
                            {"username": username, "instance": instance, "launch_time": launch_time}
                        )
                    report = {"stats": stats_tmp}
                return jsonify(report)
            return jsonify(launch_times)

        @extend.route("/extend")
        def instance_statistics():
            environment.web_ui.update_template_args()
            return render_template("extend.html", **environment.web_ui.template_args)
        environment.web_ui.app.register_blueprint(extend)

        @extend.route("/launch-times/csv")
        def request_launch_times_csv():
            response = make_response(launch_times_csv())
            file_name = f"launch_times{time()}.csv"
            disposition = f"attachment;filename={file_name}"
            response.headers["Content-type"] = "text/csv"
            response.headers["Content-disposition"] = disposition
            return response

        def launch_times_csv():
            """Returns launch times as CSV"""
            rows = [
                ",".join(
                    [
                        '"Username"',
                        '"Instance"',
                        '"Launch Times"',
                        ]
                )
            ]

            if launch_times:
                for username, instance, times in launch_times.items():
                    rows.append(f"{username, instance, launch_times}")

            return "/n".join(rows)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    if "app_sid" in context.keys():
        app_sid = context["app_sid"]
        if "current_user" in context.keys():
            current_user = context["current_user"]
            launch_times.setdefault(current_user, {}).setdefault(app_sid, 0)
            launch_times[current_user][app_sid] += response_time
