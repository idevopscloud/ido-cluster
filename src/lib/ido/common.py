import os
import subprocess
from config import *
import etcd
import urllib2
import time
import shutil

def restart_container(container_name, image, volumns, ports, env_vars):
    os.system('bash -c \"docker rm -f {} 2>&1\">/dev/null'.format(container_name))
    cmdline = [
        'docker',
        'run',
        '-d',
        '--restart=always',
        '--name={}'.format(container_name)
    ]
    if env_vars is not None:
        for key, value in env_vars.items():
            cmdline += ['-e', '{}={}'.format(key, value)]
    if ports is not None:
        for item in ports:
            cmdline += ['-p', item]
    if volumns is not None:
        for key, value in volumns.items():
            cmdline += ['-v', '{}:{}'.format(key, value)]

    cmdline.append(image)

    child = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if child.wait() != 0:
        print child.stderr.read()
        return False

    return True

def is_kube_component_ok(ip, port):
    try:
        reply = urllib2.urlopen('http://{}:{}/healthz'.format(ip, port), timeout=5)
        if reply.getcode() != 200 or reply.read() != 'ok':
            return False
        return True
    except Exception as e:
        return False

def is_docker_ok():
    fobj = file('/dev/null')
    child = subprocess.Popen('docker info'.split(), stdout=fobj, stderr=fobj)
    status = child.wait()
    if status == 0:
        return True
    else:
        return False

def kill_process_by_name(name):
    fobj = file('/dev/null')
    child = subprocess.Popen('killall {}'.format(name).split(), stdout=fobj, stderr=fobj)
    status = child.wait()

def load_flannel_subnet():
    try:
        fobj = file('/var/run/flannel/subnet.env')
        lines = fobj.readlines()
        for line in lines:
            k,v = line.split('=')
            os.environ[k] = v
        return True
    except Exception:
        print 'Flannel is not OK'

def start_flannel(binary_path, cluster_config):
    kill_process_by_name('flanneld')
    logfile = file('/var/log/ido/flannel.log', 'a')
    cmdline = '{} --etcd-endpoints=http://{}:4001'.format(binary_path, cluster_config.master_ip).split()
    child = subprocess.Popen(cmdline, stdout=logfile, stderr=logfile)
    while child.poll() is None:
        if load_flannel_subnet():
            print 'flannel started successfully'
            return True
        else:
            time.sleep(1)
    return False

def start_docker(binary_path, cluster_config=None):
    print 'starting docker'
    #os.system('bash -c \"service docker stop 2>&1\">/dev/null')
    kill_process_by_name('docker')
    if not load_flannel_subnet():
        print 'flanneld is not ok'
        return False
    os.system('bash -c \"ip link del docker0 2>&1\n" >/dev/null')
    cmdline = '{binary_path} -d --bip={subnet} ' \
              '--mtu={mtu} '\
              '--log-level={log_level} ' \
              '--storage-driver=aufs' \
              .format(binary_path=binary_path,
                      subnet=os.environ['FLANNEL_SUBNET'],
                      mtu=os.environ['FLANNEL_MTU'],
                      log_level = cluster_config.docker_log_level)
    for registry in cluster_config.docker_registries:
        cmdline += ' --insecure-registry {}'.format(registry)
    docker_log_fobj = file(cluster_config.log_dir + '/docker.log', 'a')
    child = subprocess.Popen(cmdline.split(), stdout=docker_log_fobj, stderr=docker_log_fobj)
    while child.poll() is None:
        if is_docker_ok():
            print 'docker started successfully'
            return True
        else:
            time.sleep(1)
    return False

def is_flannel_config_in_etcd(etcd_client):
    try:
        key = '/coreos.com/network/config'
        result = etcd_client.read(key).value
        return True
    except:
        return False

def get_etcd_client(master_ip):
   return etcd.Client(host=master_ip, port=4001)

def push_flannel_config(etcd_client, cluster_config):
    key = '/coreos.com/network/config'
    value = json.dumps(cluster_config.network_config.to_flannel_dict())
    etcd_client.write(key, value)

def load_config_from_etcd(etcd_client):
    try:
        key = '/ido/config'
        result = etcd_client.read(key).value
        cluster_config = ClusterConfig()
        cluster_config.load_from_json(json.loads(result))
        return cluster_config
    except:
        return None

