import os
import pynetbox

NB_URL = 'http://localhost'
NB_API_TOKEN = None

api_token_file = os.environ['HOME'] + "/nb_api_token"
if not NB_API_TOKEN and os.path.isfile(api_token_file):
    with open(api_token_file) as f:
        NB_API_TOKEN = f.read().strip()

SITES = [
    {'name': 'vagrantlab', 'slug': 'vagrantlab'}
]

ROLES = [
    {'name': 'leaf', 'slug': 'leaf'},
    {'name': 'spine', 'slug': 'spine'}
]

MANUFACTURERS = [
    {'name': 'Arista', 'slug': 'arista'}
]

DEVICE_TYPES = [
    {
        'model': 'ceos-switch',
        'manufacturer': {'name': 'Arista'},
        'slug': 'ceosswitch',
        'interface_qty': 24
    }
]

DEVICES = {
    'spines':
        {
            'prefix': 'ceos-spine-',
            'device_role': {'name': 'spine'},
            'device_type': {'model': 'ceos-switch'},
            'site': {'name': 'vagrantlab'},
            'qty': 2
        },
    'leafs':
        {
            'prefix': 'ceos-leaf-',
            'device_role': {'name': 'leaf'},
            'device_type': {'model': 'ceos-switch'},
            'site': {'name': 'vagrantlab'},
            'qty': 4
        }
}

TRANSIT_PREFIX = {
    'prefix': '192.168.254.0/24',
    'site': {'name': 'vagrantlab'}
}

RIR = {
    'name': 'VagrantLabRIR',
    'slug': 'vagrantlabrir',
    'is_private': True
}

ASNS = {
    'spine': {
        'asn': 65100
    },
    'leaf': {
        'range_start': 64601
    }
}

def create_sites(nb):
    for site in SITES:
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

def create_roles(nb):
    for role in ROLES:
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

def create_manufacturers(nb):
    for manufacturer in MANUFACTURERS:
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

def create_devicetypes(nb):
    for devicetype in DEVICE_TYPES:
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

def create_intf_templates(nb):
    for devicetype in DEVICE_TYPES:
        print("Adding interface templates to device type...", end='')
        for i in range(1, devicetype['interface_qty'] + 1):
            try:
                nb.dcim.interface_templates.create(name=f'Ethernet{i}',
                                                   device_type={'model': devicetype['model']},
                                                   type='1000base-t')
            except pynetbox.core.query.RequestError as E:
                if E.error.find("must make a unique set") != -1:
                    print(f"interface Ethernet{i} already exists, skipping")
                    continue
                else:
                    raise
        print("done")

def create_devices(nb):
    created_devices = dict()
    for role, device in DEVICES.items():
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
        for leafdev in ls_devices['leafs']:
            leafname = leafdev.name
            spineintf = f"Ethernet{j}"
            leafintf = f"Ethernet{i}"
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


def create_transit_prefix(nb):
    print(f"Creating transit prefix {TRANSIT_PREFIX['prefix']}...", end='')
    if nb.ipam.prefixes.get(prefix=TRANSIT_PREFIX['prefix']):
        print("prefix already exists, skipping")
    else:
        nb.ipam.prefixes.create(prefix=TRANSIT_PREFIX['prefix'],
                                site=TRANSIT_PREFIX['site'], status='container')
        print("done")

def create_rir_asn(nb, ls_devices):
    try:
        print(f"Creating RIR {RIR['name']}...", end='')
        rir = nb.ipam.rirs.create(**RIR)
        print("done")

    except pynetbox.core.query.RequestError as E:
        if E.error.find("name already exists") != -1:
            print("RIR already exists, skipping")
            rir = nb.ipam.rirs.get(name=RIR['name'])
        else:
            raise

    try:
        print(f"Creating Spine ASN {ASNS['spine']['asn']}...", end='')
        spine_asn = nb.ipam.asns.create(asn=ASNS['spine']['asn'],
                                        rir=rir.id, description='Spine ASN')
        print("done")

    except pynetbox.core.query.RequestError as E:
        if E.error.find("ASN already exists") != -1:
            print("ASN already exists, skipping")
            spine_asn = nb.ipam.asns.get(asn=ASNS['spine']['asn'])
        else:
            raise

    leaf_asn = ASNS['leaf']['range_start']
    leaf_asn_mapping = dict()
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

def create_transit_net_ips_bgp_sessions(nb, ls_devices, spine_asn, leaf_asn_mapping):
    i = 1
    for spinedev in ls_devices['spines']:
        j = 1
        spinename = spinedev.name
        for leafdev in ls_devices['leafs']:
            leafname = leafdev.name
            spineintfname = f"Ethernet{j}"
            leafintfname = f"Ethernet{i}"

            spineintf = nb.dcim.interfaces.get(name=spineintfname, device=spinename)
            leafintf = nb.dcim.interfaces.get(name=leafintfname, device=leafname)

            print(f"Creating transit network and IPs between {spinename} {spineintfname} "
                  f"and {leafname} {leafintfname}...", end='')
            if spineintf.count_ipaddresses == 0 and leafintf.count_ipaddresses == 0:
                tpfx = nb.ipam.prefixes.get(prefix=TRANSIT_PREFIX['prefix'])
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
                print(f"Creating BGP session between {spinename} {spineintfname} "
                      f"and {leafname} {leafintfname}...", end='')

                nb.plugins.bgp.session.create(name=f'{spinename}-{leafname}',
                                              site=spinedev.site.id,
                                              device=spinedev.id,
                                              local_as=spine_asn.id,
                                              remote_as=leaf_asn_mapping[leafname].id,
                                              local_address=spine_ip.id,
                                              remote_address=leaf_ip.id
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

def main():
    nb = pynetbox.api(NB_URL, NB_API_TOKEN)

    create_sites(nb)
    create_roles(nb)
    create_manufacturers(nb)
    create_devicetypes(nb)
    create_intf_templates(nb)
    ls_devices = create_devices(nb)
    create_connections(nb, ls_devices)
    create_transit_prefix(nb)
    spine_asn, leaf_asn_mapping =  create_rir_asn(nb, ls_devices)
    create_transit_net_ips_bgp_sessions(nb, ls_devices, spine_asn, leaf_asn_mapping)

if __name__ == '__main__':
    main()
