# this is called by docker run
#

import http.client
import boto3
import botocore
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
  time.sleep(15)
  subprocess.run(["pip3", "install", "consul_kv"])
  time.sleep(15)
  subprocess.run(["curl", "-k", "--header", "\"X-Vault-Token:${var.VAULTKEY}\"", "--request", "GET", "https://10.233.136.68:8200/v1/secret/data/dev/usa/cert/aws-credentials", "|jq -r", "\'.data.key\'", ">>", "/home/ecrwatcher/.aws/credentials"])

def get_deployed_apps_from_consul():
  print("scraping consul for deployed apps")
  url = 'http://consul:8500/v1/kv/?keys&separator=/'
  response = requests.get(url)
  toplevel_keys_json = json.loads(response.text)
  return toplevel_keys_json

def retrieve_app_configs_from_consul(toplevel_keys_json):
  # for each key found verify that it has a github repo AND branch configuration setting - that's how we know it's a deployed app
  local_dict = {}
  for x in toplevel_keys_json:
    project_name = x.strip('/')
    print("[{}] pulling consul configs".format(project_name))
    aws_account_number_url = "http://consul:8500/v1/kv/{}/config/AWS_ACCOUNT_NUMBER?raw".format(project_name)
    response_aws_account_number = requests.get(aws_account_number_url)
    aws_account_number = response_aws_account_number.text

    ecs_cluster_url = "http://consul:8500/v1/kv/{}/config/ecs_cluster?raw".format(project_name)
    response_ecs_cluster = requests.get(ecs_cluster_url)
    ecs_cluster = response_ecs_cluster.text

    aws_region_url = "http://consul:8500/v1/kv/{}/config/REGION?raw".format(project_name)
    response_aws_region = requests.get(aws_region_url)
    aws_region = response_aws_region.text

    branch_url = "http://consul:8500/v1/kv/{}/config/branch?raw".format(project_name)
    response_branch_url = requests.get(branch_url)
    test1 = response_branch_url.status_code
    branch = response_branch_url.text

    github_url = "http://consul:8500/v1/kv/{}/config/github_repo?raw".format(project_name)
    response_github_url = requests.get(github_url)
    test2 = response_github_url.status_code
    github_repo = response_github_url.text

    ecr_repo_url = "http://consul:8500/v1/kv/{}/config/ecr_repo?raw".format(project_name)
    response_ecr_repo = requests.get(ecr_repo_url)
    test3 = response_ecr_repo.status_code
    ecr_repo = response_ecr_repo.text
    if ecr_repo:
      ecr_image_digest_url = "http://consul:8500/v1/kv/{}/config/ecr_image_digest?raw".format(project_name)
      response_ecr_image_digest = requests.get(ecr_image_digest_url)
      if re.match('^sha256:[a-zA-Z0-9]*$', response_ecr_image_digest.text):
        if response_ecr_image_digest.status_code == 200:
          ecr_image_digest = response_ecr_image_digest.text
        else:
          ecr_image_digest = response_ecr_image_digest.status_code
      else:
        ecr_image_digest = 404

    if test1 == 200 and test2 == 200 and test3 == 200:
      print("[{}] is anatomically correct".format(project_name))
      local_dict.update({ project_name: [aws_account_number, ecs_cluster, branch, github_repo, ecr_repo, ecr_image_digest] })
    else:
      print("[{}] is NOT a deployed app".format(project_name))
  return local_dict

def whats_in_ecr(app_list, app_list_dict):
  client = boto3.client('ecr', region_name='us-west-2')
  for k,v in app_list_dict.items():
    print("[{}] pull imageDigest from ecr".format(k))
    try:
      response = client.describe_images(registryId=app_list_dict[k][0], repositoryName=app_list_dict[k][4], imageIds=[{'imageTag': app_list_dict[k][2]}])
    except Exception as errormsg:
      print("[{}] something went wrong w/ the ecr image lookup ({})".format(k, errormsg))
      aws_ecr_image_digest = ""
      app_list_dict[k].append(aws_ecr_image_digest)
    else:
      aws_ecr_image_digest = response['imageDetails'][0]['imageDigest']
      app_list_dict[k].append(aws_ecr_image_digest)

def container_restart_logic(app_list_dict):
  for k,v in app_list_dict.items():
    if not app_list_dict[k][6]:
      print("[{}] aws ecr_image_digest is missing, skipping".format(k))
      continue
    if app_list_dict[k][5] == app_list_dict[k][6]:
      print("[{}] aws ecr_image_digest is identical to consul's ecr_image_digest".format(k))
      continue
    if app_list_dict[k][5] != app_list_dict[k][6]:
      print("[{}] aws ecr_image_digest differs from consul's ecr_image_digest".format(k))
      container_restart_status = restart_containers(app_list_dict[k])
      update_consul = True
      for status in container_restart_status:
        if status != 200:
          print("[{}] one container didn't properly restart, not updating consul".format(k))
          update_consul = False
    if update_consul == True:
      update_consul_ecr_image_digest(app_list_dict, k)
      del(update_consul)
    else:
      del(update_consul)

#TODO: if ecr_repo and ecs_cluster don't exist don't write ecr_image_digest (conflicting w/ terraform apply)
def update_consul_ecr_image_digest(app_list_dict, key):
  #for k,v in app_list_dict.items():
  print("[{}] updating consul ecr_image_digest".format(key))
  url = "http://consul:8500/v1/kv/{}/config/ecr_image_digest".format(key)
  response = requests.put(url, data=app_list_dict[key][6])
  print("CONSUL RESPONSE: ", response.status_code, response.reason)

def restart_containers(something):
  print("[{}] restarting containers".format(something[4]))
  container_restart_status = []
  client = boto3.client('ecs', region_name='us-west-2')
  try:
    tasks = client.list_tasks(cluster=something[1], serviceName=something[4])
  except client.exceptions.ServiceNotFoundException as e:
    print("ignoring exception {}", e)
    return container_restart_status
  for task in tasks['taskArns']:
    print("[{}] {}".format(something[4], task))
    response = client.stop_task(cluster=something[1], task=task, reason="docker-ecr-watcher restart due to state change")
    container_restart_status.append(response['ResponseMetadata']['HTTPStatusCode'])
  return container_restart_status

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
      print("the following apps MAY be deployed: ", app_list)
      app_list_dict.update(retrieve_app_configs_from_consul(app_list))
      whats_in_ecr(app_list, app_list_dict)
      container_restart_logic(app_list_dict)
    else:
      print("i can't get to consul")
    print("sleeping for 60")
    time.sleep(60)


if __name__ == '__main__':
  install_software()
  app_list_dict = {}
  region_name = ""
  main()
