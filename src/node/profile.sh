#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IDO_NODE_HOME=$DIR
export IDO_LOGDIR=/var/log/ido
export PATH=${IDO_NODE_HOME}/bin:$PATH

