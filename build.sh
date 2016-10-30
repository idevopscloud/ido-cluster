#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd ${DIR}

workdir=${DIR}/target/workdir

rm -rf target 2>/dev/null
mkdir -p ${workdir}

cp -r src/master ${workdir}
cp -r src/node ${workdir}
cp -r src/lib ${workdir}

cd $workdir
git clone git@bitbucket.org:idevops/python-etcd.git
cd python-etcd && git checkout 0.4.3
cp -r src/etcd $workdir/lib
cp -r $workdir/lib $workdir/master
cp -r $workdir/lib $workdir/node

cd $workdir
tar czvf ido-master.tar.gz master
tar czvf ido-node.tar.gz node
mv ido-master.tar.gz ..
mv ido-node.tar.gz ..

