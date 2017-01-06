from .common import *
import subprocess
from config import *
import etcd
import os

class NodeManager:
    def __init__(self):
        self.IDO_NODE_HOME = os.environ['IDO_NODE_HOME']
        self.node_config_local = self.__load_node_config_from_file('/etc/ido/node.json')
        self.master_ip = self.node_config_local.master_ip
        self.etcd_client = get_etcd_client(self.master_ip)
        self.cluster_config = load_config_from_etcd(self.etcd_client)

        if not os.path.exists('/var/log/ido'):
            os.makedirs('/var/log/ido')

    @staticmethod
    def init_local_config(master_ip, node_ip):
        params = {
            'master_ip': master_ip,
            'node_ip': node_ip
        }
        json.dump(params, file('/etc/ido/node.json', 'w'), indent=2)

    def __load_node_config_from_file(self, config_file):
        try:
            fobj = file(config_file)
            params = json.loads(fobj.read())
            return NodeConfig(params)
        except:
            raise

    def start_flannel(self):
        start_flannel(self.IDO_NODE_HOME + '/bin/flanneld', self.cluster_config)

    def start_kubernetes_node(self):
        self.__start_kube_proxy()
        self.__start_kubelet()

    def __start_kube_proxy(self):
        print 'starting kube-proxy'
        kill_process_by_name('kube-proxy')
        cmdline = '{ido_home}/bin/kube-proxy --master={master_ip}:8080'\
                  ' --proxy-mode=userspace' \
                  .format(ido_home=self.IDO_NODE_HOME, master_ip=self.cluster_config.master_ip)
        logfile = file('/var/log/ido/kube-proxy.log', 'a')
        child = subprocess.Popen(cmdline.split(), stdout=logfile, stderr=logfile)
        while child.poll() is None:
            if is_kube_component_ok('127.0.0.1', 10249):
                print 'kube-proxy started successfully'
                return True
            else:
                time.sleep(1)
        return False
    
    def __start_kubelet(self):
        print 'starting kubelet'
        kill_process_by_name('kubelet')
        cmdline = '{ido_home}/bin/kubelet --api-servers={master_ip}:8080'\
                  ' --maximum-dead-containers=10'\
                  ' --minimum-image-ttl-duration=2m0s' \
                  ' --hostname_override={node_ip}' \
                  .format(ido_home=self.IDO_NODE_HOME,
                          master_ip=self.cluster_config.master_ip,
                          node_ip=self.node_config_local.node_ip)
        logfile = file('/var/log/ido/kubelet.log', 'a')
        child = subprocess.Popen(cmdline.split(), stdout=logfile, stderr=logfile)
        while child.poll() is None:
            if is_kube_component_ok('127.0.0.1', 10248):
                print 'kubelet started successfully'
                return True
            else:
                time.sleep(1)
        return False

    def start_docker(self):
        if self.cluster_config.master_ip != self.node_config_local.node_ip:
            start_docker(self.IDO_NODE_HOME + '/bin/docker', self.cluster_config)
        self.__pull_google_pause()

    def start(self):
        self.start_flannel()
        self.start_docker()
        self.start_kubernetes_node()

    def __pull_google_pause(self):
        if not is_image_existed('gcr.io/google_containers/pause', '2.0'):
            os.system('docker pull {}/idevops/pause:2.0'.format(self.cluster_config.idevopscloud_registry))
            os.system('docker tag {}/idevops/pause:2.0 gcr.io/google_containers/pause:2.0'.format(self.cluster_config.idevopscloud_registry))

