#
# Script must be run as sudo
# run this inside smartShards dir (a.k.a dont move to run)
# some post install steps maybe necessary see https://docs.docker.com/engine/install/linux-postinstall/
#

######################################################
#                 system settings                    #
######################################################

# make firewall exceptions for swarm (overlay network for docker)
ufw allow 2376/tcp && sudo ufw allow 7946/udp &&
ufw allow 7946/tcp && sudo ufw allow 80/tcp &&
ufw allow 2377/tcp && sudo ufw allow 4789/udp

#echo "## works best with <= 500 client computers ##" >> /etc/sysctl.conf
#echo "# Force gc to clean-up quickly" >> /etc/sysctl.conf
#echo "net.ipv4.neigh.default.gc_interval = 3600" >> /etc/sysctl.conf
#echo "" >> /etc/sysctl.conf
#echo "# Set ARP cache entry timeout" >> /etc/sysctl.conf
#echo "net.ipv4.neigh.default.gc_stale_time = 3600" >> /etc/sysctl.conf
#echo "" >> /etc/sysctl.conf
echo "# Setup DNS threshold for arp " >> /etc/sysctl.conf
echo "net.ipv4.neigh.default.gc_thresh3 = 4096" >> /etc/sysctl.conf
echo "net.ipv4.neigh.default.gc_thresh2 = 2048" >> /etc/sysctl.conf
echo "net.ipv4.neigh.default.gc_thresh1 = 1024" >> /etc/sysctl.conf

######################################################
#    install docker, python3 and needed libraries    #
######################################################

# make sure old version is not present 
apt-get remove docker docker-engine docker.io containerd runc

# install docker and python3
apt-get update
apt-get -y \
    install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common \
    python3 \
    python3-pip

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -

add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

apt-get -y install docker-ce docker-ce-cli containerd.io

pip3 install docker
pip3 install psutil
pip3 install mock
pip3 install flask

######################################################
#              build sawtooth image                  #
######################################################
docker build -t sawtooth:final -f  ./base-node.Dockerfile .

######################################################
#               add src to python path               #
######################################################
export PYTHONPATH=$PYTHONPATH:$PWD

######################################################
#                  final message                     #
######################################################
echo "if you have not done so yet, run the following comands then reboot\n"
echo "sudo groupadd docker; sudo usermod -aG docker $USER; newgrp docker"
echo "then rerun setup.sh to continue setup"

