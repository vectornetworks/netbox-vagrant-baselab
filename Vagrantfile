Vagrant.configure("2") do |config|
    config.vm.box = "ubuntu/focal64"
    config.vm.network "private_network", virtualbox__intnet: "oob-mgmt", auto_config: false
    config.vm.network "private_network", type: "dhcp"
    config.vm.network "forwarded_port", guest: 80, host: 8081
  
    config.vm.provision "shell", name: "Updating OOB IP address", inline: <<-SHELL
      ip address add 172.16.2.16/24 dev enp0s8
      ip link set dev enp0s8 up
    SHELL
  
    config.vm.provider "virtualbox" do |v|
      v.memory = 4096
    end

    config.vm.provision "shell", name: "Installing Netbox", privileged: true, env: {:DJANGO_SUPERUSER_PASSWORD=>'netbox123', :DJANGO_SUPERUSER_USERNAME=>'admin', :DJANGO_SUPERUSER_EMAIL=>'user@host.com'}, inline: <<-SHELL
      apt update
      apt install net-tools
      apt install -y postgresql
      systemctl start postgresql
      systemctl enable postgresql
      sudo -u postgres psql -f /vagrant/create_netbox_db.sql
      apt install -y redis-server
      apt install -y python3 python3-pip python3-venv python3-dev build-essential libxml2-dev libxslt1-dev libffi-dev libpq-dev libssl-dev zlib1g-dev
      pip3 install --upgrade pip
      mkdir -p /opt/netbox/ && cd /opt/netbox/
      git clone -b master --depth 1 https://github.com/netbox-community/netbox.git .
      adduser --system --group netbox
      chown --recursive netbox /opt/netbox/netbox/media/
      cp /vagrant/netbox_cfg.py /opt/netbox/netbox/netbox/configuration.py
      /opt/netbox/upgrade.sh
      source /opt/netbox/venv/bin/activate
      cd /opt/netbox/netbox
      python3 manage.py createsuperuser --noinput
      python3 -m pip install netbox-bgp
      cd /opt/netbox/netbox/
      python3 manage.py migrate
      python3 collectstatic
      deactivate
      cp /opt/netbox/contrib/gunicorn.py /opt/netbox/gunicorn.py
      cp -v /opt/netbox/contrib/*.service /etc/systemd/system/
      systemctl daemon-reload
      systemctl start netbox netbox-rq
      systemctl enable netbox netbox-rq
      apt install -y nginx
      cp /vagrant/nginx.conf /etc/nginx/sites-available/netbox
      rm /etc/nginx/sites-enabled/default
      ln -s /etc/nginx/sites-available/netbox /etc/nginx/sites-enabled/netbox
      systemctl restart nginx
      python3 -m pip install pynetbox
    SHELL

    config.vm.provision "shell", name: "Generating API Token", privileged: false, inline: <<-'USERSHELL'
      curl -X POST \
      -H "Content-Type: application/json" \
      -H "Accept: application/json; indent=4" \
      http://localhost/api/users/tokens/provision/ \
      --data '{"username": "admin", "password": "netbox123"}' > /home/vagrant/token_out
      
      sed -n -E 's/.*"key": "(.*)",/\1/p' /home/vagrant/token_out > /home/vagrant/nb_api_token
    USERSHELL
  end
