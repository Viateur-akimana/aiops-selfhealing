#!/bin/bash

set -e

echo "TechStream AIOps - AWS Resource Cleanup"
echo "======================================"

echo "WARNING: This will destroy all AWS resources!"
read -p "Type 'destroy-all' to confirm: " -r CONFIRM

if [[ $CONFIRM != "destroy-all" ]]; then
    echo "Cleanup cancelled"
    exit 0
fi

cd terraform

echo "Destroying AWS resources..."
terraform destroy -auto-approve

echo "Cleanup complete"

cd ..

