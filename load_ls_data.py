import os
import re
import argparse
import yaml
import pynetbox

NB_URL = 'http://localhost'
NB_API_TOKEN = None

api_token_file = os.environ['HOME'] + "/nb_api_token"
if not NB_API_TOKEN and os.path.isfile(api_token_file):
    with open(api_token_file) as f:
        NB_API_TOKEN = f.read().strip()

def create_sites(nb, ls_data):
    for site in ls_data['sites']:
        try:
            print(f"Creating site '{site['name']}'...", end='')
            nb.dcim.sites.create(name=site['name'], slug=site['slug'])
            print("done")

        except pynetbox.core.query.RequestError as E:
            if E.error.find("name already exists") != -1:
                print("site already exists, skipping")
                continue
            else:
                raise

def create_roles(nb, ls_data):
    for role in ls_data['roles']:
        try:
            print(f"Creating role '{role['name']}'...", end='')
            nb.dcim.device_roles.create(name=role['name'], slug=role['slug'])
            print("done")

        except pynetbox.core.query.RequestError as E:
            if E.error.find("name already exists") != -1:
                print("role already exists, skipping")
                continue
            else:
                raise

def create_manufacturers(nb, ls_data):
    for manufacturer in ls_data['manufacturers']:
        try:
            print(f"Creating manufacturer '{manufacturer['name']}'...", end='')
            nb.dcim.manufacturers.create(name=manufacturer['name'], slug=manufacturer['slug'])
            print("done")

        except pynetbox.core.query.RequestError as E:
            if E.error.find("name already exists") != -1:
                print("manufacturer already exists, skipping")
                continue
            else:
                raise

def create_devicetypes(nb, ls_data):
    for devicetype in ls_data['device_types']:
        try:
            print(f"Creating device type'{devicetype['model']}'...", end='')
            nb.dcim.device_types.create(model=devicetype['model'],
                                        manufacturer=devicetype['manufacturer'],
                                        slug=devicetype['slug'])
            print("done")

        except pynetbox.core.query.RequestError as E:
            if E.error.find("must make a unique set") != -1:
                print("device type already exists, skipping")
                continue
            else:
                raise

def create_intf_templates(nb, ls_data):
    for devicetype in ls_data['device_types']:
        print("Adding interface templates to device type...", end='')
        for i in range(1, devicetype['interface_qty'] + 1):
            try:
                nb.dcim.interface_templates.create(name=f"{devicetype['interface_prefix']}{i}",
                                                   device_type={'model': devicetype['model']},
                                                   type='1000base-t')
            except pynetbox.core.query.RequestError as E:
                if E.error.find("must make a unique set") != -1:
                    print(f"interface {devicetype['interface_prefix']}{i} already exists, skipping")
                    continue
                else:
                    raise
        print("done")

def create_tags(nb, ls_data):
    for tag in ls_data['tags']:
        print(f"Adding tag {tag['name']}...", end='')
        try:
            nb.extras.tags.create(**tag)
            print("done")
        except pynetbox.core.query.RequestError as E:
            if E.error.find("already exists") != -1:
                print(f"tag {tag['name']} already exists, skipping")
                continue
            else:
                raise

def create_devices(nb, ls_data):
    created_devices = dict()
    for role, device in ls_data['devices'].items():
        created_devices[role] = list()
        for i in range(1, device['qty'] + 1):
            devicename = f"{device['prefix']}{i:02d}"
            try:
                print(f"Creating device '{devicename}'...", end='')
                created_devices[role].append(nb.dcim.devices.create(
                                                name=devicename,
                                                device_role=device['device_role'],
                                                device_type=device['device_type'],
                                                site=device['site'])
                                             )
                print("done")

            except pynetbox.core.query.RequestError as E:
                if E.error.find("name already exists") != -1:
                    print("device already exists, skipping")
                    existing_device = nb.dcim.devices.get(name=devicename)
                    created_devices[role].append(existing_device)
                    continue
                else:
                    raise

    return created_devices

def create_connections(nb, ls_devices):
    i = 1
    for spinedev in ls_devices['spines']:
        j = 1
        spinename = spinedev.name
        spineIntfPrefix = get_intf_prefix(nb, spinedev)
        for leafdev in ls_devices['leafs']:
            leafname = leafdev.name
            leafIntfPrefix = get_intf_prefix(nb, spinedev)
            spineintf = f"{spineIntfPrefix}{j}"
            leafintf = f"{leafIntfPrefix}{i}"
            try:
                print(f"Creating connection between {spinename} {spineintf} "
                      f"and {leafname} {leafintf}...", end='')
                nb.dcim.cables.create(
                    a_terminations = [
                        {
                            'object_type': 'dcim.interface',
                            'object_id': nb.dcim.interfaces.get(name=spineintf,
                                                                device=spinename).id
                        }
                    ],
                    b_terminations = [
                        {
                            'object_type': 'dcim.interface',
                            'object_id': nb.dcim.interfaces.get(name=leafintf,
                                                                device=leafname).id
                        }
                    ]

                )
                print("done")

            except pynetbox.core.query.RequestError:
                print("connection already exists, skipping")
                j += 1
                continue

            j += 1
        i += 1


def create_transit_prefix(nb, ls_data):
    print(f"Creating transit prefix {ls_data['transit_prefix']['prefix']}...", end='')
    transit_prefix = nb.ipam.prefixes.get(prefix=ls_data['transit_prefix']['prefix'])
    if transit_prefix:
        print("prefix already exists, skipping")
    else:
        transit_prefix = nb.ipam.prefixes.create(prefix=ls_data['transit_prefix']['prefix'],
                                                 site=ls_data['transit_prefix']['site'],
                                                 status='container')
        print("done")

    return transit_prefix

def create_loopback_prefix(nb, ls_data):
    print(f"Creating loopback prefix {ls_data['loopback_prefix']['prefix']}...", end='')
    loopback_prefix = nb.ipam.prefixes.get(prefix=ls_data['loopback_prefix']['prefix'])
    if loopback_prefix:
        print("prefix already exists, skipping")
    else:
        loopback_prefix = nb.ipam.prefixes.create(prefix=ls_data['loopback_prefix']['prefix'],
                                                  site=ls_data['loopback_prefix']['site'],
                                                  status='container')
        loopback_s32 = loopback_prefix.available_prefixes.create({'prefix_length': 32})
        loopback_s32.available_ips.create({'description': 'RESERVED'})

        print("done")

    return loopback_prefix

def create_rir_asn(nb, ls_data, ls_devices):
    try:
        print(f"Creating RIR {ls_data['rir']['name']}...", end='')
        rir = nb.ipam.rirs.create(**ls_data['rir'])
        print("done")

    except pynetbox.core.query.RequestError as E:
        if E.error.find("name already exists") != -1:
            print("RIR already exists, skipping")
            rir = nb.ipam.rirs.get(name=ls_data['rir']['name'])
        else:
            raise

    try:
        print(f"Creating Spine ASN {ls_data['asns']['spine']['asn']}...", end='')
        spine_asn = nb.ipam.asns.create(asn=ls_data['asns']['spine']['asn'],
                                        rir=rir.id, description='Spine ASN')
        print("done")

    except pynetbox.core.query.RequestError as E:
        if E.error.find("ASN already exists") != -1:
            print("ASN already exists, skipping")
            spine_asn = nb.ipam.asns.get(asn=ls_data['asns']['spine']['asn'])
        else:
            raise

    leaf_asn = ls_data['asns']['leaf']['range_start']
    leaf_asn_mapping = dict()
    if ls_data['asns']['leaf'].get('sameasn'):
        try:
            print(f"Creating Leaf ASN {leaf_asn}...", end='')
            nb_leaf_asn = nb.ipam.asns.create(asn=leaf_asn,
                                              rir=rir.id, description=f'Leaf ASN')
            print("done")

        except pynetbox.core.query.RequestError as E:
            if E.error.find("ASN already exists") != -1:
                print("ASN already exists, skipping")
                nb_leaf_asn = nb.ipam.asns.get(asn=leaf_asn)
            else:
                raise
        
        for leaf in ls_devices['leafs']:
            leaf_asn_mapping[leaf.name] = nb_leaf_asn
        
        return spine_asn, leaf_asn_mapping

    for leaf in ls_devices['leafs']:
        try:
            print(f"Creating Leaf {leaf.name} ASN {leaf_asn}...", end='')
            created_leaf_asn = nb.ipam.asns.create(asn=leaf_asn,
                                                   rir=rir.id, description=f'Leaf {leaf.name} ASN')
            leaf_asn_mapping[leaf.name] = created_leaf_asn
            print("done")

        except pynetbox.core.query.RequestError as E:
            if E.error.find("ASN already exists") != -1:
                print("ASN already exists, skipping")
                leaf_asn_mapping[leaf.name] = nb.ipam.asns.get(asn=leaf_asn)
                leaf_asn += 1
                continue
            else:
                raise

        leaf_asn += 1

    return spine_asn, leaf_asn_mapping

def get_intf_prefix(nb, device):
    ethernetIntfs = nb.dcim.interfaces.filter(device=device.name, name__ic='Ethernet')
    intfPrefixMatch = re.match(r'Ethernet(\d+\/|(?=\d+))', list(ethernetIntfs)[0].name)
    if intfPrefixMatch:
        intfPrefix = intfPrefixMatch.group(0)
    else:
        intfPrefix = None

    return intfPrefix

def create_transit_net_ips_bgp_sessions(
    nb, transit_prefix, ls_devices, spine_asn, leaf_asn_mapping):
    i = 1
    for spinedev in ls_devices['spines']:
        j = 1
        spinename = spinedev.name
        spineIntfPrefix = get_intf_prefix(nb, spinedev)
        for leafdev in ls_devices['leafs']:
            leafname = leafdev.name
            leafIntfPrefix = get_intf_prefix(nb, leafdev)
            spineintfname = f"{spineIntfPrefix}{j}"
            leafintfname = f"{leafIntfPrefix}{i}"

            spineintf = nb.dcim.interfaces.get(name=spineintfname, device=spinename)
            leafintf = nb.dcim.interfaces.get(name=leafintfname, device=leafname)

            print(f"Creating transit network and IPs between {spinename} {spineintfname} "
                  f"and {leafname} {leafintfname}...", end='')
            if spineintf.count_ipaddresses == 0 and leafintf.count_ipaddresses == 0:
                tpfx = transit_prefix
                tnet = tpfx.available_prefixes.create({'prefix_length': 31})
                spine_ip = tnet.available_ips.create(
                    {'assigned_object_id': spineintf.id,
                    'assigned_object_type':'dcim.interface'})
                leaf_ip = tnet.available_ips.create(
                    {'assigned_object_id': leafintf.id,
                    'assigned_object_type':'dcim.interface'})
                print("done")
            else:
                print("IPs already exist, skipping")
                spine_ip = nb.ipam.ip_addresses.get(device=spinename, interface=spineintfname)
                leaf_ip = nb.ipam.ip_addresses.get(device=leafname, interface=leafintfname)

            try:
                print(f"Applying L3 base tags to {spineintfname} and {leafintfname}...", end='')
                spineintf.update({'tags': [{'name':'l3base'}]})
                leafintf.update({'tags': [{'name':'l3base'}]})
                print("done")

            except pynetbox.core.query.RequestError as E:
                if E.error.find("Related object not found") != -1:
                    print("Tag 'l3base' not found, skipping")
                else:
                    raise

            try:
                print(f"Creating BGP sessions between {spinename} {spineintfname} "
                      f"and {leafname} {leafintfname}...", end='')

                nb.plugins.bgp.session.create(name=f'{spinename}-->{leafname}',
                                              site=spinedev.site.id,
                                              device=spinedev.id,
                                              local_as=spine_asn.id,
                                              remote_as=leaf_asn_mapping[leafname].id,
                                              local_address=spine_ip.id,
                                              remote_address=leaf_ip.id
                                              )

                nb.plugins.bgp.session.create(name=f'{leafname}-->{spinename}',
                                              site=leafdev.site.id,
                                              device=leafdev.id,
                                              local_as=leaf_asn_mapping[leafname].id,
                                              remote_as=spine_asn.id,
                                              local_address=leaf_ip.id,
                                              remote_address=spine_ip.id
                                              )
                print("done")

            except pynetbox.core.query.RequestError as E:
                if E.error.find("already exists") != -1:
                    print("BGP session already exists, skipping")
                    j += 1
                    continue
                else:
                    raise

            j += 1
        i += 1

def create_loopbacks_ips(nb, ls_devices, loopback_prefix):
    for ls_device in ls_devices.values():
        for device in ls_device:
            try:
                print(f"Creating Loopback0 on {device.name}...", end='')
                loopback_intf = nb.dcim.interfaces.create(
                    name='Loopback0',
                    device=device.id,
                    type='virtual')
                print("done")

            except pynetbox.core.query.RequestError as E:
                if E.error.find("must make a unique set") != -1:
                    print("interface already exists, skipping")
                    loopback_intf = nb.dcim.interfaces.get(name='Loopback0', device=device.name)
                else:
                    raise

            print(f"Creating Loopback0 IP address for {device.name}...", end='')
            if loopback_intf.count_ipaddresses == 0:
                loopback_s32 = loopback_prefix.available_prefixes.create({'prefix_length': 32})
                loopback_s32.available_ips.create(
                    {'assigned_object_id': loopback_intf.id,
                    'assigned_object_type': 'dcim.interface'})
                print("done")
            else:
                print("IP already exists, skipping")

def create_vlans_vnis(nb, ls_data):
    for vlan in ls_data['vlans']:
        print(f"Creating VLAN {vlan['name']}...", end='')
        nb_vlan = nb.ipam.vlans.get(name=vlan['name'], vid=vlan['vid'])
        if nb_vlan:
            print(f"vlan {vlan['name']} already exists, skipping")
        else:
            nb_vlan = nb.ipam.vlans.create(name=vlan['name'], vid=vlan['vid'])
            print("done")

        if vlan.get('vni'):
            try:
                print(f"Creating L2VPN VNI {vlan['vni']}...", end='')
                nb_l2vpn = nb.ipam.l2vpns.create(
                    name=vlan['name'], slug=vlan['name'], type='vxlan-evpn', identifier=vlan['vni'])
                print("done")
            except pynetbox.core.query.RequestError as E:
                if E.error.find("already exists") != -1:
                    nb_l2vpn = nb.ipam.l2vpns.get(name=vlan['name'])
                    print("L2VPN VNI already exists, skipping")
                else:
                    raise

            try:
                print(f"Creating L2VPN termination between VNI {vlan['vni']}"
                      f" and VLAN {vlan['vid']}...", end='')
                nb.ipam.l2vpn_terminations.create(l2vpn=nb_l2vpn.id,
                                                  assigned_object_type='ipam.vlan',
                                                  assigned_object_id=nb_vlan.id)
                print("done")
            except pynetbox.core.query.RequestError as E:
                if E.error.find("already exists") != -1:
                    print("L2VPN termination already exists")
                else:
                    raise
def main():
    nb = pynetbox.api(NB_URL, NB_API_TOKEN)
    parser = argparse.ArgumentParser(description='Load leaf/spine topology into Netbox')
    parser.add_argument('lsdata', help="The leaf/spine data file in YAML format")
    args = parser.parse_args()
    with open(args.lsdata) as ndf:
        ls_data = yaml.load(ndf, Loader=yaml.Loader)

    create_sites(nb, ls_data)
    create_roles(nb, ls_data)
    create_manufacturers(nb, ls_data)
    create_devicetypes(nb, ls_data)
    create_intf_templates(nb, ls_data)
    ls_devices = create_devices(nb, ls_data)
    create_tags(nb, ls_data)
    create_connections(nb, ls_devices)
    transit_prefix = create_transit_prefix(nb, ls_data)
    loopback_prefix = create_loopback_prefix(nb, ls_data)
    spine_asn, leaf_asn_mapping =  create_rir_asn(nb, ls_data, ls_devices)
    create_transit_net_ips_bgp_sessions(nb, transit_prefix, ls_devices, spine_asn, leaf_asn_mapping)
    create_loopbacks_ips(nb, ls_devices, loopback_prefix)
    create_vlans_vnis(nb, ls_data)

if __name__ == '__main__':
    main()
