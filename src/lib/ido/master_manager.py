from .common import *
import subprocess
from config import *
import etcd

class MasterManager:
    def __init__(self, components_version):
        try:
            self.CLUSTER_CONFIG_FILE = '/etc/ido/master.json'
            self.IDO_MASTER_HOME = os.environ['IDO_MASTER_HOME']
            self.cluster_config = None
            self.cluster_config_local = ClusterConfig()
            self.cluster_config_local.load_from_file(self.CLUSTER_CONFIG_FILE)
            self.master_ip = self.cluster_config_local.master_ip
            self.etcd_client = get_etcd_client(self.master_ip)
            self.components_version = components_version
            self.paas_api_version = components_version['paas-api']
            self.paas_controller_version = components_version['paas-controller']
            self.paas_agent_version = components_version['paas-agent']

            if not os.path.exists('/var/log/ido'):
                os.makedirs('/var/log/ido')
        except:
            raise

    def load_config_from_etcd(self):
        if self.cluster_config is not None:
            return self.cluster_config
        else:
            return load_config_from_etcd(self.etcd_client)

    def start_etcd(self):
        print 'Starting etcd'
        cmd_line = [
            self.IDO_MASTER_HOME + '/bin/etcd',
            '-name=node1',
            '-initial-advertise-peer-urls=http://{}:2380'.format(self.master_ip),
            '-advertise-client-urls=http://{}:2380'.format(self.master_ip),
            '-listen-peer-urls=http://{}:2380'.format(self.master_ip),
            '-listen-client-urls=http://{}:4001,http://127.0.0.1:4001'.format(self.master_ip),
            '-initial-cluster',
            'node1=http://{}:2380'.format(self.master_ip),
            '-data-dir={}'.format(self.cluster_config_local.etcd_data_path),
            '-initial-cluster-token',
            'ido-etcd-cluster',
            '-initial-cluster-state',
            'new'
        ]
        etcd_log_fobj = file('/var/log/ido/etcd.log', 'a')
        child = subprocess.Popen(cmd_line, stdout=etcd_log_fobj, stderr=etcd_log_fobj)
        while child.poll() is None:
            if self.is_etcd_ok():
                print 'etcd started successfully'
                key = '/ido/config'
                value = json.dumps(self.cluster_config_local.to_dict())
                self.etcd_client.write(key, value)

                return True

        return False

    def is_etcd_ok(self):
        try:
            reply = urllib2.urlopen('http://127.0.0.1:4001/version', timeout=5)
            if reply.getcode() != 200:
                return False
            return True
        except Exception as e:
            return False

    def start_docker(self):
        if not self.is_etcd_ok():
            print 'etcd is not OK'
            return False
        cluster_config = self.load_config_from_etcd()
        return start_docker(self.IDO_MASTER_HOME + '/bin/docker', cluster_config)

    def start_flannel(self):
        cluster_config = self.load_config_from_etcd()
        if not is_flannel_config_in_etcd(self.etcd_client):
            push_flannel_config(self.etcd_client, cluster_config)
        start_flannel(self.IDO_MASTER_HOME + '/bin/flanneld', cluster_config)

    def __start_kube_apiserver(self, cluster_config):
        print 'starting kube-apiserver'
        kill_process_by_name('kube-apiserver')
        cmdline = 'kube-apiserver --insecure-bind-address={master_ip} ' \
                  ' --bind-address={master_ip} '\
                  ' --insecure-port=8080 ' \
                  ' --kubelet-port=10250 '\
                  ' --etcd-servers=http://127.0.0.1:4001' \
                  ' --service-cluster-ip-range={service_ip_range} '\
                  .format(master_ip = cluster_config.master_ip,
                          service_ip_range = cluster_config.service_ip_range)
        logfile = file('/var/log/ido/kube-apiserver.log', 'a')
        child = subprocess.Popen(cmdline.split(), stdout=logfile, stderr=logfile)
        while child.poll() is None:
            if is_kube_component_ok(cluster_config.master_ip, 8080):
                print 'kube-apiserver started successfully'
                return True
            else:
                time.sleep(1)
        return False

    def __start_kube_controller(self, cluster_config):
        print 'starting kube-controller'
        kill_process_by_name('kube-controller-manager')
        cmdline = 'kube-controller-manager --master={master_ip}:8080'\
                  ' --address={master_ip}'\
                  .format(master_ip = cluster_config.master_ip)
        logfile = file('/var/log/ido/kube-controller-manager.log', 'a')
        child = subprocess.Popen(cmdline.split(), stdout=logfile, stderr=logfile)
        while child.poll() is None:
            if is_kube_component_ok(cluster_config.master_ip, 10252):
                print 'kube-controller started successfully'
                return True
            else:
                time.sleep(1)
        return False

    def __start_kube_scheduler(self, cluster_config):
        print 'starting kube-scheduler'
        kill_process_by_name('kube-scheduler')
        cmdline = 'kube-scheduler --master={master_ip}:8080'\
                  ' --address={master_ip}'\
                  .format(master_ip = cluster_config.master_ip)
        logfile = file('/var/log/ido/kube-scheduler.log', 'a')
        child = subprocess.Popen(cmdline.split(), stdout=logfile, stderr=logfile)
        while child.poll() is None:
            if is_kube_component_ok(cluster_config.master_ip, 10251):
                print 'kube-scheduler started successfully'
                return True
            else:
                time.sleep(1)
        return False

    def start_kubernetes_master(self):
        cluster_config = self.load_config_from_etcd()
        self.__start_kube_apiserver(cluster_config)
        self.__start_kube_controller(cluster_config)
        self.__start_kube_scheduler(cluster_config)

    def start(self):
        self.start_etcd()
        self.start_flannel()
        self.start_docker()
        self.start_kubernetes_master()
        if not self.create_paas_agent():
            print 'Failed to start paas-agent'
        self.start_heat()
        self.start_paas_api()
        self.start_paas_controller()
        self.start_paas_agent()

    def start_heat(self):
        script_path = self.IDO_MASTER_HOME + '/bin/heat-restart.sh'
        cluster_config = self.load_config_from_etcd()
        os.system('bash {} --registry={}'.format(script_path, cluster_config.idevopscloud_registry))

    def stop(self):
        #os.system('bash -c \"service stop docker 2>&1\">/dev/null')
        kill_process_by_name('etcd')
        kill_process_by_name('docker')
        kill_process_by_name('flanneld')
        kill_process_by_name('kube-apiserver')
        kill_process_by_name('kube-controller-manager')
        kill_process_by_name('kube-scheduler')

    def reset(self):
        self.stop()

        try:
            shutil.rmtree(self.cluster_config_local.etcd_data_path)
        except:
            pass
        self.start()

    def create_paas_agent(self):
        try:
            data = file('{}/conf/paas-agent.json'.format(self.IDO_MASTER_HOME)).read()
            request = urllib2.Request('http://{}:8080/apis/extensions/v1beta1/namespaces/default/daemonsets'.format(self.master_ip),
                                      data=data,
                                      headers={'content-type':'application/json'})
            reply = urllib2.urlopen(request, timeout=5)
            if reply.getcode() not in [ 200, 201, 409 ]:
                return False
            return True
        except urllib2.HTTPError as e:
            if e.code in [409]:
                return True
        except Exception as e:
            print e

        return False

    def start_paas_api(self):
        cluster_config = self.load_config_from_etcd()
        env_vars = {
            'DOCKER_REGISTRY_URL': '{}'.format(cluster_config.private_registry),
            'K8S_IP': cluster_config.master_ip,
            'HEAT_IP': cluster_config.master_ip,
            'ETCD_IP': cluster_config.master_ip,
            'HEAT_USERNAME': 'admin',
            'HEAT_PASSWORD': 'ADMIN_PASS',
            'HEAT_AUTH_URL': 'http://{}:35357/v2.0'.format(cluster_config.master_ip),
        }
        ports = {
            '12306:12306',
        }
        image = '{}/idevops/paas-api:{}'.format(cluster_config.idevopscloud_registry, self.paas_api_version)
        return restart_container('paas-api', image, None, ports, env_vars)

    def start_paas_controller(self):
        cluster_config = self.load_config_from_etcd()
        env_vars = {
            'PAAS_API_SERVER': 'http://{}:12306'.format(cluster_config.master_ip),
            'K8S_API_SERVER': 'http://{}:8080/api/v1'.format(cluster_config.master_ip),
            'ETCD_SERVER': cluster_config.master_ip
        }
        image = '{}/idevops/paas-controller:{}'.format(cluster_config.idevopscloud_registry, self.paas_controller_version)
        return restart_container('paas-controller',
                                 image,
                                 volumns = None,
                                 ports = None,
                                 env_vars = env_vars)

    def start_paas_agent(self):
        cluster_config = self.load_config_from_etcd()
        volumns = {
            '/proc': '/host/proc:ro',
            '/sys': '/host/sys:ro',
            '/': '/rootfs:ro',
        }
        ports = {
            '22305:12305',
        }
        image = '{}/idevops/paas-agent:{}'.format(cluster_config.idevopscloud_registry, self.paas_agent_version)
        return restart_container('paas-agent',
                                 image,
                                 volumns = volumns,
                                 ports = ports,
                                 env_vars = None)

