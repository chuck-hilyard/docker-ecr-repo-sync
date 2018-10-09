FROM ubuntu:latest

RUN apt-get update && apt-get upgrade -y && DEBIAN_FRONTEND=noninteractive apt-get install -y sudo python3 python3-pip python3-jenkins python3-boto3 jq 

RUN useradd -m -s /bin/bash ecrwatcher

ADD init.py /tmp/init.py

WORKDIR /home/ecrwatcher

USER ecrwatcher

CMD [ "python3", "-u", "/tmp/init.py" ]
