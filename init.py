# this is called by docker run
#

import http.client
import boto3
import json
import os
import re
import requests
import subprocess
import time

def install_software():
  # install build/test software
  # TODO: make sure the previous install is done prior to moving on
  subprocess.run(["sudo", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-yq", "awscli"])
  time.sleep(30)
  subprocess.run(["pip3", "install", "consul_kv"])

def get_deployed_apps_from_consul():
  print("scraping consul for deployed apps")
  url = 'http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/?keys&separator=/'
  response = requests.get(url)
  toplevel_keys_json = json.loads(response.text)
  return toplevel_keys_json

def retrieve_app_configs_from_consul(toplevel_keys_json):
  # for each key found verify that it has a github repo and branch configuration setting - that's how we know it's a deployed app
  local_dict = {}
  for x in toplevel_keys_json:
    project_name = x.strip('/')
    print("pulling configs for {}".format(project_name))
    aws_account_number_url = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/AWS_ACCOUNT_NUMBER?raw".format(project_name)
    response_aws_account_number = requests.get(aws_account_number_url)
    aws_account_number = response_aws_account_number.text

    branch_url = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/branch?raw".format(project_name)
    response_branch_url = requests.get(branch_url)
    test1 = response_branch_url.status_code
    branch = response_branch_url.text

    github_url = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/github_repo?raw".format(project_name)
    response_github_url = requests.get(github_url)
    test2 = response_github_url.status_code
    github_repo = response_github_url.text

    ecr_repo_url = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/ecr_repo?raw".format(project_name)
    response_ecr_repo = requests.get(ecr_repo_url)
    test3 = response_ecr_repo.status_code
    ecr_repo = response_ecr_repo.text
    if ecr_repo:
      ecr_image_digest_url = "http://consul.user1.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/ecr_image_digest?raw".format(project_name)
      response_ecr_image_digest = requests.get(ecr_image_digest_url)
      if re.match('^sha256:[a-zA-Z0-9]*$', response_ecr_image_digest.text):
        if response_ecr_image_digest.status_code == 200:
          ecr_image_digest = response_ecr_image_digest.text
        else:
          ecr_image_digest = response_ecr_image_digest.status_code
      else:
        ecr_image_digest = 404

    if test1 == 200 and test2 == 200 and test3 == 200:
      print("{} has the right anatomy for a deployed app".format(project_name))
      local_dict.update({ project_name: [aws_account_number, branch, github_repo, ecr_repo, ecr_image_digest] })
    else:
      print("{} is NOT a deployed app".format(project_name))
  return local_dict

# maybe we'll use this
def whats_in_ecr(app_list, app_list_dict):
  # 1) if the consul:ecr_image_digest is empty AND the aws_ecr_image_digest is empty log a dumb condition
  # 2) if the consul:ecr_image_digest var is empty, restart the containers and populate the consul:ecr_image_digest
  # 3) if the consul:ecr_image_digest is populated compare it against the consul:ecr_image_digest.  if they differ, restart
  # the containers and update the consul:ecr_image_digest w/ the aws_ecr_image_digest
  # 4) if the consul:ecr_image_digest is populated but the aws:ecr_image_digest is empty do nothing
  # if the consul:ecr_image_digest is identical to aws_ecr_image_digest do nothing
  print("pull imageDigest from ecr")
  client = boto3.client('ecr')
  for k, v in app_list_dict.items():
    print("KEY:{} VALUE:{}".format(k, v))
    if app_list_dict[k][4] != 404:
      #response = client.describe_images(registryId=app_list_dict[k][0], repositoryName=app_list_dict[k][3], imageIds=[{ 'imageDigest': app_list_dict[k][4], 'imageTag': app_list_dict[k][1]}])
      response = client.describe_images(registryId=app_list_dict[k][0], repositoryName=app_list_dict[k][3], imageIds=[{'imageTag': app_list_dict[k][1]}])
      aws_ecr_image_digest = response['imageDetails'][0]['imageDigest']
      print("aws ecr image digest: ", aws_ecr_image_digest)
      app_list_dict[k].append(aws_ecr_image_digest)
      print("APP LIST DICT", app_list_dict)
    else:
      print("aws_ecr_image_digest is empty")
      app_list_dict[k].append('empty')

def exec_container_restart(app_list_dict):
  print("determine container restarts")
  for k,v in app_list_dict.items():
    print("APP:{}".format(k))
    print(v)

def restart_containers():
  pass
  # try the container restart
  # if it succeeds update the imagedigest in consul

def is_consul_up():
  print("is consul up?")
  return True

def main():
  while True:
    print("main loop")
    status = is_consul_up()
    if status == True:
      print("consul is up")
      app_list = get_deployed_apps_from_consul()
      print("the following apps are deployed: ", app_list)
      app_list_dict.update(retrieve_app_configs_from_consul(app_list))
      whats_in_ecr(app_list, app_list_dict)
      exec_container_restart(app_list_dict)
    else:
      print("i can't get to consul")
    print("sleeping for 60")
    time.sleep(60)


if __name__ == '__main__':
  #install_software()
  app_list_dict = {}
  main()
