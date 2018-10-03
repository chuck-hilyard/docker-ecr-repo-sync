# this is called by docker run
#
# starts jenkins
# installs plugins
# adds github based projects to jenkins/jobs

import http.client
import boto3
import jenkins
import json
import os
import requests
import socket
import subprocess
import time

def install_software():
  # install build/test software
  # TODO: make sure the previous install is done prior to moving on
  subprocess.run(["sudo", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-yq", "awscli"])
  time.sleep(30)
  subprocess.run(["pip3", "install", "consul_kv"])

def scrape_consul_for_deployed_apps():
  print("scraping consul for deployed apps")
  url = 'http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/?keys&separator=/'
  response = requests.get(url)
  toplevel_keys_json = json.loads(response.text)

  # for each key found verify that it has a github repo and branch configuration setting, otherwise it's
  # probably not an app that we should deploy w/ jenkins
  for x in toplevel_keys_json:
      project_name = x.strip('/')
      branch_url = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/branch?raw".format(project_name)
      response_branch_url = requests.get(branch_url)
      test1 = response_branch_url.status_code
      branch = response_branch_url.text

      github_url = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/github_repo?raw".format(project_name)
      response_github_url = requests.get(github_url)
      test2 = response_github_url.status_code
      github_repo = response_github_url.text

      ecr_repo = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/ecr_repo?raw".format(project_name)
      response_ecr_repo = requests.get(ecr_repo)
      test3 = response_ecr_repo.status_code
      ecr_repo = response_github_url.text

      if test1 == 200 and test2 == 200 and test3 == 200:
        print("{} has the right anatomy".format(project_name))

def is_consul_up():
  print("is consul up?")
  return True

def main():
  while True:
    print("main loop")
    status = is_consul_up()
    if status == True:
      print("consul is up")
      scrape_consul_for_deployed_apps()
    else:
      print("consul is DOWN...or i can't get to it")
    print("sleeping for 60")
    time.sleep(60)


if __name__ == '__main__':
  install_software()
  main()
