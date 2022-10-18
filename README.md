# Overview
This project aims to get a fully functional test lab Netbox instance up using Vagrant.  It also includes a script to load some sample data.

## How
The Vagrantfile basically consolidates all the Netbox installation steps into a shell provisioner.  It also copies over some of the configuration files and installs a few nice-to-have packages.

## Requirements
The only real requirements are [Vagrant](https://www.vagrantup.com/) with [VirtualBox](https://www.virtualbox.org/).  No other Vagrant providers have been tested, so let us know if you get it working another way - we'd love to hear what works and what doesn't.  Also, this has only been tested on MacOS, but should function the same in Windows - again, let us know.

## Installation (or not) and Use
There's no real installation required here, all that need be done is clone the repo and "vagrant up"

    git clone 
    cd netbox-vagrant-baselab
    vagrant up

After the VM boots and runs through its provisioning scripts, you should have a fully installed and operable Netbox instance.  The Vagrantfile includes an automatic port forwarding on the host machine port 8081, so if you navigate to http://localhost:8081 on the host machine that should take you to the Netbox login.  The default credentials are **admin/netbox123**

## Loading Sample Data
This repo also includes a script, *load_ls_data.py*, that can be used to quickly load some sample data into Netbox.  Without modification, the script will load up a 2 Spine, 4 Leaf Arista CEOS clos topology with all the required connections and IP addressing.  Start by ssh'ing to the Vagrant guest (from the repo folder):

    vagrant ssh

Once ssh'd into the guest, the script can be run as follows:

    python3 /vagrant/load_ls_data.py

It will provide some output about the objects it is creating and status.  After the script run is complete, you can log into Netbox and begin testing (or just poking around - this should give you a feel for some of the basic Netbox data and objects).

### Customizing the Data
Some of the data in the *load_ls_data.py* script can be customized by modifying the global variables at the top of the script.  If, for example, you wanted to change the device manufacturer or model, that could be accomplished by editing the MANUFACTURERS and DEVICE_TYPES variables, respectively.  Most of the globals should be fairly safe to modify using sane values, but just note that the script assumes a leaf/spine clos topology so modifying the DEVICES should take that into consideration.

## API Token
An API token for the 'admin' user is automatically generated during the provisioning process.  It is located at ```/home/vagrant/nb_api_token``` and can be used for testing API calls.  The ```pynetbox``` library is also installed by default and can be leveraged for testing Python scripts.

## Vagrant Note - additional private networks
The provided Vagrantfile adds two additonal private networks:

* A host-only connection. This can be used to connect direct from the host to the guest, if for some reason you don't want to use the port forwarding.
* An internal connection. This is an internal (guest-only) network that can be used to communicate with other Vagrant VMs.  The name of the network is 'oob-mgmt' and the IP is hardcoded to 172.16.2.16/24.  If on the off chance there is a collision with either the name or IP address in your local VirtualBox configuration, you can comment out or remove the following lines out of the Vagrantfile:

```
    config.vm.network "private_network", virtualbox__intnet: "oob-mgmt", auto_config: false

    config.vm.provision "shell", name: "Updating OOB IP address", inline: <<-SHELL
      ip address add 172.16.2.16/24 dev enp0s8
      ip link set dev enp0s8 up
    SHELL
```