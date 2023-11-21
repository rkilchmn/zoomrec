#!/bin/bash
# Get the header line from rocm-smi output
header=$(rocm-smi | head -n 5 | tail -n 1)
# Print the header line
echo "$header"
while true
do
  # Get the GPU status data for GPU 0
  gpu_status=$(rocm-smi | grep -E '^0')
  # Print the GPU status data inline
  echo -ne "$gpu_status\033[0K\r"
  # Wait for one second before refreshing the GPU status again
  sleep 1
done
