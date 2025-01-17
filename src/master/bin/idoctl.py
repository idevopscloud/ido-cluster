#!/usr/bin/env python

import sys
import os
import subprocess
import json
import time
import argparse
import urllib2

if 'IDO_MASTER_HOME' not in os.environ:
    print 'Environment variable <IDO_MASTER_HOME> is not set'
    sys.exit(1)
else:
    IDO_MASTER_HOME = os.environ['IDO_MASTER_HOME']

sys.path.insert(0, IDO_MASTER_HOME + '/lib')
import ido
import etcd

components_version = {
    'paas-api': '1.1.1',
    'paas-controller': '1.1',
    'paas-agent': '0.9.2',
}

def cmd_reset(args):
    global components_version
    if not args.is_force:
        print('Dangerous! All cluster data will be lost.')
        input_str = raw_input('Input your choice y/n: ')
        if input_str == 'n':
            return False
        elif input_str == 'y':
            pass
        else:
            print 'Please input y or n'
            return False

    print 'Start reset cluster ...'
    master_mgr = ido.MasterManager(components_version)
    master_mgr.reset()
    print 'Cluster resetting is done'

def cmd_start(args):
    global components_version
    master_mgr = ido.MasterManager(components_version)

    if args.component == 'docker':
        master_mgr.start_docker()
    elif args.component == 'etcd':
        master_mgr.start_etcd()
    elif args.component == 'flannel':
        master_mgr.start_flannel()
    elif args.component == 'k8s':
        master_mgr.start_kubernetes_master()
    elif args.component == 'heat':
        master_mgr.start_heat()
    elif args.component == 'paas-api':
        master_mgr.start_paas_api()
    elif args.component == 'paas-controller':
        master_mgr.start_paas_controller()
    elif args.component == 'paas-agent':
        master_mgr.start_paas_agent()
    elif args.component == 'all':
        master_mgr.start()

def cmd_stop(args):
    global components_version
    master_mgr = ido.MasterManager(components_version)
    if master_mgr.stop():
        print "master is stopped successfully"

def help(args):
    print 'help command here'

def main(environ, argv):
    parser = argparse.ArgumentParser(prog='ido-master')
    subparsers = parser.add_subparsers(help='sub-command help')

    parser_reset = subparsers.add_parser('reset')
    parser_reset.add_argument('-f', action="store_true", dest='is_force')
    parser_reset.set_defaults(func=cmd_reset)

    parser_stop = subparsers.add_parser('stop')
    parser_stop.set_defaults(func=cmd_stop)

    parser_start = subparsers.add_parser('start')
    parser_start.add_argument('component', choices=['all', 'docker', 'etcd','flannel', 'k8s', 'heat', 'paas-api', 'paas-controller', 'paas-agent'])
    parser_start.set_defaults(func=cmd_start)

    args = parser.parse_args(sys.argv[1:])
    return (args.func(args))

if __name__ == '__main__':
    main(os.environ, sys.argv[1:])

