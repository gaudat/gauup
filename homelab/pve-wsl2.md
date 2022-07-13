# Installing Proxmox VE on WSL2

So I recently moved to another country. Now my home lab server is over 200 ms away. The solution? Put the home lab on my laptop.

This is performed on a Zephyrus G14 2022 laptop. Note that this has an AMD CPU. Intel CPU seems not to work but I have not tried.

### 1. Install WSL2 and Debian

Proxmox is based on Debian so that is obviously the first thing I tried.

In an Admin Powershell (`Win` + `x` then `a` from desktop):
```sh
wsl --install -d Debian
```

Set up the admin user in the new window.

After getting the Debian shell:
```sh
# Get a root shell
sudo -i

# Set root password. Need this to log in PVE web UI.
passwd

# Confirm which Debian version it is
cat /etc/os-release
# As of 2022-07 it is Debian 9 stretch.
```
Go to [PVE wiki](https://pve.proxmox.com/wiki/FAQ#faq-support-table) and see which version to install. 
For Debian 9 it's PVE 5.x.

### Install prerequiste packages
```sh
apt update
apt install apt-transport-https python3-requests lsb-release
```

### Add Proxmox repo and keys
Update "stretch" or "9" to WSL2's Debian version, and "5" to the Proxmox major version number.
```sh
# https://pve.proxmox.com/wiki/Install_Proxmox_VE_on_Debian_Stretch

echo "deb http://download.proxmox.com/debian/pve stretch pve-no-subscription" > /etc/apt/sources.list.d/pve-install-repo.list

wget http://download.proxmox.com/debian/proxmox-ve-release-5.x.gpg -O /etc/apt/trusted.gpg.d/proxmox-ve-release-5.x.gpg
chmod +r /etc/apt/trusted.gpg.d/proxmox-ve-release-5.x.gpg  # optional, if you have a changed default umask
```

### Genie
WSL2 does not have systemd bundled. To solve this we use [Genie](https://github.com/arkane-systems/genie). 

Update "stretch" to WSL2's Debian version. Wget may fail to verify the TLS certificates. It can be bypassed by the `--no-check-certificate` flag.

```sh
# https://arkane-systems.github.io/wsl-transdebian/

wget -O /etc/apt/trusted.gpg.d/wsl-transdebian.gpg https://arkane-systems.github.io/wsl-transdebian/apt/wsl-transdebian.gpg

chmod a+r /etc/apt/trusted.gpg.d/wsl-transdebian.gpg

cat << EOF > /etc/apt/sources.list.d/wsl-transdebian.list
deb https://arkane-systems.github.io/wsl-transdebian/apt/ stretch main
deb-src https://arkane-systems.github.io/wsl-transdebian/apt/ stretch main
EOF
```

### Add Microsoft repos
Genie depends on .NET runtime which is not available on Debian default archives. The WSL installation may somehow forget to install the Microsoft repos. If `/etc/apt/trusted.gpg.d/microsoft.asc` is not present we may need to add the repo again.

Update "stretch" and "9" to WSL2's Debian version. Wget may fail to verify the TLS certificates. It can be bypassed by the `--no-check-certificate` flag.

```sh
# https://docs.microsoft.com/en-us/windows-server/administration/linux-package-repository-for-microsoft-software

wget -O /etc/apt/trusted.gpg.d/microsoft.asc https://packages.microsoft.com/keys/microsoft.asc 

cat << EOF > /etc/apt/sources.list.d/microsoft.list
deb https://packages.microsoft.com/debian/9/prod stretch main
deb-src https://packages.microsoft.com/debian/9/prod stretch main
EOF
```

After all repos are added run `apt update` and fix any errors.

### Install Genie
In Debian root shell:
```sh
apt install -y systemd-genie
```

Reboot the WSL2 system after installing Genie. In PowerShell:
```sh
wsl --shutdown
wsl 
```

And you should be back to a Debian shell.

### Start Genie
In Debian **admin** (not root) shell:
```sh
genie -s
# Waiting for systemd....!!!!!
```
Sometimes Genie may get stuck here. Press `Ctrl` + `c` and run `genie -s` again in that case. You will be greeted with a single `$`.

Let's get to a more sensible shell.
```sh
sudo -l
# root@DESKTOP-7ADUAG1-wsl:~#
```
Note that `-wsl` is appended to the hostname. 

### From now on we will only work with this shell under Genie but not the original one. If you closed this shell, just run `wsl` again from Windows and it will be back. If you rebooted the machine, start Genie and check the hostname ends with `-wsl`.

If you run `genie -s` again in this shell, the hostname will be changed to `...-wsl-wsl`. In that case run `wsl --shutdown` in Windows to reset.

Run `systemctl` to verify systemd is running.

### Install Proxmox

You may want to export the machine before running this. Because if this installation goes wrong you will need to rebuild from scratch.

In PowerShell:
```
wsl --shutdown
wsl --export Debian pve-checkpoint.tar
wsl
```

In the Genie root shell:
```sh
apt install proxmox-ve --no-install-recommends
```

Wait until it is done. If errors pop up when configuring packages, it is because systemd is not running.

It is normal that the services fail to start. It's because WSL2 machines do not preserve IP and MAC addresses on reboot.

Another reminder that we will only be working in a Genie root shell from now on.

### Network configuration

Set WSL2 to not overwrite the hosts file. Add these lines to `/etc/wsl.conf`:
```
[network]
generateHosts = false
```

Overwrite `/etc/hosts` with the following, then replace the hostname (`DESKTOP-7ADUAG1`) with that of your machine.
```
127.0.0.1       localhost
172.30.27.206 DESKTOP-7ADUAG1.localdomain DESKTOP-7ADUAG1-wsl

# The following lines are desirable for IPv6 capable hosts
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
```

Then we will drop a service to change the hosts files before Proxmox services start.

In `/usr/local/bin/pvepreup.sh`:
```sh
#!/bin/bash

ip4addr=`ip -4 a | awk '/inet .* scope global/ {split($2,out,"/");print out[1]}'`

awk "/^127\.0\.0\.1.*`hostname`/ {next} /`hostname`/ {\$1 = \"$ip4addr\"} // {print}" /etc/hosts > /etc/hosts.new && mv /etc/hosts.new /etc/hosts
```

In `/etc/systemd/system/pvepreup.service`:
```
[Unit]
Description=Fix /etc/hosts before starting PVE
Before=pve-cluster.service
After=network.target
DefaultDependencies=no
Before=shutdown.target
Conflicts=shutdown.target

[Service]
ExecStart=/usr/local/bin/pvepreup.sh
KillMode=mixed
TimeoutStopSec=10
Type=oneshot

[Install]
WantedBy=multi-user.target
```

Then run:
```
chmod +x /usr/local/bin/pvepreup.sh
systemctl daemon-reload
systemctl enable pvepreup
systemctl status pvepreup
```
Check the service is loaded without any errors.

### Verify everything is working

Reboot or start the WSL from PowerShell:
```sh
wsl --shutdown # If you need to reboot
wsl
```

In the Debian shell run:
```
me@DESKTOP-7ADUAG1:~$ genie -s
# Waiting for systemd....!!!!!
# If stuck here Ctrl + C and run genie -s again

# Inside Genie now
$ sudo -l

root@DESKTOP-7ADUAG1-wsl:~#
```

Once we get to Genie root shell Proxmox should be running. The Web UI can be reached at `https://localhost:8006`.

For SSH access, drop your public key to `/root/.ssh/authorized_keys`. This is symlinked to another file by Proxmox.

### What if it does not work
Places to check (in Genie root shell):
```
systemctl
systemctl status pvedaemon
netstat -plnt
cat /etc/hosts
tail /var/log/syslog
```