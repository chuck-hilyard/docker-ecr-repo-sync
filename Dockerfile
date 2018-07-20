FROM jenkins/jenkins:latest

USER root

RUN /usr/local/bin/install-plugins.sh git matrix-auth workflow-aggregator docker-workflow blueocean credentials-binding 

ENV JENKINS_USER admin
ENV JENKINS_PASS admin

RUN apt-get -y update && apt-get -y upgrade && apt-get -y install python3 python3-jenkins python3-pip vim
RUN pip3 install requests

COPY --chown=jenkins *.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY --chown=jenkins *.xml /var/jenkins_home/
COPY aws_codebuild /root/.ssh/id_rsa

RUN ssh-keyscan github.com >> ~/.ssh/known_hosts
RUN cd /tmp; git clone https://github.com/chuck-hilyard/docker-jenkins-master
RUN cd /etc; git clone https://github.com/chuck-hilyard/docker-jenkins-master
RUN cd /var/jenkins_home; git clone https://github.com/chuck-hilyard/docker-jenkins-master
#RUN cd /var/jenkins_home; git clone https://github.com/chuck-hilyard/docker-jenkins-master 
RUN chown -R jenkins:jenkins /var/jenkins_home/

#COPY --chown=jenkins aws_codebuild /var/jenkins_home/.ssh/id_rsa
#RUN ssh-keyscan github.com >> /var/jenkins_home/.ssh/known_hosts
#RUN git clone https://github.com/chuck-hilyard/docker-jenkins-master /var/jenkins_home/docker-jenkins-master --branch master
#RUN chown -R jenkins:jenkins /var/jenkins_home/

VOLUME /var/jenkins_home

USER jenkins

CMD [ "python3", "-u", "/tmp/docker-jenkins-master/init.py" ]
